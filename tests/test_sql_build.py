"""Fresh-build test: rebuild the database from the raw CSVs in a temporary file, then run
every SQL file in order. This is the PRD acceptance check "queries run cleanly from a fresh
database build". Skipped when the raw data isn't present (e.g. in CI without the dataset).
"""

import importlib.util

import duckdb
import pytest

from src.db import RAW_DIR, RAW_TABLES, ROOT, load_named_sql

HAVE_RAW = all((RAW_DIR / name).exists() for name in RAW_TABLES)
pytestmark = pytest.mark.skipif(not HAVE_RAW, reason="raw CSVs not downloaded")

# Named-query files run after the build, in file order (each reads only earlier layers)
QUERY_FILES = [
    "03_data_quality_checks.sql",
    "04_business_queries.sql",
    "05_eda_queries.sql",
    "06_ml_features.sql",
]


def _load_build_script():
    spec = importlib.util.spec_from_file_location("build_db", ROOT / "scripts" / "build_db.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fresh_db(tmp_path_factory):
    """A brand-new database built from the raw CSVs (the real data/olist.duckdb is untouched)."""
    build = _load_build_script()
    con = duckdb.connect(str(tmp_path_factory.mktemp("db") / "fresh.duckdb"))
    build.load_raw(con)
    build.run_sql_files(con)
    yield con
    con.close()


def test_build_creates_star_schema(fresh_db):
    tables = {r[0] for r in fresh_db.execute("SHOW TABLES").fetchall()}
    for name in ["fact_orders", "fact_order_items", "dim_customer", "dim_seller", "dim_product"]:
        assert name in tables
    assert fresh_db.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0] == 99_441


@pytest.mark.parametrize("filename", QUERY_FILES)
def test_every_named_query_runs(fresh_db, filename):
    queries = load_named_sql(filename)
    assert queries, f"no named queries found in {filename}"
    for query in queries:
        rows = fresh_db.execute(query.sql).fetchall()
        assert rows, f"{filename}:{query.name} returned no rows"
