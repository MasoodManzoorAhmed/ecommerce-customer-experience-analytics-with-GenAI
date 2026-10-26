"""Late-delivery risk: score a real test-period order, explain it (SHAP), and try what-ifs."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app import metrics as m
from app.ui import (
    CORAL,
    INK,
    PLOTLY_CONFIG,
    TEAL,
    callout,
    chip,
    hero,
    section,
    style_fig,
)
from src.features import FEATURES
from src.predict import linear_contributions, load_model


@st.cache_resource
def model_and_meta():
    model, meta = load_model()
    return model, meta


@st.cache_data
def scored_orders():
    model, _ = model_and_meta()
    df = m.load("risk_test_orders")
    df["late_probability"] = model.predict_proba(df[FEATURES])[:, 1]
    return df


model, meta = model_and_meta()
threshold = meta["threshold"]
orders = scored_orders()
base_rate = orders["is_late"].mean()

hero(
    "Late-delivery model · logistic regression · test period Apr-Aug 2018",
    "Will this order <em>arrive late</em>?",
    "The model scores an order at the moment of purchase, using only what is known then "
    "(promised delivery time, distance, seller track record, platform load). Pick a real order "
    "from the unseen test period, see why it scored as it did, and change the inputs.",
)

# ---------------------------------------------------------------- order picker
p1, p2 = st.columns([2.2, 3])
view = p1.segmented_control(
    "Show orders",
    ["Highest risk", "Arrived late", "Arrived on time"],
    default="Highest risk",
    key="risk_view",
)
if view == "Arrived late":
    pool = orders[orders["is_late"] == 1]
elif view == "Arrived on time":
    pool = orders[orders["is_late"] == 0]
else:
    pool = orders
pool = pool.sort_values("late_probability", ascending=False).head(30)
labels = {
    row.order_id: f"{row.order_id[:8]} · {row.late_probability:.0%} risk · "
    f"{row.seller_state} → {row.customer_state} · {row.primary_category}"
    for row in pool.itertuples()
}
order_id = p2.selectbox("Order", list(labels), format_func=labels.get, key="risk_order")
order = orders.loc[orders["order_id"] == order_id].iloc[0]

# ---------------------------------------------------------------- prediction + explanation
x = orders.loc[orders["order_id"] == order_id, FEATURES]
p = float(model.predict_proba(x)[0, 1])
band = m.risk_band(p, threshold)
left, right = st.columns([1, 1.6], gap="large")
with left:
    with st.container(border=True):
        st.markdown(
            '<div class="cx-kpi-label">Predicted late probability</div>', unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="cx-big{" coral" if band == "high" else ""}">{p:.0%}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            chip(f"{band} risk", "coral" if band == "high" else "teal" if band == "low" else "sand")
            + chip(
                "arrived late" if order["is_late"] else "arrived on time",
                "coral" if order["is_late"] else "teal",
            )
            + chip(f"{p / base_rate:.1f}× the average order", "ink"),
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="cx-note">Average late rate in the test period: {base_rate:.1%}. '
            f"High risk = at or above {threshold:.1%} (cost-based threshold, missed late order "
            "= 5× a false alarm). Purchased "
            f"{order['purchase_ts']:%d %b %Y}, promised in {int(order['promised_days'])} days, "
            + (
                "distance unknown."
                if np.isnan(order["distance_km"])
                else f"{order['distance_km']:,.0f} km."
            )
            + "</div>",
            unsafe_allow_html=True,
        )
with right:
    section(
        "Why this score", "SHAP contributions in log-odds · coral raises the risk, teal lowers it"
    )
    contrib = linear_contributions(model, x).iloc[0]
    contrib = contrib.drop(labels=["is_nov_dec"]).sort_values(key=np.abs, ascending=False).head(8)
    contrib = contrib[::-1]
    fig = go.Figure(
        go.Bar(
            x=contrib.values,
            y=[m.FEATURE_LABELS.get(f, f) for f in contrib.index],
            orientation="h",
            marker_color=[CORAL if v > 0 else TEAL for v in contrib.values],
            customdata=[str(order[f]) for f in contrib.index],
            hovertemplate="%{y}<br>value: %{customdata}<br>%{x:+.2f} log-odds<extra></extra>",
        )
    )
    fig.add_vline(x=0, line=dict(color=INK, width=1))
    st.plotly_chart(style_fig(fig, height=330), config=PLOTLY_CONFIG, width="stretch")

# ---------------------------------------------------------------- what-if
section("What if…", "change the order and the model re-scores it instantly")
w1, w2, w3, w4 = st.columns(4)
promised = w1.slider(
    "Promised delivery days", 2, 60, int(order["promised_days"]), key="wi_promised"
)
known_km = 0 if np.isnan(order["distance_km"]) else int(round(order["distance_km"]))
distance = w2.slider("Seller-customer distance (km)", 0, 3500, known_km, step=50, key="wi_distance")
freight = w3.slider(
    "Freight cost (R$)",
    0.0,
    200.0,
    float(min(order["freight_value"], 200.0)),
    step=1.0,
    key="wi_freight",
)
same_state = w4.toggle("Seller in the customer's state", bool(order["same_state"]), key="wi_same")
x_new = x.copy()
x_new["promised_days"] = promised
x_new["distance_km"] = float(distance)
x_new["freight_value"] = freight
x_new["freight_ratio"] = freight / float(order["order_value"]) if order["order_value"] else np.nan
x_new["same_state"] = int(same_state)
p_new = float(model.predict_proba(x_new)[0, 1])
delta = p_new - p
change = (
    "unchanged"
    if abs(delta) < 0.0005
    else f"{'+' if delta > 0 else '−'}{abs(delta) * 100:.1f} points vs {p:.1%}"
)
callout(
    f"With these inputs the predicted late probability is <b>{p_new:.1%}</b> "
    f"({change}), <b>{m.risk_band(p_new, threshold)} risk</b>.",
    tone="coral" if delta > 0.005 else "teal",
)

with st.expander("How good is this model? (read before using it)"):
    tm = meta["test_metrics"]
    st.markdown(
        f"- **Ranking, not certainty.** Test PR-AUC **{tm['pr_auc']:.3f}** "
        f"vs **{tm['base_rate']:.3f}** for random guessing ({tm['pr_auc_lift']:.1f}× better); "
        f"ROC-AUC {tm['roc_auc']:.3f}.\n"
        "- **Use it as a priority list** for cheap actions (an early *“may be delayed”* message), "
        "not as a yes/no alarm: a flag only pays off if a missed late order costs more than about "
        "6 false alarms.\n"
        "- **Drift:** the late rate moved from 5.7% (2017) to 12.9% (Q1 2018) to 4.4% (test), so "
        "probabilities need monthly recalibration in production.\n"
        "- Details: `notebooks/02_late_delivery_model.ipynb` (time-based split, no leakage, SHAP "
        "checked against the `shap` library)."
    )
