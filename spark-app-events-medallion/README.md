# App events medallion pipeline (PySpark)

A bronze → silver → gold pipeline for mobile app events that arrive from two
regional systems with different schemas. It runs locally with PySpark and is
structured to drop into a Databricks job (write Delta tables instead of parquet).

## The data problem

U.S. and EU events come from separate systems:

- **U.S.** events are nested JSON with an account ID and a plain email.
- **EU** events have a different shape, a separate member ID, epoch-millisecond
  timestamps, and an email that is already SHA-256 hashed.

Some people use the app in both regions, so counting accounts overstates the
audience. Both streams also deliver some events more than once.

## What it does

| Layer | Step |
|---|---|
| Bronze | Read raw JSON exactly as delivered |
| Silver | Flatten nested fields, standardize timestamps and platforms, and derive a privacy-safe `person_id` (SHA-256 of the normalized email) so U.S. and EU identities stitch together |
| Silver | Deduplicate on `event_id`, and quarantine rows missing identity or timestamps |
| Gold | Sessions (a new session after 30 minutes of inactivity), DAU, and MAU counted by person rather than by account |

On the sample data, stitching resolves 165 regional accounts to 148 people in the
first month, so MAU based on accounts would be overstated by about 11%.

## Run it

```bash
pip install -r requirements.txt
python scripts/generate_events.py   # optional: regenerate synthetic events
pytest -q                           # unit tests on small in-memory DataFrames
python pipeline.py                  # writes silver and gold outputs to ./output
```
