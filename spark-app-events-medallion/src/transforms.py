"""Bronze -> silver -> gold transformations for regional app events.

Each function takes and returns a DataFrame so it can be unit tested and reused
in a Databricks job (swap the parquet writes in pipeline.py for Delta tables).
"""
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

SESSION_GAP_MINUTES = 30

SILVER_COLUMNS = ["event_id", "source_region", "source_user_id", "person_id",
                  "event_name", "event_ts", "platform"]


def silver_us(bronze: DataFrame) -> DataFrame:
    """Flatten nested US events and derive a privacy-safe person_id from email."""
    return bronze.select(
        F.col("event_id"),
        F.lit("US").alias("source_region"),
        F.col("user.us_account_id").alias("source_user_id"),
        F.sha2(F.lower(F.trim(F.col("user.email"))), 256).alias("person_id"),
        F.col("event.name").alias("event_name"),
        F.to_timestamp(F.col("event.ts")).alias("event_ts"),
        F.lower(F.col("device.platform")).alias("platform"),
    )


def silver_eu(bronze: DataFrame) -> DataFrame:
    """EU events arrive with a different schema and an already-hashed email."""
    return bronze.select(
        F.col("id").alias("event_id"),
        F.lit("EU").alias("source_region"),
        F.col("account.eu_member_id").alias("source_user_id"),
        F.col("account.email_sha256").alias("person_id"),
        F.col("event_name"),
        F.timestamp_seconds(F.col("event_time_ms") / 1000).alias("event_ts"),
        F.lower(F.col("platform")).alias("platform"),
    )


def unify_and_dedupe(*frames: DataFrame) -> DataFrame:
    """Union regional events and keep one row per event_id (at-least-once delivery)."""
    unified = frames[0].select(SILVER_COLUMNS)
    for frame in frames[1:]:
        unified = unified.unionByName(frame.select(SILVER_COLUMNS))
    first = Window.partitionBy("event_id").orderBy("event_ts")
    return (
        unified.withColumn("_rn", F.row_number().over(first))
        .filter("_rn = 1")
        .drop("_rn")
    )


def quarantine_invalid(events: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Split rows with missing identity or timestamps into a quarantine set."""
    bad = F.col("person_id").isNull() | F.col("event_ts").isNull() | F.col("event_name").isNull()
    return events.filter(~bad), events.filter(bad)


def sessionize(events: DataFrame, gap_minutes: int = SESSION_GAP_MINUTES) -> DataFrame:
    """Assign session ids: a new session starts after `gap_minutes` of inactivity."""
    by_person = Window.partitionBy("person_id").orderBy("event_ts")
    with_gap = events.withColumn(
        "_prev_ts", F.lag("event_ts").over(by_person)
    ).withColumn(
        "_new_session",
        (F.col("_prev_ts").isNull()
         | ((F.unix_timestamp("event_ts") - F.unix_timestamp("_prev_ts")) > gap_minutes * 60)
         ).cast("int"),
    )
    return (
        with_gap.withColumn("session_number", F.sum("_new_session").over(by_person))
        .withColumn("session_id", F.concat_ws("-", "person_id", "session_number"))
        .drop("_prev_ts", "_new_session")
    )


def gold_sessions(sessionized: DataFrame) -> DataFrame:
    return sessionized.groupBy("person_id", "session_id").agg(
        F.min("event_ts").alias("session_start"),
        F.max("event_ts").alias("session_end"),
        F.count("*").alias("events"),
        F.countDistinct("source_region").alias("regions"),
    )


def gold_daily_active(events: DataFrame) -> DataFrame:
    return (
        events.withColumn("activity_date", F.to_date("event_ts"))
        .groupBy("activity_date")
        .agg(F.countDistinct("person_id").alias("dau"))
    )


def gold_monthly_active(events: DataFrame) -> DataFrame:
    return (
        events.withColumn("activity_month", F.date_trunc("month", "event_ts").cast("date"))
        .groupBy("activity_month")
        .agg(
            F.countDistinct("person_id").alias("mau"),
            F.countDistinct("source_user_id").alias("unstitched_accounts"),
        )
    )
