"""Purchase-time features for the late-delivery model.

Prediction moment = the purchase. A feature is allowed only if its value is known
at that moment. Seller history uses only orders DELIVERED before the purchase
(an earlier order still in transit has no known outcome yet).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.db import connect, load_named_sql

TARGET = "is_late"

NUMERIC_FEATURES = [
    "promised_days",
    "purchase_weekday",
    "purchase_hour",
    "is_nov_dec",
    "distance_km",
    "same_state",
    "order_value",
    "freight_value",
    "freight_ratio",
    "n_items",
    "n_sellers",
    "total_weight_g",
    "total_volume_cm3",
    "seller_orders_90d",
    "seller_delivered_90d",
    "seller_late_rate_90d",
    "seller_prior_late_rate",
    "market_late_rate_30d",
    "market_volume_ratio",
]
CATEGORICAL_FEATURES = ["customer_state", "seller_state", "payment_type_main", "primary_category"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Known only after purchase (or the outcome itself): must never be model inputs.
FORBIDDEN_COLUMNS = {
    "is_late",
    "delay_days",
    "delivery_days",
    "delivered_ts",
    "delivered_customer_ts",
    "delivered_carrier_ts",
    "approved_ts",
    "approval_hours",
    "review_score",
    "has_comment",
    "dq_flags",
    "order_status",
}

# Time-based split on purchase date (2016 excluded as too thin; see data-quality report).
TRAIN_END = pd.Timestamp("2018-01-01")  # train: 2017-01-01 .. 2017-12-31
VALID_END = pd.Timestamp("2018-04-01")  # valid: 2018-01-01 .. 2018-03-31; test: 2018-04 .. 2018-08


def haversine_km(lat1, lng1, lat2, lng2) -> np.ndarray:
    """Great-circle distance in km between two sets of coordinates (NaN-safe)."""
    lat1, lng1, lat2, lng2 = (
        np.radians(np.asarray(v, dtype=float)) for v in (lat1, lng1, lat2, lng2)
    )
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def _window_stats(times: np.ndarray, values: np.ndarray, t: np.ndarray, window=None):
    """Count and sum of `values` for events with time in [t - window, t) (window=None: all past).

    `times` must be sorted. side="left" makes the upper bound strict, so an event at the
    exact purchase moment (the order itself) is never counted.
    """
    cum = np.concatenate([[0], np.cumsum(values)])
    hi = np.searchsorted(times, t, side="left")
    lo = 0 if window is None else np.searchsorted(times, t - window, side="left")
    return hi - lo, cum[hi] - cum[lo]


def _rate(late: np.ndarray, n: np.ndarray) -> np.ndarray:
    """late / n, or NaN where n == 0 (no history is 'unknown', not 0%)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(n > 0, late / np.maximum(n, 1), np.nan)


