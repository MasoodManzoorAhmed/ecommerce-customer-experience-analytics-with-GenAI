"""Step d: a failing query is sent back to the model once, with the error, and corrected."""

from types import SimpleNamespace

import pytest

from genai.text_to_sql.pipeline import CONFIGS, answer
from src.db import DB_PATH

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="database not built")


class ScriptedModel:
    """Stands in for LLMClient: replies with the given texts in order, records the messages."""

    model = "scripted"

    def __init__(self, *replies):
        self.replies, self.seen = list(replies), []

    def complete(self, messages, max_tokens=0):
        self.seen.append(messages)
        text = self.replies.pop(0)
        return SimpleNamespace(
            text=text, prompt_tokens=10, completion_tokens=5, latency_s=0.1, cached=False
        )


BROKEN = "```sql\nSELECT COUNT(*) FROM fact_orders WHERE delivered = TRUE\n```"  # no such column
FIXED = "```sql\nSELECT COUNT(*) FROM fact_orders WHERE is_delivered\n```"
SCHEMA = "fact_orders(order_id VARCHAR, is_delivered BOOLEAN)"


def test_execution_error_is_sent_back_and_corrected():
    model = ScriptedModel(BROKEN, FIXED)
    out = answer("How many orders were delivered?", model, CONFIGS["a+b+c+d"], schema=SCHEMA)
    assert out["retried"] and out["error_stage"] == ""
    assert out["result"]["rows"] == [[96470]]
    follow_up = model.seen[1][-1]["content"]
    assert follow_up.startswith("Your query failed") and "delivered" in follow_up
    assert out["prompt_tokens"] == 20  # both calls are counted


def test_without_step_d_the_error_is_final():
    model = ScriptedModel(BROKEN)
    out = answer("How many orders were delivered?", model, CONFIGS["a+b+c"], schema=SCHEMA)
    assert out["error_stage"] == "execution" and not out["retried"]
    assert len(model.seen) == 1


def test_only_one_retry_is_allowed():
    model = ScriptedModel(BROKEN, BROKEN)
    out = answer("How many orders were delivered?", model, CONFIGS["a+b+c+d"], schema=SCHEMA)
    assert out["error_stage"] == "execution" and out["retried"]
    assert len(model.seen) == 2
