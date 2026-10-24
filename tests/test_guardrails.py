"""Guardrails for LLM-written SQL: only safe, read-only queries on allowed tables get through."""

import pytest

from genai.text_to_sql.guardrails import GuardrailError, check_sql, extract_sql


def test_select_on_allowed_table_passes_and_gets_a_limit():
    sql = check_sql("SELECT COUNT(*) FROM fact_orders")
    assert "LIMIT 1000" in sql


def test_existing_limit_is_kept():
    assert check_sql("SELECT * FROM dim_seller LIMIT 5").endswith("LIMIT 5")


def test_cte_names_are_not_treated_as_tables():
    check_sql("WITH t AS (SELECT * FROM fact_orders) SELECT COUNT(*) FROM t")


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE fact_orders",
        "DELETE FROM fact_orders",
        "UPDATE fact_orders SET order_value = 0",
        "INSERT INTO dim_seller VALUES (1)",
        "CREATE TABLE x AS SELECT 1",
        "SELECT 1; DROP TABLE fact_orders",
    ],
)
def test_writes_and_multiple_statements_are_rejected(sql):
    with pytest.raises(GuardrailError):
        check_sql(sql)


@pytest.mark.parametrize("table", ["stg_orders", "raw.orders", "information_schema.tables"])
def test_tables_outside_the_star_schema_are_rejected(table):
    with pytest.raises(GuardrailError, match="not allowed"):
        check_sql(f"SELECT * FROM {table}")


def test_unparseable_sql_is_rejected():
    with pytest.raises(GuardrailError):
        check_sql("SELEC count FROM")


def test_extract_sql_from_fenced_reply():
    reply = "Here you go:\n```sql\nSELECT 1 AS x;\n```\nThis counts rows."
    assert extract_sql(reply) == "SELECT 1 AS x"


def test_extract_sql_from_plain_reply_with_chatter():
    assert (
        extract_sql("Sure! SELECT COUNT(*) FROM fact_orders;") == "SELECT COUNT(*) FROM fact_orders"
    )
