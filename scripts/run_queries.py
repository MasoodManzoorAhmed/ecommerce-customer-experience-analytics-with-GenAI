"""Run every named query in sql/04_business_queries.sql and save each result.

Queries are separated by "-- name: <query_name>" markers. Results are printed
and written to sql/results/<query_name>.csv (small aggregates, committed as evidence).
The database is opened read-only, so analysis can never modify the data.

    python scripts/run_queries.py              # run all
    python scripts/run_queries.py q07 q08      # run queries whose name starts with these
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # make the src package importable when run as a script

from src.db import connect, load_named_sql  # noqa: E402

OUT_DIR = ROOT / "sql" / "results"


def main(prefixes: list[str]) -> int:
    queries = {q.name: q.sql for q in load_named_sql("04_business_queries.sql")}
    if prefixes:
        queries = {n: q for n, q in queries.items() if n.startswith(tuple(prefixes))}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    with connect(read_only=True) as con:
        for name, sql in queries.items():
            df = con.execute(sql).df()
            df.to_csv(OUT_DIR / f"{name}.csv", index=False)
            print(f"\n=== {name}  ({len(df)} rows)")
            print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
