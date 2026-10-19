"""Leakage and correctness tests for src/features.py (synthetic data, no database)."""

import numpy as np
import pandas as pd

from src.features import (
    FEATURES,
    FORBIDDEN_COLUMNS,
    add_market_context,
    add_seller_history,
    feature_checks,
    haversine_km,
    time_split,
)

ts = pd.Timestamp


def test_no_forbidden_columns_in_features():
    assert not set(FEATURES) & FORBIDDEN_COLUMNS


def test_seller_history_uses_only_orders_delivered_before_purchase():
    events = pd.DataFrame(
        {
            "seller_key": [1, 1, 1, 1],
            "order_id": ["a", "b", "c", "d"],
            "purchase_ts": [ts("2017-01-01"), ts("2017-01-05"), ts("2017-01-10"), ts("2017-02-01")],
            # a delivered late on Jan 8; b delivered on time Jan 20 (still in transit on Jan 10)
            "delivered_ts": [ts("2017-01-08"), ts("2017-01-20"), ts("2017-01-25"), pd.NaT],
            "is_late": [True, False, False, None],
        }
    )
    orders = events[["seller_key", "order_id", "purchase_ts"]].copy()
    out = add_seller_history(orders, events).set_index("order_id")

    # order c (Jan 10): a and b were purchased before; only a was DELIVERED before (late)
    assert out.loc["c", "seller_orders_90d"] == 2
    assert out.loc["c", "seller_delivered_90d"] == 1
    assert out.loc["c", "seller_prior_late_rate"] == 1.0
    # order d (Feb 1): a, b, c all delivered before; 1 of 3 late
    assert out.loc["d", "seller_delivered_90d"] == 3
    assert np.isclose(out.loc["d", "seller_prior_late_rate"], 1 / 3)
    # first order has no history; its own outcome is never used
    assert out.loc["a", "seller_orders_90d"] == 0
    assert np.isnan(out.loc["a", "seller_prior_late_rate"])


def test_rolling_window_drops_old_events():
    events = pd.DataFrame(
        {
            "seller_key": [1, 1],
            "order_id": ["old", "new"],
            "purchase_ts": [ts("2017-01-01"), ts("2017-06-01")],
            "delivered_ts": [ts("2017-01-10"), pd.NaT],
            "is_late": [True, None],
        }
    )
    orders = events[["seller_key", "order_id", "purchase_ts"]].copy()
    out = add_seller_history(orders, events).set_index("order_id")
    # "old" was delivered ~142 days before "new": outside the 90-day window, inside all-time
    assert out.loc["new", "seller_delivered_90d"] == 0
    assert np.isnan(out.loc["new", "seller_late_rate_90d"])
    assert out.loc["new", "seller_prior_late_rate"] == 1.0


def test_market_late_rate_uses_only_past_deliveries():
    events = pd.DataFrame(
        {
            "seller_key": [1, 2, 3],
            "order_id": ["a", "b", "c"],
            "purchase_ts": [ts("2017-01-01"), ts("2017-01-02"), ts("2017-01-20")],
            "delivered_ts": [ts("2017-01-10"), ts("2017-01-25"), ts("2017-01-30")],
            "is_late": [True, True, False],
        }
    )
    orders = events[["seller_key", "order_id", "purchase_ts"]].copy()
    out = add_market_context(orders, events).set_index("order_id")
    # at c's purchase (Jan 20) only a (late) has been delivered; b arrives on Jan 25
    assert out.loc["c", "market_late_rate_30d"] == 1.0


def test_future_outcomes_do_not_change_past_features():
    events = pd.DataFrame(
        {
            "seller_key": [1, 1],
            "order_id": ["a", "b"],
            "purchase_ts": [ts("2017-01-01"), ts("2017-03-01")],
            "delivered_ts": [ts("2017-01-10"), ts("2017-03-10")],
            "is_late": [False, False],
        }
    )
    orders = events[["seller_key", "order_id", "purchase_ts"]].copy()
    before = add_seller_history(orders, events)
    events.loc[1, "is_late"] = True  # change the LATER order's outcome
    after = add_seller_history(orders, events)
    assert before.loc[0].equals(after.loc[0])


def test_haversine_known_distance():
    # Sao Paulo -> Rio de Janeiro is roughly 360 km
    d = haversine_km([-23.55], [-46.63], [-22.91], [-43.17])[0]
    assert 340 < d < 380


def test_time_split_is_ordered_and_disjoint():
    dates = pd.Series(
        pd.to_datetime(["2017-06-01", "2017-12-31", "2018-01-01", "2018-03-31", "2018-04-01"])
    )
    assert time_split(dates).tolist() == ["train", "train", "valid", "valid", "test"]


def test_feature_checks_find_missing_and_duplicates():
    from src.features import FEATURES as F
    from src.features import TARGET

    row = {f: 1.0 for f in F}
    for c in ["customer_state", "seller_state", "payment_type_main", "primary_category"]:
        row[c] = "x"
    table = pd.DataFrame([row, row, row])
    table["order_id"] = ["a", "a", "b"]
    table[TARGET] = 0
    table["split"] = ["train", "train", "test"]
    table.loc[0, "distance_km"] = np.nan
    checks = feature_checks(table)
    assert checks["duplicates"].loc[0, "rows"] == 1  # order "a" twice
    assert checks["missing"].loc["distance_km", "train"] == 50.0
    assert checks["infinite"]["inf_values"].sum() == 0
