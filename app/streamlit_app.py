"""Olist customer-experience analytics: Streamlit app entry point.

streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # the app imports src/, genai/ and app/ from the project root

import streamlit as st  # noqa: E402

from app.ui import inject_css, sidebar_brand, sidebar_footer  # noqa: E402

st.set_page_config(
    page_title="Olist CX Analytics",
    page_icon=":material/insights:",
    layout="wide",
    initial_sidebar_state="auto",  # open on desktop, collapsed on phones
)
inject_css()
sidebar_brand()

pages = st.navigation(
    {
        "Analytics": [
            st.Page(
                "pages/overview.py", title="Overview", icon=":material/insights:", default=True
            ),
            st.Page("pages/risk.py", title="Late-delivery risk", icon=":material/local_shipping:"),
        ],
        "GenAI": [
            st.Page("pages/ask.py", title="Ask the data", icon=":material/forum:"),
            st.Page("pages/themes.py", title="Review themes", icon=":material/reviews:"),
        ],
    }
)
sidebar_footer()
pages.run()
