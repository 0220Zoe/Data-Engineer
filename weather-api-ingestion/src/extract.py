"""Extract hourly weather observations from the Open-Meteo archive API."""
from __future__ import annotations

import time
from datetime import date

import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_FIELDS = ["temperature_2m", "precipitation", "wind_speed_10m"]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def fetch_hourly(
    city: str,
    latitude: float,
    longitude: float,
    start: date,
    end: date,
    session: requests.Session | None = None,
    max_attempts: int = 3,
    backoff_seconds: float = 2.0,
) -> dict:
    """Return the raw API payload, retrying transient failures with backoff."""
    session = session or requests.Session()
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(HOURLY_FIELDS),
        "timezone": "UTC",
    }
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(ARCHIVE_URL, params=params, timeout=30)
            if response.status_code in RETRYABLE_STATUS:
                raise requests.HTTPError(f"retryable status {response.status_code}")
            response.raise_for_status()
            payload = response.json()
            payload["_city"] = city
            return payload
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            last_error = exc
            if attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)
    raise RuntimeError(f"Failed to fetch {city} after {max_attempts} attempts") from last_error
