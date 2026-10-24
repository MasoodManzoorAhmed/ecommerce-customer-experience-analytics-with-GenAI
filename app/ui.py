"""Design system for the Streamlit app: palette, global CSS, reusable components, chart style.

Same "Storyteller" identity as the Power BI report and the Excel workbook: deep teal for
structure, teal for normal values, coral ONLY for problems, a warm off-white canvas.
Fonts come from the visitor's own system (no Google Fonts request: faster, and no visitor IP
sent to a third party, which matters under GDPR).
"""

from __future__ import annotations

import html
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

ASSETS = Path(__file__).resolve().parent / "assets"

INK = "#0B3C49"  # headings, sidebar
TEAL = "#0B6E7A"  # normal / good values
LIGHT_TEAL = "#7FB7BE"
PALE = "#E9F2F3"
CORAL = "#E4572E"  # problems only
SAND = "#C9B79C"  # reference lines
TEXT = "#1F2A2E"
MUTED = "#5C6B70"
BORDER = "#E9E2D6"
CANVAS = "#FAF8F4"
GRID = "#EEE9E0"

FONT_STACK = "'Segoe UI', 'Inter', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"

CSS = f"""
<style>
:root {{ --ink:{INK}; --teal:{TEAL}; --coral:{CORAL}; --muted:{MUTED}; --border:{BORDER}; }}
html, body, [class*="css"], .stMarkdown, button, input, textarea {{ font-family: {FONT_STACK}; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px; }}
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* sidebar */
section[data-testid="stSidebar"] {{ border-right: none; }}
section[data-testid="stSidebar"] a span {{ font-size: 0.95rem; }}
img[data-testid="stLogo"] {{ height: 2.4rem; }}
.cx-side-foot {{ color: rgba(233,242,243,0.65); font-size: 0.74rem; line-height: 1.5; }}

/* hero */
.cx-eyebrow {{ color: {TEAL}; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; margin-bottom: 0.35rem; }}
.cx-title {{ color: {INK}; font-size: 2.15rem; font-weight: 750; line-height: 1.15;
  letter-spacing: -0.02em; margin: 0 0 0.5rem 0; }}
.cx-title em {{ color: {CORAL}; font-style: normal; }}
.cx-subtitle {{ color: {MUTED}; font-size: 1.02rem; line-height: 1.55; max-width: 860px;
  margin-bottom: 1.4rem; }}

/* KPI cards */
.cx-kpi {{ background: #FFFFFF; border: 1px solid {BORDER}; border-radius: 14px;
  padding: 1.05rem 1.15rem 0.95rem 1.15rem; height: 100%;
  box-shadow: 0 1px 2px rgba(11,60,73,0.04); margin-bottom: 0.5rem; }}
.cx-kpi-label {{ color: {MUTED}; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.03em;
  text-transform: uppercase; }}
.cx-kpi-value {{ color: {INK}; font-size: 1.85rem; font-weight: 700; margin-top: 0.3rem;
  letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }}
.cx-kpi-value.coral {{ color: {CORAL}; }}
.cx-kpi-sub {{ color: {MUTED}; font-size: 0.8rem; margin-top: 0.25rem; }}

/* section headers, cards, chips, callouts */
.cx-section {{ color: {INK}; font-size: 1.08rem; font-weight: 700; margin: 1.6rem 0 0.1rem 0; }}
.cx-caption {{ color: {MUTED}; font-size: 0.85rem; margin-bottom: 0.6rem; }}
.cx-chip {{ display: inline-block; padding: 0.18rem 0.65rem; border-radius: 999px;
  font-size: 0.78rem; font-weight: 600; margin: 0 0.35rem 0.35rem 0; }}
.cx-chip.teal {{ background: {PALE}; color: {TEAL}; }}
.cx-chip.coral {{ background: #FCE6DF; color: {CORAL}; }}
.cx-chip.ink {{ background: {INK}; color: #FFFFFF; }}
.cx-chip.sand {{ background: #F3EDE3; color: #7A6A4F; }}
.cx-callout {{ background: #FFFFFF; border: 1px solid {BORDER}; border-left: 4px solid {CORAL};
  border-radius: 12px; padding: 0.9rem 1.1rem; color: {TEXT}; font-size: 0.93rem;
  line-height: 1.5; }}
.cx-callout.teal {{ border-left-color: {TEAL}; }}
.cx-callout b {{ color: {INK}; }}
.cx-big {{ color: {INK}; font-size: 3.1rem; font-weight: 750; letter-spacing: -0.03em;
  line-height: 1; font-variant-numeric: tabular-nums; }}
.cx-big.coral {{ color: {CORAL}; }}
.cx-note {{ color: {MUTED}; font-size: 0.8rem; line-height: 1.5; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def sidebar_brand() -> None:
    """Wordmark at the very top of the sidebar, above the page navigation."""
    st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))


def sidebar_footer() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="cx-side-foot">Customer experience analytics · ML · GenAI<br><br>'
            "Data: Olist Brazilian e-commerce (Kaggle), ~96k delivered orders, 2016-2018."
            "<br>Every number is reconciled with SQL, Power BI and Excel."
            "<br><br>Built by Masood</div>",
            unsafe_allow_html=True,
        )


def hero(eyebrow: str, title_html: str, subtitle: str) -> None:
    """Page header. `title_html` may wrap one phrase in <em> to colour it coral."""
    st.markdown(
        f'<div class="cx-eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="cx-title">{title_html}</div>'
        f'<div class="cx-subtitle">{html.escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def section(title: str, caption: str = "") -> None:
    st.markdown(f'<div class="cx-section">{html.escape(title)}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="cx-caption">{html.escape(caption)}</div>', unsafe_allow_html=True)


def kpi_cards(cards: list[tuple[str, str, str, bool]]) -> None:
    """A row of KPI cards: (label, value, sub-caption, highlight_as_problem)."""
    for col, (label, value, sub, problem) in zip(st.columns(len(cards)), cards, strict=True):
        tone = " coral" if problem else ""
        col.markdown(
            f'<div class="cx-kpi"><div class="cx-kpi-label">{html.escape(label)}</div>'
            f'<div class="cx-kpi-value{tone}">{html.escape(value)}</div>'
            f'<div class="cx-kpi-sub">{html.escape(sub)}</div></div>',
            unsafe_allow_html=True,
        )


def chip(text: str, tone: str = "teal") -> str:
    return f'<span class="cx-chip {tone}">{html.escape(text)}</span>'


def callout(text_html: str, tone: str = "coral") -> None:
    st.markdown(f'<div class="cx-callout {tone}">{text_html}</div>', unsafe_allow_html=True)


def style_fig(
    fig: go.Figure, height: int = 340, y_title: str = "", percent: bool = False
) -> go.Figure:
    """One look for every chart: quiet grid, no chart junk, one y-axis, readable hover."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=12, t=12, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_STACK, color=MUTED, size=12),
        showlegend=False,
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=BORDER, font=dict(color=TEXT, size=12)),
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, linecolor=BORDER, ticks="", tickfont=dict(color=MUTED))
    fig.update_yaxes(
        gridcolor=GRID,
        zeroline=False,
        ticks="",
        title_text=y_title,
        tickformat=".0%" if percent else None,
        tickfont=dict(color=MUTED),
    )
    return fig


PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}
