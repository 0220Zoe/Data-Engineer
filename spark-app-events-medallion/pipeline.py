"""Run the medallion pipeline locally. On Databricks, write Delta tables instead."""
from pathlib import Path

from pyspark.sql import SparkSession

from src import transforms as t

ROOT = Path(__file__).resolve().parent
DATA, OUT = ROOT / "data", ROOT / "output"


def main() -> None:
    spark = (SparkSession.builder.appName("app-events-medallion")
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())

    bronze_us = spark.read.json(str(DATA / "us_events.jsonl"))
    bronze_eu = spark.read.json(str(DATA / "eu_events.jsonl"))

    events = t.unify_and_dedupe(t.silver_us(bronze_us), t.silver_eu(bronze_eu))
    valid, quarantined = t.quarantine_invalid(events)
    sessionized = t.sessionize(valid).cache()

    outputs = {
        "silver/events": sessionized,
        "silver/quarantine": quarantined,
        "gold/sessions": t.gold_sessions(sessionized),
        "gold/daily_active_users": t.gold_daily_active(sessionized),
        "gold/monthly_active_users": t.gold_monthly_active(sessionized),
    }
    for name, frame in outputs.items():
        frame.write.mode("overwrite").parquet(str(OUT / name))

    print(f"bronze rows: {bronze_us.count() + bronze_eu.count()}")
    print(f"silver rows after dedupe: {sessionized.count()} (quarantined: {quarantined.count()})")
    outputs["gold/monthly_active_users"].orderBy("activity_month").show()
    spark.stop()


if __name__ == "__main__":
    main()
