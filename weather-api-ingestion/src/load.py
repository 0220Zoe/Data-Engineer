"""Idempotent loading into DuckDB with a high-water mark per city."""
from __future__ import annotations

from datetime import datetime, timezone

import duckdb

DDL = """
CREATE TABLE IF NOT EXISTS weather_hourly (
    city             VARCHAR   NOT NULL,
    observed_at      TIMESTAMP NOT NULL,
    temperature_c    DOUBLE,
    precipitation_mm DOUBLE,
    wind_speed_kmh   DOUBLE,
    loaded_at        TIMESTAMP NOT NULL,
    PRIMARY KEY (city, observed_at)
);
CREATE TABLE IF NOT EXISTS weather_quarantine (
    city           VARCHAR,
    observed_at    TIMESTAMP,
    payload        VARCHAR,
    issues         VARCHAR,
    quarantined_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id           VARCHAR,
    city             VARCHAR,
    status           VARCHAR,
    rows_loaded      INTEGER,
    rows_quarantined INTEGER,
    started_at       TIMESTAMP,
    finished_at      TIMESTAMP
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def connect(path: str = "weather.duckdb") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(path)
    con.execute(DDL)
    return con


def high_water_mark(con, city: str) -> datetime | None:
    return con.execute(
        "SELECT MAX(observed_at) FROM weather_hourly WHERE city = ?", [city]
    ).fetchone()[0]


def upsert(con, rows: list[dict]) -> int:
    """Insert new rows and update changed ones, so re-running a window is safe."""
    if not rows:
        return 0
    now = _now()
    con.executemany(
        """
        INSERT INTO weather_hourly VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (city, observed_at) DO UPDATE SET
            temperature_c    = excluded.temperature_c,
            precipitation_mm = excluded.precipitation_mm,
            wind_speed_kmh   = excluded.wind_speed_kmh,
            loaded_at        = excluded.loaded_at
        """,
        [
            (r["city"], r["observed_at"], r["temperature_c"],
             r["precipitation_mm"], r["wind_speed_kmh"], now)
            for r in rows
        ],
    )
    return len(rows)


def quarantine(con, rows: list[dict]) -> int:
    if not rows:
        return 0
    now = _now()
    con.executemany(
        "INSERT INTO weather_quarantine VALUES (?, ?, ?, ?, ?)",
        [(r.get("city"), r.get("observed_at"), repr(r), r["issues"], now) for r in rows],
    )
    return len(rows)


def log_run(con, run_id, city, status, loaded, quarantined, started_at) -> None:
    con.execute(
        "INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
        [run_id, city, status, loaded, quarantined, started_at, _now()],
    )
