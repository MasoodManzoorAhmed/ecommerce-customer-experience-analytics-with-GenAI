"""Streamlit app: KPI logic matches the reconciled numbers, and every page renders."""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app import metrics as m
from src.db import ROOT

EXPECTED_CSV = ROOT / "powerbi" / "expected_values.csv"
EXPECTED = pd.read_csv(EXPECTED_CSV).set_index("check")["expected_value"]


def test_kpis_from_the_app_extract_match_power_bi_and_sql():
    k = m.kpis(m.load("kpi_month_state"))
    assert k["revenue"] == pytest.approx(EXPECTED["Revenue"], abs=0.01)
    assert k["delivered_orders"] == EXPECTED["Delivered Orders"]
    assert k["on_time_rate"] == pytest.approx(EXPECTED["On-time %"], rel=1e-9)
    assert k["avg_review"] == pytest.approx(EXPECTED["Avg Review"], rel=1e-9)
    assert k["review_on_time"] - k["review_late"] == pytest.approx(
        EXPECTED["Review Gap (on-time - late)"], rel=1e-9
    )


def test_filters_rebuild_ratios_from_sums():
    ms = m.load("kpi_month_state")
    year_2018 = m.kpis(m.apply_filters(ms, 2018, None))
    sp = m.kpis(m.apply_filters(ms, None, "SP"))
    assert round(year_2018["revenue"], 2) == 7217172.24  # gold answer m01
    assert 0 < sp["on_time_rate"] < 1 and sp["delivered_orders"] < 96470


def test_delay_buckets_match_sql_q08():
    q08 = pd.read_csv(ROOT / "sql" / "results" / "q08_reviews_by_delay.csv")
    d = m.delay_reviews(m.load("delay_reviews"))
    assert d["delay_bucket"].tolist() == m.DELAY_ORDER
    assert d["reviews"].tolist() == q08["reviewed_orders"].tolist()
    assert d["avg_review"].round(2).tolist() == q08["avg_review"].tolist()


def test_worst_state_matches_power_bi():
    st_tbl = m.states(m.load("kpi_month_state"))
    worst = st_tbl.iloc[0]
    assert worst["customer_state"] == "MA" and round(worst["on_time_rate"], 4) == 0.8264


def test_risk_bands_follow_the_threshold():
    assert m.risk_band(0.05, 0.045) == "high"
    assert m.risk_band(0.03, 0.045) == "medium"
    assert m.risk_band(0.01, 0.045) == "low"


@pytest.mark.parametrize("page", ["overview", "risk", "themes"])
def test_page_renders_without_errors(page):
    at = AppTest.from_file(str(ROOT / "app" / "pages" / f"{page}.py"), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