def add_seller_history(orders: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Seller history from strictly earlier events only.

    - seller_orders_90d: seller's orders PURCHASED in the 90 days before this purchase
    - seller_delivered_90d / seller_late_rate_90d: orders DELIVERED in those 90 days, share late
    - seller_prior_late_rate: share late among ALL orders delivered before this purchase
    Rolling windows keep the features stationary (all-time counts grow with platform age).
    An order still in transit at purchase time has no known outcome, so it is not counted.
    """
    out = orders.copy()
    n = len(out)
    names = ["seller_orders_90d", "seller_delivered_90d", "late_90d", "delivered_all", "late_all"]
    cols = {c: np.zeros(n) for c in names}
    positions = out.groupby("seller_key").indices
    w90 = np.timedelta64(90, "D")

    for seller, ev in events.groupby("seller_key"):
        if seller not in positions:
            continue
        idx = positions[seller]
        t = out["purchase_ts"].to_numpy()[idx]
        purchases = np.sort(ev["purchase_ts"].to_numpy())
        deliv = ev.dropna(subset=["delivered_ts"]).sort_values("delivered_ts")
        d_times = deliv["delivered_ts"].to_numpy()
        d_late = deliv["is_late"].astype(int).to_numpy()
        cols["seller_orders_90d"][idx], _ = _window_stats(
            purchases, np.ones(len(purchases)), t, w90
        )
        cols["seller_delivered_90d"][idx], cols["late_90d"][idx] = _window_stats(
            d_times, d_late, t, w90
        )
        cols["delivered_all"][idx], cols["late_all"][idx] = _window_stats(d_times, d_late, t)

    out["seller_orders_90d"] = cols["seller_orders_90d"]
    out["seller_delivered_90d"] = cols["seller_delivered_90d"]
    out["seller_late_rate_90d"] = _rate(cols["late_90d"], cols["seller_delivered_90d"])
    out["seller_prior_late_rate"] = _rate(cols["late_all"], cols["delivered_all"])
    return out


def add_market_context(orders: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Platform-wide signals known at purchase time.

    - market_late_rate_30d: share late among ALL orders delivered in the 30 days before purchase
    - market_volume_ratio: orders purchased in the last 7 days vs the weekly average of the
      last 28 days (a ratio, so it is not inflated by platform growth)
    """
    out = orders.copy()
    ev = events.drop_duplicates("order_id")
    t = out["purchase_ts"].to_numpy()
    deliv = ev.dropna(subset=["delivered_ts"]).sort_values("delivered_ts")
    n30, late30 = _window_stats(
        deliv["delivered_ts"].to_numpy(),
        deliv["is_late"].astype(int).to_numpy(),
        t,
        np.timedelta64(30, "D"),
    )
    out["market_late_rate_30d"] = _rate(late30, n30)
    purchases = np.sort(ev["purchase_ts"].to_numpy())
    ones = np.ones(len(purchases))
    n7, _ = _window_stats(purchases, ones, t, np.timedelta64(7, "D"))
    n28, _ = _window_stats(purchases, ones, t, np.timedelta64(28, "D"))
    out["market_volume_ratio"] = np.where(n28 > 0, n7 / np.maximum(n28 / 4, 1e-9), np.nan)
    return out


def build_features(orders: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Combine ml_orders + ml_seller_events into: order_id, purchase_ts, FEATURES, target."""
    df = add_market_context(add_seller_history(orders, events), events)
    df["purchase_weekday"] = df["purchase_ts"].dt.dayofweek
    df["purchase_hour"] = df["purchase_ts"].dt.hour
    df["is_nov_dec"] = df["purchase_ts"].dt.month.isin([11, 12]).astype(int)
    df["distance_km"] = haversine_km(
        df["customer_lat"], df["customer_lng"], df["seller_lat"], df["seller_lng"]
    )
    df["same_state"] = (df["customer_state"] == df["seller_state"]).astype(int)
    df["order_value"] = df["order_value"].astype(float)
    df["freight_value"] = df["freight_value"].astype(float)
    df["freight_ratio"] = df["freight_value"] / df["order_value"].where(df["order_value"] > 0)
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype("category")
    df[TARGET] = df[TARGET].astype(int)
    return df[["order_id", "purchase_ts", *FEATURES, TARGET]]


def time_split(purchase_ts: pd.Series) -> pd.Series:
    """Label each row train / valid / test by purchase date (no shuffling, no overlap)."""
    return pd.Series(
        np.select(
            [purchase_ts < TRAIN_END, purchase_ts < VALID_END], ["train", "valid"], default="test"
        ),
        index=purchase_ts.index,
    )


def load_model_table(include_open: bool = False) -> pd.DataFrame:
    """Run the feature SQL and return the full model table with a train/valid/test column.

    Default: delivered orders only (the main model's label).
    include_open=True also keeps orders still undelivered after their promised date at the
    data cut-off, labelled late (label sensitivity check); `label_source` says which is which.
    """
    queries = {q.name: q.sql for q in load_named_sql("06_ml_features.sql")}
    with connect(read_only=True) as con:
        orders = con.execute(queries["ml_orders"]).df()
        events = con.execute(queries["ml_seller_events"]).df()
    delivered = orders["is_delivered"].astype(bool)
    if include_open:
        orders["is_late"] = orders["is_late"].astype("boolean").fillna(True)
    else:
        orders = orders[delivered].reset_index(drop=True)
        delivered = delivered[delivered].reset_index(drop=True)
    table = build_features(orders, events)
    table["split"] = time_split(table["purchase_ts"])
    if include_open:
        table["label_source"] = np.where(delivered, "delivered", "open_past_promise")
    return table


def feature_checks(table: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Data checks on the model table before any modelling.

    Returns:
      missing    - % missing per feature and split (only features with any missing value)
      duplicates - duplicate order_ids, and rows identical on every feature + target
      infinite   - count of +/-inf values per numeric feature (should be 0)
      outliers   - training-set skew, 1st/99th percentiles and % of rows beyond 3 x IQR
    """
    missing = table.groupby("split")[FEATURES].apply(lambda d: d.isna().mean() * 100).T
    splits = [c for c in ("train", "valid", "test") if c in missing.columns]
    missing = missing.loc[missing.sum(axis=1) > 0, splits]
    duplicates = pd.DataFrame(
        {
            "check": [
                "duplicate order_id",
                "identical rows (all features + target, different orders)",
            ],
            "rows": [
                int(table["order_id"].duplicated().sum()),
                int(table[[*FEATURES, TARGET]].duplicated().sum()),
            ],
        }
    )
    num = table[NUMERIC_FEATURES].astype(float)
    infinite = pd.DataFrame({"inf_values": np.isinf(num).sum()})
    train = num[table["split"] == "train"]
    q1, q3 = train.quantile(0.25), train.quantile(0.75)
    iqr = q3 - q1
    outliers = pd.DataFrame(
        {
            "skew": train.skew(),
            "p01": train.quantile(0.01),
            "median": train.median(),
            "p99": train.quantile(0.99),
            "max": train.max(),
            "pct_beyond_3iqr": ((train > q3 + 3 * iqr) | (train < q1 - 3 * iqr)).mean() * 100,
        }
    ).sort_values("skew", ascending=False)
    return {
        "missing": missing,
        "duplicates": duplicates,
        "infinite": infinite,
        "outliers": outliers,
    }
