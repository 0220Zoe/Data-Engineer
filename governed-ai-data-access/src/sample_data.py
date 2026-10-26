"""Synthetic warehouse tables plus the entity lookup used by discovery operations."""
from __future__ import annotations

import random
from datetime import date, timedelta

import duckdb

SECTIONS = ["Politics", "Economy", "Technology", "Health", "Energy"]
AUTHORS = ["Alex Rivera", "Jordan Lee", "Sam Patel", "Morgan Chen", "Taylor Brooks", "Casey Kim"]


def build(con: duckdb.DuckDBPyConnection, seed: int = 1) -> None:
    rng = random.Random(seed)
    rows, start = [], date(2026, 7, 1)
    for day in range(110):
        for section in SECTIONS:
            for author in rng.sample(AUTHORS, 3):
                views = rng.randint(50, 900)
                rows.append((start + timedelta(days=day), section, author, views,
                             int(views * rng.uniform(0.4, 0.8))))
    con.execute("""
        CREATE OR REPLACE TABLE article_daily_metrics (
            view_date DATE, section VARCHAR, author VARCHAR,
            pageviews INTEGER, unique_readers INTEGER)
    """)
    con.executemany("INSERT INTO article_daily_metrics VALUES (?, ?, ?, ?, ?)", rows)
    refresh_entities(con)


def refresh_entities(con: duckdb.DuckDBPyConnection) -> None:
    """Materialize distinct filter values once (e.g. daily), so discovery calls
    hit a small lookup table instead of scanning the large fact table."""
    con.execute("""
        CREATE OR REPLACE TABLE entity_values AS
        SELECT 'section' AS entity_type, section AS entity_value, COUNT(*) AS row_count
        FROM article_daily_metrics GROUP BY section
        UNION ALL
        SELECT 'author', author, COUNT(*)
        FROM article_daily_metrics GROUP BY author
    """)
