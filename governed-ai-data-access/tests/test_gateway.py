import duckdb
import pytest

import evaluate
from src import sample_data
from src.gateway import Gateway, OperationError

AUG = {"start_date": "2026-08-01", "end_date": "2026-08-31"}


@pytest.fixture
def gw():
    con = duckdb.connect()
    sample_data.build(con)
    return Gateway(con)


def call(gw, op, params, role="assistant"):
    return gw.call(op, params, caller="test", role=role)


def test_retrieve_returns_grouped_metrics(gw):
    result = call(gw, "retrieve_article_metrics", AUG)
    assert result.columns == ["section", "pageviews", "reader_days"]
    assert len(result.rows) == 5


def test_guessed_entity_value_points_to_discovery(gw):
    with pytest.raises(OperationError, match="Call discover_values"):
        call(gw, "retrieve_article_metrics", {**AUG, "author": "Jordan"})


def test_discovery_returns_exact_values(gw):
    result = call(gw, "discover_values", {"entity_type": "author", "search": "jordan"})
    assert [r[0] for r in result.rows] == ["Jordan Lee"]


def test_invented_parameters_are_rejected(gw):
    with pytest.raises(OperationError, match="Unknown parameter"):
        call(gw, "retrieve_article_metrics", {**AUG, "filters": "Author=Jordan Lee"})


def test_group_by_only_accepts_allowed_columns(gw):
    with pytest.raises(OperationError, match="must be one of"):
        call(gw, "retrieve_article_metrics", {**AUG, "group_by": "section; DROP TABLE audit_log"})


def test_values_are_bound_not_interpolated(gw):
    result = call(gw, "discover_values", {"entity_type": "section", "search": "x' OR '1'='1"})
    assert result.rows == []


def test_date_range_limit(gw):
    with pytest.raises(OperationError, match="maximum is 92"):
        call(gw, "retrieve_article_metrics", {"start_date": "2026-07-01", "end_date": "2026-10-15"})


def test_role_permissions(gw):
    with pytest.raises(OperationError, match="may not call"):
        call(gw, "discover_values", {"entity_type": "author", "search": "a"}, role="guest")


def test_every_call_is_audited_including_rejections(gw):
    call(gw, "retrieve_article_metrics", AUG)
    with pytest.raises(OperationError):
        call(gw, "unknown_op", {})
    statuses = gw.con.execute("SELECT status FROM audit_log ORDER BY called_at").fetchall()
    assert [s[0] for s in statuses] == ["ok", "rejected"]


def test_tool_definitions_are_strict_json_schemas(gw):
    tools = {t["name"]: t for t in gw.tool_definitions()}
    schema = tools["retrieve_article_metrics"]["input_schema"]
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["start_date", "end_date"]


def test_all_verified_queries_pass():
    assert all(passed for _, passed in evaluate.run())
