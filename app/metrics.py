"""Data access and KPI logic for the app (no Streamlit widgets here, so it is unit-testable).

The extracts in app/data/ hold additive counts and sums; every ratio is rebuilt as
sum / sum after filtering, exactly like the semantic layer, Power BI and the Excel report.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"
TREND_WINDOW = ("2017-01", "2018-08")  # months with enough orders for a monthly trend
DELAY_ORDER = [
    "10+ days early",
    "0-9 days early",
    "1-3 days late",
    "4-7 days late",
    "8-14 days late",
    "15+ days late",
]


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet")


def apply_filters(df: pd.DataFrame, year: int | None, state: str | None) -> pd.DataFrame:
    if year is not None:
        df = df[df["year"] == year]
    if state is not None:
        df = df[df["customer_state"] == state]
    return df


def kpis(ms: pd.DataFrame) -> dict[str, float]:
    """Headline KPIs from the month x state extract (ratios rebuilt from sums)."""
    s = ms.sum(numeric_only=True)
    delivered = s["delivered_orders"]
    return {
        "revenue": s["revenue"],
        "delivered_orders": delivered,
        "aov": s["revenue"] / delivered if delivered else float("nan"),
        "on_time_rate": 1 - s["late_orders"] / delivered if delivered else float("nan"),
        "avg_review": s["review_sum"] / s["reviews"] if s["reviews"] else float("nan"),
        "review_on_time": s["review_sum_on_time"] / s["reviews_on_time"]
        if s["reviews_on_time"]
        else float("nan"),
        "review_late": s["review_sum_late"] / s["reviews_late"]
        if s["reviews_late"]
        else float("nan"),
        "avg_delivery_days": s["delivery_days_sum"] / s["delivery_days_n"]
        if s["delivery_days_n"]
        else float("nan"),
    }


def monthly(ms: pd.DataFrame, full_window: bool) -> pd.DataFrame:
    """Revenue, late rate and average review per purchase month."""
    g = ms.groupby("year_month", as_index=False).sum(numeric_only=True)
    if full_window:
        g = g[g["year_month"].between(*TREND_WINDOW)]
    g["late_rate"] = g["late_orders"] / g["delivered_orders"]
    g["avg_review"] = g["review_sum"] / g["reviews"]
    return g


def states(ms: pd.DataFrame, min_orders: int = 500) -> pd.DataFrame:
    """On-time rate and review per customer state with at least `min_orders` delivered orders."""
    g = ms.groupby("customer_state", as_index=False).sum(numeric_only=True)
    g = g[g["delivered_orders"] >= min_orders].copy()
    g["on_time_rate"] = 1 - g["late_orders"] / g["delivered_orders"]
    g["avg_review"] = g["review_sum"] / g["reviews"]
    return g.sort_values("on_time_rate")


def delay_reviews(dr: pd.DataFrame) -> pd.DataFrame:
    """Average review and 1-2 star share per delivery-delay bucket, in delay order."""
    g = dr.groupby("delay_bucket", as_index=False).sum(numeric_only=True)
    g["avg_review"] = g["review_sum"] / g["reviews"]
    g["low_share"] = g["low_ratings"] / g["reviews"]
    g["late"] = g["delay_bucket"].str.contains("late")
    g["order"] = g["delay_bucket"].map(DELAY_ORDER.index)
    return g.sort_values("order")


def model_metadata() -> dict:
    return json.loads((ROOT / "models" / "metadata.json").read_text(encoding="utf-8"))


def risk_band(p: float, threshold: float) -> str:
    """Same bands as fact_order_risk: high at/above the cost-based threshold, medium at half."""
    if p >= threshold:
        return "high"
    return "medium" if p >= threshold / 2 else "low"


FEATURE_LABELS = {
    "promised_days": "Promised delivery days",
    "purchase_weekday": "Weekday of purchase",
    "purchase_hour": "Hour of purchase",
    "is_nov_dec": "November/December order",
    "distance_km": "Seller-customer distance",
    "same_state": "Seller in customer's state",
    "order_value": "Order value",
    "freight_value": "Freight cost",
    "freight_ratio": "Freight / order value",
    "n_items": "Number of items",
    "n_sellers": "Number of sellers",
    "total_weight_g": "Total weight",
    "total_volume_cm3": "Total volume",
    "seller_orders_90d": "Seller orders, last 90 days",
    "seller_delivered_90d": "Seller deliveries, last 90 days",
    "seller_late_rate_90d": "Seller late rate, last 90 days",
    "seller_prior_late_rate": "Seller late rate, all history",
    "market_late_rate_30d": "Platform late rate, last 30 days",
    "market_volume_ratio": "Platform order volume (7d vs 28d)",
    "customer_state": "Customer state",
    "seller_state": "Seller state",
    "payment_type_main": "Payment method",
    "primary_category": "Product category",
}
