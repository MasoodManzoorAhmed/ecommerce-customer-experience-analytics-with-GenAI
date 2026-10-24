"""Overview: the executive story in one page (KPIs, trends, the delay -> review link, states)."""

import plotly.graph_objects as go
import streamlit as st

from app import metrics as m
from app.ui import (
    CORAL,
    INK,
    LIGHT_TEAL,
    PLOTLY_CONFIG,
    SAND,
    TEAL,
    callout,
    hero,
    kpi_cards,
    section,
    style_fig,
)

ms_all = st.cache_data(m.load)("kpi_month_state")
dr_all = st.cache_data(m.load)("delay_reviews")

hero(
    "Olist · Brazilian marketplace · 2017-2018",
    "Late deliveries cost about <em>2 stars</em> per order.",
    "Why do customers leave bad reviews, and where does delivery go wrong? Every number below "
    "is rebuilt from the order data for the period and state you choose.",
)

# ---------------------------------------------------------------- filters (one row, above)
f1, f2, _ = st.columns([2.2, 1.6, 3])
year_choice = f1.segmented_control(
    "Period", ["All years", "2017", "2018"], default="All years", key="ov_year"
)
year = None if year_choice in (None, "All years") else int(year_choice)
state_options = ["All states", *sorted(ms_all["customer_state"].unique())]
state_choice = f2.selectbox("Customer state", state_options, key="ov_state")
state = None if state_choice == "All states" else state_choice

ms = m.apply_filters(ms_all, year, state)
dr = m.apply_filters(dr_all, year, state)
k = m.kpis(ms)
scope = f"{year_choice if year else 'All years'} · {state_choice}"

# ---------------------------------------------------------------- KPIs
gap = k["review_on_time"] - k["review_late"]
kpi_cards(
    [
        ("Revenue", f"R$ {k['revenue'] / 1e6:,.2f}M", "item value, delivered orders", False),
        ("Delivered orders", f"{k['delivered_orders']:,.0f}", f"AOV R$ {k['aov']:,.2f}", False),
        (
            "On-time delivery",
            f"{k['on_time_rate']:.1%}",
            f"{1 - k['on_time_rate']:.1%} arrived late",
            k["on_time_rate"] < 0.90,
        ),
        ("Average review", f"{k['avg_review']:.2f} ★", "1-5 stars, delivered orders", False),
        (
            "Review gap",
            f"−{gap:.2f} ★",
            f"late {k['review_late']:.2f} ★ vs on time {k['review_on_time']:.2f} ★",
            True,
        ),
    ]
)

