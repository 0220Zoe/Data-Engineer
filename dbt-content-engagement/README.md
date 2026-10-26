# Content engagement models (dbt + DuckDB)

A layered dbt project modeling article readership and social media engagement for
a digital publisher. It uses synthetic data and runs locally on DuckDB; the same
models run on Snowflake or Databricks by swapping the profile.

## The modeling problem

Social posts keep collecting likes and shares for days after they're published, so
recent posts always look like they're underperforming. Dropping recent posts from
reports is a common fix, but it hides data and makes post counts stop
reconciling. This project **flags** each post with a maturity window
(`is_mature`, controlled by the `maturity_days` variable) so analysts can filter
explicitly, and every post is still counted.

## Layers

| Layer | Models | Purpose |
|---|---|---|
| Staging | `stg_articles`, `stg_pageviews`, `stg_social_post_snapshots` | Type casting, cleanup, and deduplication of replayed events |
| Intermediate | `int_social_posts_latest` | Latest cumulative engagement snapshot per post |
| Marts | `dim_articles`, `fct_article_daily_views`, `fct_social_post_engagement`, `article_performance` | Analytics-ready tables at a documented grain |

`article_performance` aggregates each fact table *before* joining to the article
dimension, which avoids join fan-out inflating the totals.

## Tests

- Generic tests: `unique`, `not_null`, `accepted_values`, `relationships`.
- A custom generic test, `unique_combination`, enforces the article × day grain.
- Singular tests check that cumulative engagement never decreases, and that every
  deduplicated pageview is accounted for in the mart.

## Run it

```bash
pip install dbt-duckdb
python scripts/generate_seeds.py      # optional: regenerate the synthetic data
dbt build --profiles-dir .            # seeds, models, and all tests
dbt build --profiles-dir . --vars '{maturity_days: 3}'
```
