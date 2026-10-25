"""Export the star schema (plus model scores) to Parquet files for Power BI.

Each named query in sql/07_powerbi_export.sql becomes data/powerbi/<name>.parquet.
Parquet keeps column types (dates, decimals, booleans), unlike CSV.

    python scripts/build_db.py          # first, if the database isn't built
    python scripts/export_powerbi.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # make the src package importable when run as a script

from src.db import connect, load_named_sql  # noqa: E402

OUT_DIR = ROOT / "data" / "powerbi"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with connect(read_only=True) as con:
        for query in load_named_sql("07_powerbi_export.sql"):
            path = OUT_DIR / f"{query.name}.parquet"
            con.execute(f"COPY ({query.sql.rstrip(';')}) TO '{path.as_posix()}' (FORMAT parquet)")
            rows = con.execute(
                f"SELECT COUNT(*) FROM read_parquet('{path.as_posix()}')"
            ).fetchone()[0]
            print(f"  {path.name:28s} {rows:>9,} rows  {path.stat().st_size / 1e6:6.2f} MB")
        # GenAI Module 2 output: only present after `python -m genai.review_themes.apply cascade`
        tables = {
            t for (t,) in con.execute("SELECT table_name FROM information_schema.tables").fetchall()
        }
        if "fact_review_theme" in tables:
            path = OUT_DIR / "fact_review_theme.parquet"
            con.execute(
                "COPY (SELECT review_id, order_id, theme, source FROM fact_review_theme) "
                f"TO '{path.as_posix()}' (FORMAT parquet)"
            )
            print(f"  {path.name:28s} (review themes, Module 2)")
    print(f"Done. Point Power BI at: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