# ---------------------------------------------------------------- trends (2 charts, 1 axis each)
mon = m.monthly(ms, full_window=year is None)
c1, c2 = st.columns(2, gap="large")
with c1:
    section("Monthly revenue", f"R$, by purchase month · {scope}")
    peak = mon.loc[mon["revenue"].idxmax()]
    colors = [INK if ym == peak["year_month"] else TEAL for ym in mon["year_month"]]
    fig = go.Figure(
        go.Bar(
            x=mon["year_month"],
            y=mon["revenue"],
            marker_color=colors,
            hovertemplate="%{x}<br>R$ %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_annotation(
        x=peak["year_month"],
        y=peak["revenue"],
        text=f"peak {peak['year_month']}",
        showarrow=False,
        yshift=12,
        font=dict(color=INK, size=11),
    )
    st.plotly_chart(style_fig(fig), config=PLOTLY_CONFIG, use_container_width=True)
with c2:
    section("Late-delivery rate", f"share of delivered orders arriving late · {scope}")
    avg_late = 1 - k["on_time_rate"]
    fig = go.Figure(
        go.Scatter(
            x=mon["year_month"],
            y=mon["late_rate"],
            mode="lines+markers",
            line=dict(color=CORAL, width=2),
            marker=dict(size=7, color=CORAL, line=dict(color="#FFFFFF", width=2)),
            hovertemplate="%{x}<br>%{y:.1%} late<extra></extra>",
        )
    )
    fig.add_hline(y=avg_late, line=dict(color=SAND, width=1.5, dash="dot"))
    fig.add_annotation(
        x=mon["year_month"].iloc[0],
        y=avg_late,
        text=f"average {avg_late:.1%}",
        showarrow=False,
        yshift=10,
        xanchor="left",
        font=dict(color="#7A6A4F", size=11),
    )
    st.plotly_chart(style_fig(fig, percent=True), config=PLOTLY_CONFIG, use_container_width=True)

# ---------------------------------------------------------------- the core finding
d = m.delay_reviews(dr)
c3, c4 = st.columns([1.35, 1], gap="large")
with c3:
    section("Average review by delivery delay", f"reviewed delivered orders · {scope}")
    fig = go.Figure(
        go.Bar(
            x=[b.replace(" days ", " days<br>") for b in d["delay_bucket"]],
            y=d["avg_review"],
            marker_color=[CORAL if late else TEAL for late in d["late"]],
            text=[f"{v:.2f}" for v in d["avg_review"]],
            textposition="outside",
            textfont=dict(color=INK, size=12),
            customdata=d[["reviews", "low_share"]],
            hovertemplate="%{x}<br>%{y:.2f} ★ · %{customdata[1]:.0%} gave 1-2 ★"
            "<br>%{customdata[0]:,} reviews<extra></extra>",
        )
    )
    fig.update_yaxes(range=[0, 5.2])
    st.plotly_chart(style_fig(fig), config=PLOTLY_CONFIG, use_container_width=True)
with c4:
    section("What the data says", scope)
    late_buckets = d[d["late"]]
    one_to_three = d.loc[d["delay_bucket"] == "1-3 days late", "avg_review"]
    st.markdown("&nbsp;", unsafe_allow_html=True)
    callout(
        f"<b>Ratings fall from the first day late.</b> On-time orders average "
        f"<b>{k['review_on_time']:.2f} ★</b>; just 1-3 days late already drops to "
        f"<b>{one_to_three.iloc[0]:.2f} ★</b>"
        if len(one_to_three)
        else "<b>Ratings fall as soon as an order is late.</b>"
    )
    st.markdown("&nbsp;", unsafe_allow_html=True)
    if len(late_buckets):
        worst = late_buckets.iloc[-1]
        callout(
            f"<b>{worst['low_share']:.0%} of customers</b> whose order came "
            f"{worst['delay_bucket']} gave 1 or 2 stars.",
            tone="coral",
        )
    st.markdown("&nbsp;", unsafe_allow_html=True)
    callout(
        "<b>Action to test:</b> warn customers early and prioritise high-risk orders "
        "(see <i>Late-delivery risk</i>), then measure the effect on reviews.",
        tone="teal",
    )

# ---------------------------------------------------------------- states
section(
    "On-time delivery by customer state",
    "states with 500+ delivered orders in the selection · worst first · coral = below 90%",
)
st_tbl = m.states(m.apply_filters(ms_all, year, None))
if st_tbl.empty:
    st.info("No state has 500+ delivered orders in this period.")
else:
    fig = go.Figure(
        go.Bar(
            x=st_tbl["customer_state"],
            y=st_tbl["on_time_rate"],
            marker_color=[
                (CORAL if r < 0.90 else TEAL) if (state is None or s == state) else LIGHT_TEAL
                for s, r in zip(st_tbl["customer_state"], st_tbl["on_time_rate"], strict=True)
            ],
            customdata=st_tbl[["delivered_orders", "avg_review"]],
            hovertemplate="%{x}: %{y:.1%} on time<br>%{customdata[0]:,} orders · "
            "%{customdata[1]:.2f} ★<extra></extra>",
        )
    )
    fig.update_yaxes(range=[0.75, 1.0])
    st.plotly_chart(
        style_fig(fig, height=300, percent=True), config=PLOTLY_CONFIG, use_container_width=True
    )

st.markdown(
    '<div class="cx-note">Definitions: revenue = item prices of delivered orders, excluding '
    "freight · on time = delivered by the promised date · reviews from delivered orders. "
    "Source: <code>app/data</code> extracts of the DuckDB star schema; totals reconcile with "
    "SQL, the Power BI report and the Excel workbook (R$ 13,220,248.93 · 96,470 orders · "
    "93.23% on time · 4.16 ★).</div>",
    unsafe_allow_html=True,
)
