# Governed AI data access

A small gateway that lets an AI assistant answer business questions from a
warehouse **without writing its own SQL**. The assistant can only call approved
operations from a catalog, and every call is permission-checked, validated, and
audited. Built on DuckDB with synthetic data; the same pattern applies to
Snowflake or Databricks.

## Why this pattern

Letting an LLM write free-form SQL against a warehouse causes predictable
problems: invented column names, guessed filter values, unbounded scans, and no
record of what was asked. A catalog of governed operations fixes this:

| Problem | How the gateway handles it |
|---|---|
| The model guesses a filter value ("Jordan" instead of "Jordan Lee") | Entity parameters are checked against a lookup table, and the error tells the model to call `discover_values` first |
| The model invents parameters (`filters: "Author=..."`) | Unknown parameters are rejected with the list of allowed ones, instead of being silently ignored |
| SQL injection or arbitrary SQL | Values are bound parameters; the one substituted identifier (`group_by`) must match an enum |
| Expensive queries | Date ranges and row limits are capped per operation |
| No accountability | Every call, including rejected ones, is written to `audit_log` with caller, role, parameters, and outcome |
| "Is the answer right?" | `verified_queries.yaml` pairs real questions with known-correct answers, checked by `evaluate.py` and in CI |

## Two operation types

- **Discovery** (`discover_values`) returns valid filter values. It reads a small
  `entity_values` lookup table that is refreshed on a schedule, rather than
  scanning the large fact table on every call.
- **Retrieval** (`retrieve_article_metrics`) returns metrics using only the
  validated parameters.

`Gateway.tool_definitions()` turns the catalog into strict JSON-schema tool
definitions (`additionalProperties: false`) that can be handed to an LLM.

## Run it

```bash
pip install -r requirements.txt
python demo.py        # an assistant guesses wrong, self-corrects via discovery, and is audited
python evaluate.py    # verified-query evaluation
pytest -q
```
