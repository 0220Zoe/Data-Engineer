"""A minimal governed data-access layer for AI assistants.

Assistants call named operations from catalog.yaml with parameters. The gateway
checks the caller's role, validates every parameter, runs pre-approved SQL with
bound values, and writes an audit record for each call, including rejected ones.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import yaml

CATALOG_PATH = Path(__file__).resolve().parent.parent / "catalog.yaml"

AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    called_at  TIMESTAMP,
    caller     VARCHAR,
    role       VARCHAR,
    operation  VARCHAR,
    params     VARCHAR,
    status     VARCHAR,
    row_count  INTEGER,
    error      VARCHAR
)
"""


class OperationError(ValueError):
    """A rejected call. Messages are written to help the assistant self-correct."""


@dataclass
class Result:
    operation: str
    columns: list[str]
    rows: list[tuple]


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    return yaml.safe_load(path.read_text())["operations"]


class Gateway:
    def __init__(self, con: duckdb.DuckDBPyConnection, catalog: dict | None = None):
        self.con = con
        self.catalog = catalog or load_catalog()
        self.con.execute(AUDIT_DDL)

    # -- public API ---------------------------------------------------------

    def call(self, operation: str, params: dict, caller: str, role: str) -> Result:
        try:
            spec = self._get_spec(operation, role)
            clean = self._validate(spec, params)
            result = self._execute(operation, spec, clean)
        except OperationError as exc:
            self._audit(caller, role, operation, params, "rejected", 0, str(exc))
            raise
        self._audit(caller, role, operation, params, "ok", len(result.rows), None)
        return result

    def tool_definitions(self) -> list[dict]:
        """Describe each operation as a JSON-schema tool an LLM can be given."""
        tools = []
        for name, spec in self.catalog.items():
            properties, required = {}, []
            for pname, p in spec["params"].items():
                schema = _json_schema(p)
                properties[pname] = schema
                if p.get("required"):
                    required.append(pname)
            tools.append({
                "name": name,
                "description": " ".join(spec["description"].split()),
                "input_schema": {"type": "object", "properties": properties,
                                 "required": required, "additionalProperties": False},
            })
        return tools

    # -- internals ----------------------------------------------------------

    def _get_spec(self, operation: str, role: str) -> dict:
        if operation not in self.catalog:
            raise OperationError(
                f"Unknown operation '{operation}'. Available: {sorted(self.catalog)}"
            )
        spec = self.catalog[operation]
        if role not in spec["allowed_roles"]:
            raise OperationError(f"Role '{role}' may not call '{operation}'")
        return spec

    def _validate(self, spec: dict, params: dict) -> dict:
        unknown = set(params) - set(spec["params"])
        if unknown:
            raise OperationError(
                f"Unknown parameter(s) {sorted(unknown)}. Allowed: {sorted(spec['params'])}"
            )
        clean = {}
        for name, p in spec["params"].items():
            value = params.get(name, p.get("default"))
            if value is None:
                if p.get("required"):
                    raise OperationError(f"Missing required parameter '{name}'")
                clean[name] = None
                continue
            clean[name] = self._check_value(name, p, value)

        if "max_date_range_days" in spec:
            span = (clean["end_date"] - clean["start_date"]).days
            if span < 0:
                raise OperationError("end_date must be on or after start_date")
            if span > spec["max_date_range_days"]:
                raise OperationError(
                    f"Date range is {span} days; the maximum is {spec['max_date_range_days']}. "
                    "Split the request into smaller ranges."
                )
        return clean

    def _check_value(self, name: str, p: dict, value):
        kind = p["type"]
        if kind == "enum":
            if value not in p["values"]:
                raise OperationError(f"'{name}' must be one of {p['values']}, got {value!r}")
            return value
        if kind == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise OperationError(f"'{name}' must be an integer")
            if not p.get("min", value) <= value <= p.get("max", value):
                raise OperationError(f"'{name}' must be between {p['min']} and {p['max']}")
            return value
        if kind == "date":
            try:
                return value if isinstance(value, date) else date.fromisoformat(value)
            except (TypeError, ValueError):
                raise OperationError(f"'{name}' must be an ISO date like 2026-10-01") from None
        if kind == "string":
            if not isinstance(value, str) or len(value) > p.get("max_length", 200):
                raise OperationError(f"'{name}' must be a string of at most {p.get('max_length', 200)} characters")
            return value
        if kind == "entity":
            # Reject guessed values and point the assistant at the discovery operation.
            exists = self.con.execute(
                "SELECT 1 FROM entity_values WHERE entity_type = ? AND entity_value = ?",
                [p["entity_type"], value],
            ).fetchone()
            if not exists:
                raise OperationError(
                    f"'{value}' is not a known {p['entity_type']}. Call discover_values with "
                    f"entity_type='{p['entity_type']}' to find the exact value."
                )
            return value
        raise OperationError(f"Unsupported parameter type '{kind}'")

    def _execute(self, operation: str, spec: dict, clean: dict) -> Result:
        sql = spec["sql"]
        if "{group_by}" in sql:
            # Safe: clean["group_by"] has already been checked against the enum.
            sql = sql.replace("{group_by}", clean["group_by"])
        bound = {k: v for k, v in clean.items() if f"${k}" in sql}
        cursor = self.con.execute(sql, bound)
        columns = [d[0] for d in cursor.description]
        return Result(operation, columns, cursor.fetchall())

    def _audit(self, caller, role, operation, params, status, row_count, error) -> None:
        self.con.execute(
            "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [datetime.now(timezone.utc).replace(tzinfo=None), caller, role, operation,
             json.dumps(params, default=str, sort_keys=True), status, row_count, error],
        )


def _json_schema(p: dict) -> dict:
    kind = p["type"]
    if kind == "enum":
        return {"type": "string", "enum": p["values"]}
    if kind == "integer":
        return {"type": "integer", "minimum": p["min"], "maximum": p["max"]}
    if kind == "date":
        return {"type": "string", "format": "date"}
    if kind == "entity":
        return {"type": "string",
                "description": f"Exact {p['entity_type']} value from discover_values"}
    return {"type": "string", "maxLength": p.get("max_length", 200)}
