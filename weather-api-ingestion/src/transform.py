"""Flatten the API's column-oriented payload into one row per city-hour."""
from __future__ import annotations

from datetime import datetime


def flatten_hourly(payload: dict) -> list[dict]:
    hourly = payload.get("hourly") or {}
    rows = []
    for i, ts in enumerate(hourly.get("time") or []):
        rows.append(
            {
                "city": payload["_city"],
                "observed_at": datetime.fromisoformat(ts),
                "temperature_c": _at(hourly.get("temperature_2m"), i),
                "precipitation_mm": _at(hourly.get("precipitation"), i),
                "wind_speed_kmh": _at(hourly.get("wind_speed_10m"), i),
            }
        )
    return rows


def _at(values: list | None, i: int):
    if values is None or i >= len(values):
        return None
    return values[i]
