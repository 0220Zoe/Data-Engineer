# Data Engineering Portfolio

Hands-on data engineering projects by **Zoe Pan**: ingestion, modeling, data
quality, and large-scale transformation. Each project is self-contained, runs
locally, and has its own tests and README.

| Project | Stack | Highlights |
|---|---|---|
| [nba-coaching-pipeline](nba-coaching-pipeline/) | Python, SQLite, SQL | Reconciles incompatible vendor IDs without fuzzy matching; audit tables for rejected records, pipeline runs, and API fetches |
| [weather-api-ingestion](weather-api-ingestion/) | Prefect, DuckDB, Docker | Incremental loads with a high-water mark, retries with backoff, idempotent upserts, quarantine for failed quality checks |
| [dbt-content-engagement](dbt-content-engagement/) | dbt, DuckDB | Layered staging → intermediate → marts models, a maturity-window flag for still-growing social engagement, generic and singular tests |
| [spark-app-events-medallion](spark-app-events-medallion/) | PySpark (Databricks-ready) | Bronze → silver → gold, nested JSON flattening, cross-region identity stitching, sessionization, DAU/MAU |

## Principles across these projects

- **Never drop bad data silently.** Quarantine it with a reason, or flag it.
- **Make every load safe to re-run.** Upserts, deduplication, and explicit grains.
- **Test the logic, not just the code.** Reconciliation checks, grain tests, and
  edge cases like replayed events and late-arriving corrections.
- **Document the limits.** Each README states what the data can and can't support.

All tests run in CI on every push (see `.github/workflows/ci.yml`).
