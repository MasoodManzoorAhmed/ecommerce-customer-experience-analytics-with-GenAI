"""Step a (column descriptions) must cover the real schema exactly, and every prompt must build."""

import pytest

from genai.text_to_sql.eval_set import ALLOWED_TABLES
from genai.text_to_sql.pipeline import CONFIGS, build_messages, load_descriptions, schema_for
from src.db import DB_PATH, connect

DESCRIPTIONS = load_descriptions()
needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="database not built")


def test_every_allowed_table_is_described():
    assert set(DESCRIPTIONS) == set(ALLOWED_TABLES)
    for table, info in DESCRIPTIONS.items():
        assert info["description"].strip(), table


@needs_db
@pytest.mark.parametrize("table", sorted(ALLOWED_TABLES))
def test_descriptions_match_the_database_columns(table):
    with connect(read_only=True) as con:
        columns = {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}
    described = set(DESCRIPTIONS[table]["columns"])
    assert columns - described == set(), "columns without a description"
    assert described - columns == set(), "descriptions of columns that don't exist"


@needs_db
def test_described_schema_lists_stored_values_of_short_text_columns():
    text = schema_for(CONFIGS["a"])
    assert "'credit_card'" in text and "'delivered'" in text and "'RJ'" in text
    assert "customer_unique_id VARCHAR" in text and "Values: '0" not in text  # long ids not listed


@needs_db
@pytest.mark.parametrize("name", list(CONFIGS))
def test_every_configuration_builds_a_prompt(name):
    config = CONFIGS[name]
    system = build_messages("How many orders?", config, schema_for(config))[0]["content"]
    assert ("TABLE fact_orders" in system) == config.descriptions
    assert ("Business definitions" in system) == config.semantic_layer
