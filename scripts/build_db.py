"""Build data/olist.duckdb from the raw Olist CSVs.

Step 1 loads each CSV unchanged into the `raw` schema (raw.orders, raw.order_items, ...).
Step 2 runs the numbered SQL build files (staging, star schema) if they exist.
The build is idempotent: the database file is recreated from scratch every run.

    python scripts/build_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "olist.duckdb"
SQL_DIR = ROOT / "sql"

# CSV file -> table name in the raw schema
RAW_TABLES = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_orders_dataset.csv": "orders",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "category_translation",
}

# SQL files that build tables, run in order (business queries are run separately)
BUILD_SQL = ["01_staging.sql", "02_star_schema.sql"]


def load_raw(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Load every CSV into raw.<table> and return the row count per table."""
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    counts = {}
    for csv_name, table in RAW_TABLES.items():
        path = RAW_DIR / csv_name
        if not path.exists():
            raise FileNotFoundError(f"{path} not found; run scripts/download_data.py first")
        # Raw layer keeps every column as text so nothing is silently cast or lost;
        # types are set explicitly in sql/01_staging.sql.
        con.execute(
            f"CREATE TABLE raw.{table} AS "
            "SELECT * FROM read_csv(?, header = true, all_varchar = true)",
            [path.as_posix()],
        )
        counts[table] = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
    return counts


def run_sql_files(con: duckdb.DuckDBPyConnection) -> None:
    """Execute the numbered build SQL files that exist."""
    for name in BUILD_SQL:
        path = SQL_DIR / name
        if not path.exists():
            print(f"  (skipped {name}: not written yet)")
            continue
        con.execute(path.read_text(encoding="utf-8"))
        print(f"  ran {name}")


def main() -> int:
    DB_PATH.unlink(missing_ok=True)
    with duckdb.connect(str(DB_PATH)) as con:
        print(f"Loading raw CSVs into {DB_PATH.name}")
        for table, n in load_raw(con).items():
            print(f"  raw.{table:22s} {n:>9,} rows")
        print("Running SQL build files")
        run_sql_files(con)
    return 0


if __name__ == "__main__":
    sys.exit(main())
