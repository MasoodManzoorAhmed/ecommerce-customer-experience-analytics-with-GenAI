"""Ask the data: plain-English question -> SQL (always shown) -> guarded, read-only result."""

import json
import os
import urllib.request

import pandas as pd
import plotly.graph_objects as go
import sqlglot
import streamlit as st
from dotenv import load_dotenv

from app.metrics import ROOT
from app.ui import INK, PLOTLY_CONFIG, TEAL, callout, chip, hero, section, style_fig
from genai.text_to_sql.llm_client import OLLAMA_BASE_URL, LLMClient
from genai.text_to_sql.pipeline import CONFIGS, answer, schema_for
from src.db import DB_PATH

CONFIG = CONFIGS["a+b+c+d"]  # the best configuration from the evaluation
APP_CACHE = ROOT / "app" / ".cache" / "llm_cache.jsonl"  # app questions never touch eval results
LOCAL_MODEL = "ollama/qwen2.5-coder-16k"
HOSTED_MODELS = {
    "cohere/north-mini-code:free": "OpenRouter · north-mini-code (free, 50/day)",
    "google/gemma-4-31b-it:free": "OpenRouter · gemma-4-31b (free, 50/day)",
}
SUGGESTIONS = [  # deliberately NOT evaluation questions
    "Which 5 product categories had the best average review in 2018?",
    "How did the late-delivery rate change by quarter in 2017?",
    "What share of delivered orders were paid by voucher?",
    "Which 5 seller states have the highest average freight per order?",
]


@st.cache_data(ttl=30, show_spinner=False)
def local_model_ready() -> bool:
    try:
        url = OLLAMA_BASE_URL.removesuffix("/v1") + "/api/tags"
        tags = json.load(urllib.request.urlopen(url, timeout=2))
        return any(t["name"].startswith("qwen2.5-coder-16k") for t in tags.get("models", []))
    except Exception:  # noqa: BLE001 - Ollama not installed or not running
        return False


@st.cache_data(show_spinner=False)
def prompt_schema() -> str:
    return schema_for(CONFIG)


def auto_chart(df: pd.DataFrame):
    """A bar or line chart when the result is a label column + a number column."""
    if df.shape[1] < 2 or not 2 <= len(df) <= 40:
        return None
    label, value = df.columns[0], df.columns[-1]
    if not pd.api.types.is_numeric_dtype(df[value]):
        return None
    labels = df[label].astype(str)
    is_time = labels.str.fullmatch(r"\d{4}(-\d{2})?|\d{1,2}").all()
    if is_time:
        trace = go.Scatter(
            x=labels, y=df[value], mode="lines+markers", line=dict(color=TEAL, width=2)
        )
    else:
        trace = go.Bar(x=labels, y=df[value], marker_color=TEAL)
    fig = go.Figure(trace)
    fig.update_layout(xaxis_title=label, yaxis_title=value)
    fig.update_xaxes(type="category")  # quarters/years are labels, not a number line
    return style_fig(fig, height=320)


def pretty_sql(sql: str) -> str:
    try:
        return sqlglot.transpile(sql, read="duckdb", write="duckdb", pretty=True)[0]
    except sqlglot.errors.ParseError:
        return sql


load_dotenv(ROOT / ".env")
hero(
    "GenAI · text-to-SQL · semantic layer · guardrails",
    "Ask the data in <em>plain English</em>.",
    "Type a business question. A language model writes the SQL using the company's definitions "
    "(semantic layer), similar solved examples and the column descriptions; the query is checked "
    "and run read-only. You always see the SQL, so you can check what was counted.",
)

if not DB_PATH.exists():
    callout(
        "<b>This page needs the project database</b> (<code>data/olist.duckdb</code>). Run "
        "<code>python scripts/download_data.py</code> and <code>python scripts/build_db.py</code> "
        "first. The Overview and Risk pages work without it."
    )
    st.stop()

options = {}
if local_model_ready():
    options[LOCAL_MODEL] = "Local · qwen2.5-coder 7B (free, unlimited)"
if os.getenv("OPENROUTER_API_KEY"):
    options |= HOSTED_MODELS
