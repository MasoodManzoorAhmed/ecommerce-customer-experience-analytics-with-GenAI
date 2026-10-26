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


# ---------------------------------------------------------------- review themes (GenAI Module 2)
THEME_LABELS = {
    "never_arrived": "Never arrived",
    "late_delivery": "Late delivery",
    "wrong_or_missing_item": "Wrong or missing item",
    "damaged": "Damaged / defective",
    "product_quality": "Product quality",
    "other": "Other (service, vague)",
}
DELIVERY_THEMES = ("never_arrived", "late_delivery")
PRODUCT_THEMES = ("wrong_or_missing_item", "damaged", "product_quality")
SITUATION_ORDER = ["on time", "late", "not delivered"]
THEME_RESULTS = ROOT / "genai" / "review_themes" / "results"


def load_themes() -> pd.DataFrame:
    """One row per review (a few reviews cover several orders with the same text)."""
    df = load("review_themes").drop_duplicates("review_id")
    df["year"] = df["year_month"].str[:4].astype(int)
    return df


def theme_shares(df: pd.DataFrame) -> pd.DataFrame:
    """Reviews and share per theme, largest first."""
    out = df["theme"].value_counts().rename_axis("theme").reset_index(name="reviews")
    out["share"] = out["reviews"] / out["reviews"].sum()
    out["label"] = out["theme"].map(THEME_LABELS)
    return out


def theme_by_situation(df: pd.DataFrame) -> pd.DataFrame:
    """Theme mix (row shares) within each delivery situation."""
    mix = pd.crosstab(df["situation"], df["theme"], normalize="index")
    return mix.reindex([s for s in SITUATION_ORDER if s in mix.index]).fillna(0.0)


def approach_comparison() -> pd.DataFrame:
    """Gold-set scores of the three approaches with their speed (from the logged stats)."""
    path = THEME_RESULTS / "approach_comparison.csv"
    if not path.exists():
        return pd.DataFrame()
    table = pd.read_csv(path)[["approach", "macro_f1", "accuracy"]]
    stats = {
        "zero-shot LLM": "llm_stats_gold.json",
        "TF-IDF + logistic regression": "tfidf_stats.json",
        "LoRA fine-tuned transformer": "lora_stats.json",
    }
    table["seconds_per_review"] = [
        json.loads((THEME_RESULTS / stats[a]).read_text())["seconds_per_review"]
        if (THEME_RESULTS / stats.get(a, "_")).exists()
        else None
        for a in table["approach"]
    ]
    return table
