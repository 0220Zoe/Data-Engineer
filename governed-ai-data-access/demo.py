"""Show how an assistant's tool calls flow through the gateway."""
import json

import duckdb

from src import sample_data
from src.gateway import Gateway, OperationError

con = duckdb.connect()
sample_data.build(con)
gw = Gateway(con)

print("Tool definitions given to the assistant:")
print(json.dumps(gw.tool_definitions()[1], indent=2)[:600], "...\n")

calls = [
    # The assistant guesses an author name that doesn't exist exactly...
    ("retrieve_article_metrics", {"start_date": "2026-09-01", "end_date": "2026-09-30", "author": "Jordan"}),
    # ...so it follows the error's advice and discovers the exact value...
    ("discover_values", {"entity_type": "author", "search": "jordan"}),
    # ...then retries with the exact value.
    ("retrieve_article_metrics", {"start_date": "2026-09-01", "end_date": "2026-09-30",
                                  "author": "Jordan Lee", "group_by": "author"}),
    # Invented parameters are rejected rather than silently ignored.
    ("retrieve_article_metrics", {"start_date": "2026-09-01", "end_date": "2026-09-30",
                                  "filters": "Author=Jordan Lee"}),
]
for op, params in calls:
    try:
        result = gw.call(op, params, caller="demo-assistant", role="assistant")
        print(f"OK   {op}: {result.rows}")
    except OperationError as exc:
        print(f"FAIL {op}: {exc}")

print("\nAudit log:")
for row in con.execute("SELECT operation, status, row_count FROM audit_log").fetchall():
    print("  ", row)
