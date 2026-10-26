"""Row-level data quality rules. Failing rows are quarantined, not dropped."""
from __future__ import annotations

RANGES = {
    "temperature_c": (-90.0, 60.0),
    "precipitation_mm": (0.0, 500.0),
    "wind_speed_kmh": (0.0, 400.0),
}


def check_row(row: dict) -> list[str]:
    issues = []
    if row.get("observed_at") is None:
        issues.append("missing observed_at")
    for field, (low, high) in RANGES.items():
        value = row.get(field)
        if value is None:
            issues.append(f"missing {field}")
        elif not low <= value <= high:
            issues.append(f"{field}={value} outside [{low}, {high}]")
    return issues


def split_valid(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (valid_rows, quarantined_rows); quarantined rows carry their issues."""
    valid, quarantined = [], []
    for row in rows:
        issues = check_row(row)
        if issues:
            quarantined.append({**row, "issues": "; ".join(issues)})
        else:
            valid.append(row)
    return valid, quarantined