if not options:
    callout(
        "<b>No language model is available.</b> Start the local model with Ollama "
        "(<code>ollama create qwen2.5-coder-16k -f genai/ollama/Modelfile</code>) or add an "
        "OpenRouter key to <code>.env</code>."
    )
    st.stop()

c1, c2 = st.columns([1.3, 2])
model = c1.selectbox("Model", list(options), format_func=options.get, key="ask_model")
if model in HOSTED_MODELS:
    c2.markdown(
        '<div class="cx-note" style="padding-top:1.9rem">Hosted model: your question is sent to '
        "OpenRouter. The free tier allows about 50 questions a day.</div>",
        unsafe_allow_html=True,
    )

picked = st.pills("Try a question", SUGGESTIONS, key="ask_suggestion")
with st.form("ask_form", border=False):
    question = st.text_area(
        "Your question",
        value=picked or "",
        placeholder="e.g. Which 5 states had the most late deliveries in 2018?",
        height=90,
    )
    asked = st.form_submit_button("Ask", type="primary", icon=":material/arrow_forward:")

if asked and question.strip():
    with st.spinner("Finding similar examples, writing SQL, checking and running it…"):
        out = answer(
            question.strip(), LLMClient(model=model, cache_path=APP_CACHE), CONFIG, prompt_schema()
        )
    st.session_state.setdefault("ask_history", []).insert(0, out)

history = st.session_state.get("ask_history", [])
if history:
    out = history[0]
    ok = out["error_stage"] == ""
    status = chip("answered", "teal") if ok else chip(f"failed at {out['error_stage']}", "coral")
    if out["cached"]:
        status += chip(f"from cache · first answered in {out['latency_s']:.0f} s", "sand")
    else:
        status += chip(f"{out['latency_s']:.1f} s", "sand")
    if out["retried"]:
        status += chip("self-corrected once", "ink")
    section(out["question"])
    st.markdown(status, unsafe_allow_html=True)
    if out["sql"]:
        st.code(pretty_sql(out["sql"]), language="sql")
    elif out["sql_raw"]:
        st.code(out["sql_raw"], language="sql")
    if ok:
        result = pd.DataFrame(out["result"]["rows"], columns=out["result"]["columns"])
        if result.shape == (1, 1):
            st.markdown(
                f'<div class="cx-big">{result.iat[0, 0]:,}</div>'
                if isinstance(result.iat[0, 0], int)
                else f'<div class="cx-big">{result.iat[0, 0]}</div>',
                unsafe_allow_html=True,
            )
            st.caption(result.columns[0])
        else:
            chart = auto_chart(result)
            if chart is not None:
                st.plotly_chart(chart, config=PLOTLY_CONFIG, use_container_width=True)
            st.dataframe(result, hide_index=True, use_container_width=True)
    else:
        callout(
            "<b>The question could not be answered safely.</b> "
            f"<code>{out['error'][:300]}</code><br>Try rephrasing it, or name the metric "
            "(revenue, on-time rate, average review) and the period."
        )
    if len(history) > 1:
        with st.expander(f"Earlier questions ({len(history) - 1})"):
            for h in history[1:6]:
                st.markdown(f"**{h['question']}**")
                st.code(h["sql"] or h["sql_raw"] or h["error"], language="sql")

with st.expander("How reliable is this assistant?"):
    st.markdown(
        "Measured on a 46-question benchmark with hand-checked answers (execution accuracy), "
        "adding one improvement at a time on the local model: **34.8% → 80.4%**. The semantic "
        "layer gave the largest gain. The remaining errors are mostly queries that run but count "
        "the wrong thing, which is why the SQL is always shown. Guardrails: one SELECT only, "
        "allowed tables only, no file access, automatic LIMIT, read-only connection, 15 s timeout."
    )
    chart_path = ROOT / "genai" / "results" / "accuracy_per_step.png"
    if chart_path.exists():
        st.image(str(chart_path), use_container_width=True)
st.markdown(
    f'<div class="cx-note" style="color:{INK}">Answers come from the Olist star schema '
    "(DuckDB). Business definitions: <code>genai/semantic_layer.yaml</code>.</div>",
    unsafe_allow_html=True,
)
