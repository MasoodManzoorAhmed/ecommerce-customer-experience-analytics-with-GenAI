"""Review themes (GenAI Module 2): what unhappy customers complain about, and how we know."""

import html

import plotly.graph_objects as go
import streamlit as st

from app import metrics as m
from app.ui import (
    CORAL,
    INK,
    LIGHT_TEAL,
    MUTED,
    PLOTLY_CONFIG,
    SAND,
    TEAL,
    callout,
    hero,
    kpi_cards,
    section,
    style_fig,
)

if not (m.DATA / "review_themes.parquet").exists():
    st.info("Review themes are not built yet: run `python -m genai.review_themes.apply lora`.")
    st.stop()

themes_all = st.cache_data(m.load_themes)()
THEME_COLORS = {
    "never_arrived": CORAL,
    "late_delivery": "#F2A38A",
    "wrong_or_missing_item": INK,
    "damaged": TEAL,
    "product_quality": LIGHT_TEAL,
    "other": SAND,
}

# ---------------------------------------------------------------- filters
f1, f2, _ = st.columns([2.2, 1.6, 3])
year_choice = f1.segmented_control(
    "Period", ["All years", "2017", "2018"], default="All years", key="th_year"
)
year = None if year_choice in (None, "All years") else int(year_choice)
state_options = ["All states", *sorted(themes_all["customer_state"].unique())]
state_choice = f2.selectbox("Customer state", state_options, key="th_state")
state = None if state_choice == "All states" else state_choice
df = m.apply_filters(themes_all, year, state)
scope = f"{year_choice if year else 'All years'} · {state_choice}"
if df.empty:
    st.warning("No low-score reviews with text for this selection.")
    st.stop()

shares = m.theme_shares(df)
top = shares.iloc[0]
delivery = df["theme"].isin(m.DELIVERY_THEMES).mean()
product = df["theme"].isin(m.PRODUCT_THEMES).mean()

llm_share = (df["source"] == "llm").mean()
checked = (
    f", with a local LLM re-labelling the {llm_share:.0%} the model was unsure about."
    if llm_share > 0
    else "."
)
hero(
    "GenAI Module 2 · complaint themes",
    f"<em>{top['label']}</em> is the top complaint in bad reviews.",
    f"Every 1-3 star review with a written comment ({len(df):,} for {scope}), classified into "
    f"one complaint theme by a fine-tuned Portuguese model{checked}",
)

kpi_cards(
    [
        ("Reviews classified", f"{len(df):,}", "1-3 ★ with a comment", False),
        ("Top theme", f"{top['share']:.0%}", top["label"].lower(), True),
        ("Delivery problems", f"{delivery:.0%}", "never arrived + late", delivery > 0.4),
        ("Product problems", f"{product:.0%}", "wrong, damaged or poor quality", False),
    ]
)

# ---------------------------------------------------------------- charts
c1, c2 = st.columns([1, 1.25], gap="large")
with c1:
    section("Share of bad reviews by theme", f"one theme per review · {scope}")
    s = shares.iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=s["share"],
            y=s["label"],
            orientation="h",
            marker_color=[THEME_COLORS[t] for t in s["theme"]],
            text=[f"{v:.0%}" for v in s["share"]],
            textposition="outside",
            textfont=dict(color=INK, size=12),
            customdata=s["reviews"],
            hovertemplate="%{y}<br>%{x:.1%} · %{customdata:,} reviews<extra></extra>",
        )
    )
    fig = style_fig(fig, height=330)
    fig.update_xaxes(tickformat=".0%", range=[0, s["share"].max() * 1.25])
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, config=PLOTLY_CONFIG, width="stretch")
with c2:
    section("Theme mix by delivery situation", f"share of each situation's bad reviews · {scope}")
    mix = m.theme_by_situation(df)
    fig = go.Figure()
    for theme in m.THEME_LABELS:
        if theme in mix.columns:
            fig.add_bar(
                name=m.THEME_LABELS[theme],
                y=mix.index,
                x=mix[theme],
                orientation="h",
                marker_color=THEME_COLORS[theme],
                hovertemplate=f"{m.THEME_LABELS[theme]}<br>%{{y}}: %{{x:.0%}}<extra></extra>",
            )
    fig = style_fig(fig, height=330)
    fig.update_layout(
        barmode="stack",
        showlegend=True,
        legend=dict(
            orientation="h", y=-0.18, x=0, traceorder="normal", font=dict(size=11, color=MUTED)
        ),
    )
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, config=PLOTLY_CONFIG, width="stretch")

on_time = df[df["situation"] == "on time"]
if len(on_time):
    on_time_product = on_time["theme"].isin(m.PRODUCT_THEMES).mean()
    callout(
        f"<b>Fixing delivery is not enough.</b> Even when the order arrived on time, "
        f"{on_time_product:.0%} of bad reviews ({len(on_time):,} reviews) are about the product: "
        "wrong or missing items, damage, or quality. That points at seller and catalogue "
        "quality, not logistics.",
        tone="teal",
    )

# ---------------------------------------------------------------- read the reviews
section("Read the reviews", "a random sample of the selected theme (original Portuguese)")
choice = st.pills(
    "Theme",
    list(m.THEME_LABELS),
    format_func=m.THEME_LABELS.get,
    default=top["theme"],
    key="th_pick",
    label_visibility="collapsed",
)
picked = df[(df["theme"] == (choice or top["theme"])) & (df["text"].str.len() > 0)]
sample = picked.sample(n=min(6, len(picked)), random_state=42) if len(picked) else picked
for _, r in sample.iterrows():
    with st.container(border=True):
        st.markdown(
            f'<div class="cx-note"><b>{"★" * int(r["review_score"])}</b> · {r["situation"]} · '
            f"{r['customer_state']} · {r['year_month']}</div>"
            f"{html.escape(r['text'])}",  # customer text: escaped before rendering as HTML
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------- how it was labelled
section(
    "How the labels were made",
    "three approaches scored on 200 hand-labelled reviews never used for training",
)
comp = m.approach_comparison()
if not comp.empty:
    st.dataframe(
        comp.rename(
            columns={
                "approach": "Approach",
                "macro_f1": "Macro-F1",
                "accuracy": "Accuracy",
                "seconds_per_review": "Seconds / review",
            }
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Macro-F1": st.column_config.NumberColumn(format="%.3f"),
            "Accuracy": st.column_config.NumberColumn(format="percent"),
            "Seconds / review": st.column_config.NumberColumn(format="%.4f"),
        },
    )
callout(
    "<b>Cascade:</b> the fine-tuned model (LoRA on BERTimbau) labels every review; reviews where "
    "it is less than 70% sure go to the LLM, the most accurate approach. "
    + (
        f"{llm_share:.0%} of the reviews shown here were labelled by the LLM."
        if llm_share > 0
        else "The LLM pass has not run yet, so these are the fine-tuned model's labels."
    ),
    tone="teal",
)
