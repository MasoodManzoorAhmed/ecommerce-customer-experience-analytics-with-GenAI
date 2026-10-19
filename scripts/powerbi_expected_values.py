"""Compute the numbers the Power BI report must show, from the exported Parquet files.

Each value uses the same logic as the matching DAX measure in powerbi/measures.dax,
so any mismatch in Power BI points to a modelling or DAX mistake (reconciliation).
Output: powerbi/expected_values.csv

    python scripts/export_powerbi.py
    python scripts/powerbi_expected_values.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PQ = ROOT / "data" / "powerbi"
OUT = ROOT / "powerbi" / "expected_values.csv"

# (check, visual / filter context, DAX measure, SQL over the Parquet views)
CHECKS = [
    (
        "Delivered Orders",
        "card, no filters",
        "[Delivered Orders]",
        "SELECT COUNT(*) FROM fo WHERE is_delivered",
    ),
    (
        "Revenue",
        "card, no filters",
        "[Revenue]",
        "SELECT SUM(i.price) FROM fi i JOIN fo USING (order_id) WHERE fo.is_delivered",
    ),
    (
        "AOV",
        "card, no filters",
        "[AOV]",
        "SELECT SUM(i.price) / COUNT(DISTINCT order_id) FROM fi i JOIN fo USING (order_id) "
        "WHERE fo.is_delivered",
    ),
    (
        "Late Orders",
        "card, no filters",
        "[Late Orders]",
        "SELECT COUNT(*) FROM fo WHERE is_delivered AND is_late",
    ),
    (
        "On-time %",
        "card, no filters",
        "[On-time %]",
        "SELECT 1 - AVG(is_late::INT) FROM fo WHERE is_delivered",
    ),
    (
        "Avg Review",
        "card, no filters",
        "[Avg Review]",
        "SELECT AVG(review_score) FROM fo WHERE is_delivered",
    ),
    (
        "Avg Delivery Days",
        "card, no filters",
        "[Avg Delivery Days]",
        "SELECT AVG(delivery_days) FROM fo WHERE is_delivered",
    ),
    (
        "Review Gap (on-time - late)",
        "card, no filters",
        "[Review Gap]",
        "SELECT AVG(review_score) FILTER (WHERE NOT is_late) - AVG(review_score) FILTER (WHERE is_late) "
        "FROM fo WHERE is_delivered",
    ),
    (
        "Revenue 2018-08",
        "year_month = 2018-08",
        "[Revenue]",
        "SELECT SUM(i.price) FROM fi i JOIN fo USING (order_id) JOIN dd ON dd.date_key = fo.purchase_date_key "
        "WHERE fo.is_delivered AND dd.year_month = '2018-08'",
    ),
    (
        "Revenue MoM % 2018-08",
        "year_month = 2018-08",
        "[Revenue MoM %]",
        "WITH m AS (SELECT dd.year_month ym, SUM(i.price) rev FROM fi i JOIN fo USING (order_id) "
        "JOIN dd ON dd.date_key = fo.purchase_date_key WHERE fo.is_delivered GROUP BY 1) "
        "SELECT (SELECT rev FROM m WHERE ym='2018-08') / (SELECT rev FROM m WHERE ym='2018-07') - 1",
    ),
    (
        "Revenue YoY % 2018-08",
        "year_month = 2018-08",
        "[Revenue YoY %]",
        "WITH m AS (SELECT dd.year_month ym, SUM(i.price) rev FROM fi i JOIN fo USING (order_id) "
        "JOIN dd ON dd.date_key = fo.purchase_date_key WHERE fo.is_delivered GROUP BY 1) "
        "SELECT (SELECT rev FROM m WHERE ym='2018-08') / (SELECT rev FROM m WHERE ym='2017-08') - 1",
    ),
    (
        "Revenue % of Total: SP customers",
        "bar by customer state, row SP",
        "[Revenue % of Total]",
        "SELECT SUM(i.price) FILTER (WHERE c.state = 'SP') / SUM(i.price) FROM fi i JOIN fo USING (order_id) "
        "JOIN dc c ON c.customer_key = fo.customer_key WHERE fo.is_delivered",
    ),
    (
        "On-time %: MA customers",
        "bar by customer state, row MA",
        "[On-time %]",
        "SELECT 1 - AVG(fo.is_late::INT) FROM fo JOIN dc c ON c.customer_key = fo.customer_key "
        "WHERE fo.is_delivered AND c.state = 'MA'",
    ),
    (
        "Revenue: health_beauty",
        "table by category, row health_beauty",
        "[Revenue]",
        "SELECT SUM(i.price) FROM fi i JOIN fo USING (order_id) JOIN dp p ON p.product_key = i.product_key "
        "WHERE fo.is_delivered AND p.category_en = 'health_beauty'",
    ),
    (
        "Category Cumulative %: 7th category",
        "Pareto by category, 7th row (housewares)",
        "[Category Cumulative %]",
        "WITH c AS (SELECT p.category_en, SUM(i.price) rev FROM fi i JOIN fo USING (order_id) "
        "JOIN dp p ON p.product_key = i.product_key WHERE fo.is_delivered GROUP BY 1) "
        "SELECT SUM(rev) FILTER (WHERE rk <= 7) / SUM(rev) FROM "
        "(SELECT rev, ROW_NUMBER() OVER (ORDER BY rev DESC) rk FROM c)",
    ),
    (
        "Category On-time %: office_furniture",
        "table by category, row office_furniture",
        "[Category On-time %]",
        "SELECT 1 - COUNT(DISTINCT order_id) FILTER (WHERE fo.is_late) / COUNT(DISTINCT order_id) "
        "FROM fi i JOIN fo USING (order_id) JOIN dp p ON p.product_key = i.product_key "
        "WHERE fo.is_delivered AND p.category_en = 'office_furniture'",
    ),
    (
        "Seller Revenue Rank 1: revenue",
        "table by seller_id, rank 1 row",
        "[Revenue]",
        "SELECT MAX(rev) FROM (SELECT i.seller_key, SUM(i.price) rev FROM fi i JOIN fo USING (order_id) "
        "WHERE fo.is_delivered GROUP BY 1)",
    ),
    (
        "Avg Late Risk (test orders)",
        "card, no filters",
        "[Avg Late Risk (test)]",
        "SELECT AVG(late_probability) FROM fo WHERE model_split = 'test'",
    ),
    (
        "Actual Late Rate (test orders)",
        "card, no filters",
        "[Late Rate (test)]",
        "SELECT AVG(is_late::INT) FROM fo WHERE model_split = 'test'",
    ),
    (
        "On-time %: test orders, risk_band = high",
        "bar by risk_band (filter model_split = test), row high",
        "[On-time %]",
        "SELECT 1 - AVG(is_late::INT) FROM fo WHERE model_split = 'test' AND risk_band = 'high'",
    ),
    (
        "On-time %: test orders, risk_band = low",
        "bar by risk_band (filter model_split = test), row low",
        "[On-time %]",
        "SELECT 1 - AVG(is_late::INT) FROM fo WHERE model_split = 'test' AND risk_band = 'low'",
    ),
    (
        "Avg Review (via items): health_beauty",
        "table by category, row health_beauty",
        "[Avg Review (via items)]",
        "SELECT AVG(review_score) FROM fo WHERE is_delivered AND order_id IN (SELECT i.order_id FROM fi i JOIN dp p ON p.product_key = i.product_key WHERE p.category_en = 'health_beauty')",
    ),
]


def _fmt(check: str, measure: str, value: float) -> str:
    """Human-readable value, formatted the way the Power BI visual should show it."""
    if "%" in check or "%" in measure or "Rate" in measure or "Risk" in measure:
        return f"{value:.2%}"
    if "Revenue" in check or "AOV" in check:
        return f"R$ {value:,.2f}"
    if "Orders" in check:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def main() -> int:
    con = duckdb.connect()
    for alias, name in [
        ("fo", "fact_orders"),
        ("fi", "fact_order_items"),
        ("dd", "dim_date"),
        ("dc", "dim_customer"),
        ("dp", "dim_product"),
        ("ds", "dim_seller"),
    ]:
        con.execute(
            f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{(PQ / name).as_posix()}.parquet')"
        )
    rows = [
        {
            "check": check,
            "where_to_look": where,
            "dax_measure": measure,
            "expected_value": float(con.execute(sql).fetchone()[0]),
        }
        for check, where, measure, sql in CHECKS
    ]
    df = pd.DataFrame(rows)
    df["display"] = [_fmt(r.check, r.dax_measure, r.expected_value) for r in df.itertuples()]
    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False)
    pd.set_option("display.width", 200)
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
