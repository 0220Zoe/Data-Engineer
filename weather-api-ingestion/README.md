# Weather API ingestion (Prefect + DuckDB)

An incremental ingestion pipeline that pulls hourly observations from the public
[Open-Meteo archive API](https://open-meteo.com/) for several cities and loads them
into DuckDB. It's small on purpose; the point is the production patterns.

## What it demonstrates

- **Orchestration:** a Prefect flow with task-level retries (`flow.py`).
- **Resilient extraction:** retries with backoff on timeouts, connection errors, and
  retryable HTTP statuses (429, 5xx). It fails loudly after the last attempt.
- **Incremental loading:** a per-city high-water mark, so each run only requests new
  data. The last loaded day is re-read so late corrections are picked up.
- **Idempotency:** an upsert on `(city, observed_at)`. Re-running any window never
  creates duplicates.
- **Data quality:** range and null checks. Failing rows go to `weather_quarantine`
  with the reason, instead of being silently dropped.
- **Run auditing:** `pipeline_runs` records complete, partial, and failed loads per city.

## Layout

```text
flow.py              Prefect flow: extract -> validate -> load, per city
src/extract.py       API client with retries and backoff
src/transform.py     Column-oriented payload -> one row per city-hour
src/quality.py       Row-level rules and quarantine split
src/load.py          DuckDB DDL, upsert, high-water mark, run log
tests/               Unit tests, including a mocked flaky API
Dockerfile           Container for scheduled runs
```

## Run it

```bash
pip install -r requirements.txt
pytest -q             # unit tests, no network needed
python flow.py        # runs the flow and writes weather.duckdb
```

Then inspect the results:

```sql
SELECT city, COUNT(*), MAX(observed_at) FROM weather_hourly GROUP BY city;
SELECT * FROM pipeline_runs ORDER BY finished_at DESC;
```
