"""Prefect flow: incremental, retried, quality-checked weather ingestion."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from prefect import flow, get_run_logger, task

from src import extract, load, quality, transform

CITIES = {
    "Washington DC": (38.9072, -77.0369),
    "Lisbon": (38.7223, -9.1393),
    "Boston": (42.3601, -71.0589),
}
DEFAULT_BACKFILL_DAYS = 7
ARCHIVE_LAG_DAYS = 2  # the archive API publishes with a short delay


@task(retries=2, retry_delay_seconds=10)
def extract_city(city: str, lat: float, lon: float, start: date, end: date) -> dict:
    return extract.fetch_hourly(city, lat, lon, start, end)


@task
def transform_and_check(payload: dict) -> tuple[list[dict], list[dict]]:
    rows = transform.flatten_hourly(payload)
    return quality.split_valid(rows)


@flow(name="weather-api-ingestion")
def weather_ingestion(db_path: str = "weather.duckdb") -> None:
    logger = get_run_logger()
    con = load.connect(db_path)
    run_id = str(uuid.uuid4())
    end = date.today() - timedelta(days=ARCHIVE_LAG_DAYS)

    for city, (lat, lon) in CITIES.items():
        started_at = load._now()
        hwm = load.high_water_mark(con, city)
        # Re-read the last loaded day so late-arriving corrections are upserted.
        start = hwm.date() if hwm else end - timedelta(days=DEFAULT_BACKFILL_DAYS)
        try:
            payload = extract_city(city, lat, lon, start, end)
            valid, bad = transform_and_check(payload)
            loaded = load.upsert(con, valid)
            quarantined = load.quarantine(con, bad)
            status = "complete" if not bad else "partial"
            logger.info("%s: %s rows loaded, %s quarantined", city, loaded, quarantined)
        except Exception:
            loaded, quarantined, status = 0, 0, "failed"
            logger.exception("%s failed", city)
        load.log_run(con, run_id, city, status, loaded, quarantined, started_at)


if __name__ == "__main__":
    weather_ingestion()
