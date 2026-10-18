"""Run every named query in sql/03_business_queries.sql and save each result.

Queries are separated by "-- name: <query_name>" markers. Results are printed
and written to sql/results/<query_name>.csv (small aggregates, committed as evidence).
The database is opened read-only, so analysis can never modify the data.

    python scripts/run_queries.py              # run all
    python scripts/run_queries.py q07 q08      # run queries whose name starts with these
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "olist.duckdb"
SQL_FILE = ROOT / "sql" / "03_business_queries.sql"
OUT_DIR = ROOT / "sql" / "results"

NAME_MARKER = re.compile(r"^-- name:\s*(\S+)\s*$", re.MULTILINE)


def parse_queries(sql_text: str) -> dict[str, str]:
    """Split the SQL file into {query_name: sql} using the name markers."""
    parts = NAME_MARKER.split(sql_text)
    # parts = [header, name1, body1, name2, body2, ...]
    return {name: body.strip() for name, body in zip(parts[1::2], parts[2::2], strict=True)}


def main(prefixes: list[str]) -> int:
    queries = parse_queries(SQL_FILE.read_text(encoding="utf-8"))
    if prefixes:
        queries = {n: q for n, q in queries.items() if n.startswith(tuple(prefixes))}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        for name, sql in queries.items():
            df = con.execute(sql).df()
            df.to_csv(OUT_DIR / f"{name}.csv", index=False)
            print(f"\n=== {name}  ({len(df)} rows)")
            print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
