"""The semantic layer's definitions must run and agree with the Power BI reconciliation values."""

import pandas as pd
import pytest
import yaml

from src.db import DB_PATH, ROOT, connect

LAYER = yaml.safe_load((ROOT / "genai" / "semantic_layer.yaml").read_text(encoding="utf-8"))
METRICS = LAYER["metrics"]
EXPECTED_CSV = ROOT / "powerbi" / "expected_values.csv"
EXPECTED = pd.read_csv(EXPECTED_CSV).set_index("check")["expected_value"]

# metric -> (check name in powerbi/expected_values.csv, scale: the layer returns percentages 0-100)
POWER_BI = {
    "delivered_orders": ("Delivered Orders", 1),
    "revenue": ("Revenue", 1),
    "average_order_value": ("AOV", 1),
    "late_orders": ("Late Orders", 1),
    "on_time_rate_pct": ("On-time %", 100),
    "average_review": ("Avg Review", 1),
    "average_delivery_days": ("Avg Delivery Days", 1),
    "review_gap": ("Review Gap (on-time - late)", 1),
}


def metric_sql(m: dict) -> str:
    return f"SELECT {m['expression']} FROM {m['from']} WHERE {m['filter']}"


@pytest.mark.parametrize("name", list(METRICS))
def test_every_metric_is_documented(name):
    for key in ("description", "expression", "from", "filter"):
        assert METRICS[name].get(key), f"{name} has no {key}"


@pytest.mark.skipif(not DB_PATH.exists(), reason="database not built")
@pytest.mark.parametrize("name", list(METRICS))
def test_every_metric_runs_and_matches_its_stated_value(name):
    with connect(read_only=True) as con:
        value = float(con.execute(metric_sql(METRICS[name])).fetchone()[0])
    if "expected" in METRICS[name]:
        assert value == pytest.approx(METRICS[name]["expected"], rel=1e-5)


@pytest.mark.skipif(not DB_PATH.exists(), reason="database not built")
@pytest.mark.parametrize("name", list(POWER_BI))
def test_definitions_match_power_bi(name):
    """One definition across SQL, Power BI and the LLM (CLAUDE.md convention)."""
    check, scale = POWER_BI[name]
    with connect(read_only=True) as con:
        value = float(con.execute(metric_sql(METRICS[name])).fetchone()[0])
    assert value == pytest.approx(EXPECTED[check] * scale, rel=1e-9)
