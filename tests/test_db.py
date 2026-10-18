"""Tests for named-SQL parsing and the data-quality check file (no database needed)."""

from src.db import load_named_sql, parse_named_sql

SAMPLE = """-- header comment
-- name: first_check
-- table: orders
-- issue: Something odd
-- decision: FLAG
-- action: Labelled.
SELECT 1 AS affected, 2 AS base;

-- name: second_query
SELECT 42;
"""


def test_parse_splits_on_name_markers():
    queries = parse_named_sql(SAMPLE)
    assert [q.name for q in queries] == ["first_check", "second_query"]
    assert queries[1].sql == "SELECT 42;"


def test_parse_reads_metadata_lines():
    first = parse_named_sql(SAMPLE)[0]
    assert first.meta == {
        "table": "orders",
        "issue": "Something odd",
        "decision": "FLAG",
        "action": "Labelled.",
    }
    assert parse_named_sql(SAMPLE)[1].meta == {}


def test_every_quality_check_is_documented():
    checks = load_named_sql("04_data_quality_checks.sql")
    assert len(checks) >= 40
    names = [c.name for c in checks]
    assert len(names) == len(set(names)), "duplicate check names"
    for check in checks:
        assert {"table", "issue", "decision", "action"} <= check.meta.keys(), check.name
        assert check.meta["decision"] in {"FIX", "FLAG", "KEEP", "SCOPE"}, check.name


def test_business_queries_have_insights():
    for query in load_named_sql("03_business_queries.sql"):
        assert "-- INSIGHT:" in query.sql and "INSIGHT: TBD" not in query.sql, query.name
