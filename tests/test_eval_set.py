"""Tests for the text-to-SQL evaluation set (genai/eval/text_to_sql_eval.yaml)."""

import json
import re

import pytest
import sqlglot
from sqlglot import exp

from genai.text_to_sql.eval_set import (
    ALLOWED_TABLES,
    DIFFICULTIES,
    EXPECTED_PATH,
    load_eval_set,
    run_query,
    tables_used,
)
from src.db import DB_PATH, connect

ITEMS = load_eval_set()
HAVE_DB = DB_PATH.exists()


def test_at_least_40_items_across_all_difficulties():
    assert len(ITEMS) >= 40
    for difficulty in DIFFICULTIES:
        assert sum(i.difficulty == difficulty for i in ITEMS) >= 10


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.id)
def test_gold_sql_is_a_single_select_on_allowed_tables(item):
    statements = sqlglot.parse(item.gold_sql, read="duckdb")
    assert len(statements) == 1
    assert isinstance(statements[0], (exp.Select, exp.Union))
    assert tables_used(item.gold_sql) <= ALLOWED_TABLES


def test_tables_used_ignores_cte_names():
    sql = "WITH t AS (SELECT * FROM fact_orders) SELECT * FROM t JOIN dim_date ON TRUE"
    assert tables_used(sql) == {"fact_orders", "dim_date"}


@pytest.mark.skipif(not HAVE_DB, reason="database not built")
def test_expected_results_match_the_gold_sql():
    """The stored expected results are in sync with the gold SQL and the current database."""
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    assert set(expected) == {i.id for i in ITEMS}
    with connect(read_only=True) as con:
        for item in ITEMS:
            result = run_query(con, item.gold_sql)
            assert result["rows"], f"{item.id} returned no rows"
            assert result == expected[item.id], f"{item.id} differs from the expected file"


@pytest.mark.skipif(not HAVE_DB, reason="database not built")
def test_rankings_have_no_tie_at_the_cut_off():
    """A 'top k' question is fair only if rows k and k+1 differ (else the answer is arbitrary)."""
    with connect(read_only=True) as con:
        for item in ITEMS:
            m = re.search(r"LIMIT (\d+)\s*$", item.gold_sql)
            if not m:
                continue
            k = int(m.group(1))
            rows = con.execute(item.gold_sql[: m.start()]).fetchall()
            if len(rows) > k:
                assert rows[k - 1][-1] != rows[k][-1], f"{item.id}: tie at position {k}"
