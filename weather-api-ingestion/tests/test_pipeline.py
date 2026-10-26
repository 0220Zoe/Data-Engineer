from datetime import date, datetime

import pytest
import requests

from src import extract, load, quality, transform

PAYLOAD = {
    "_city": "Lisbon",
    "hourly": {
        "time": ["2026-10-01T00:00", "2026-10-01T01:00", "2026-10-01T02:00"],
        "temperature_2m": [18.2, 17.9, 120.0],
        "precipitation": [0.0, 0.4, 0.0],
        "wind_speed_10m": [12.0, None, 9.5],
    },
}


def valid_rows():
    valid, _ = quality.split_valid(transform.flatten_hourly(PAYLOAD))
    return valid


def test_flatten_creates_one_row_per_hour():
    rows = transform.flatten_hourly(PAYLOAD)
    assert len(rows) == 3
    assert rows[0]["observed_at"] == datetime(2026, 10, 1, 0, 0)
    assert rows[1]["wind_speed_kmh"] is None


def test_quality_quarantines_instead_of_dropping():
    valid, bad = quality.split_valid(transform.flatten_hourly(PAYLOAD))
    assert len(valid) == 1
    assert len(bad) == 2
    assert "missing wind_speed_kmh" in bad[0]["issues"]
    assert "temperature_c=120.0 outside" in bad[1]["issues"]


def test_upsert_is_idempotent_and_applies_corrections():
    con = load.connect(":memory:")
    load.upsert(con, valid_rows())
    load.upsert(con, valid_rows())  # re-running the same window adds nothing
    assert con.execute("SELECT COUNT(*) FROM weather_hourly").fetchone()[0] == 1

    load.upsert(con, [{**valid_rows()[0], "temperature_c": 18.5}])
    assert con.execute("SELECT temperature_c FROM weather_hourly").fetchone()[0] == 18.5


def test_high_water_mark_tracks_latest_hour_per_city():
    con = load.connect(":memory:")
    assert load.high_water_mark(con, "Lisbon") is None
    load.upsert(con, valid_rows())
    assert load.high_water_mark(con, "Lisbon") == datetime(2026, 10, 1, 0, 0)


def make_response(status: int, body: bytes = b"") -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = body
    return response


class FlakySession:
    """Returns a 503 on the first call, then succeeds."""

    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return make_response(503)
        return make_response(200, b'{"hourly": {"time": []}}')


def test_extract_retries_transient_errors():
    session = FlakySession()
    payload = extract.fetch_hourly(
        "Boston", 0, 0, date(2026, 1, 1), date(2026, 1, 2),
        session=session, backoff_seconds=0,
    )
    assert session.calls == 2
    assert payload["_city"] == "Boston"


def test_extract_raises_after_max_attempts():
    class AlwaysDown:
        def get(self, *args, **kwargs):
            return make_response(500)

    with pytest.raises(RuntimeError):
        extract.fetch_hourly(
            "Boston", 0, 0, date(2026, 1, 1), date(2026, 1, 2),
            session=AlwaysDown(), max_attempts=2, backoff_seconds=0,
        )
