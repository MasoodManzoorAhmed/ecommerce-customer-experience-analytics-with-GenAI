"""Export the small data extracts the Streamlit app reads (app/data/*.parquet, committed).

- kpi_month_state.parquet   month x state counts and sums (excel_monthly_state, sql/08)
- delay_reviews.parquet     reviews by month x state x delivery-delay bucket (sql/09)
- risk_test_orders.parquet  model features + actual outcome for test-period orders, so the
                            risk page can score and explain real orders without the database

    python scripts/export_app_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # make the src package importable when run as a script

from src.db import connect, load_named_sql  # noqa: E402
from src.features import load_model_table  # noqa: E402

OUT_DIR = ROOT / "app" / "data"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    queries = {q.name: q.sql for q in load_named_sql("08_excel_report.sql")}
    queries |= {q.name: q.sql for q in load_named_sql("09_app_data.sql")}
    with connect(read_only=True) as con:
        frames = {
            "kpi_month_state": con.execute(queries["excel_monthly_state"]).df(),
            "delay_reviews": con.execute(queries["app_delay_reviews"]).df(),
        }
    table = load_model_table()
    frames["risk_test_orders"] = table[table["split"] == "test"].drop(columns="split")
    for name, df in frames.items():
        path = OUT_DIR / f"{name}.parquet"
        df.to_parquet(path, index=False)
        print(f"  {path.name:26s} {len(df):>7,} rows  {path.stat().st_size / 1e6:5.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
