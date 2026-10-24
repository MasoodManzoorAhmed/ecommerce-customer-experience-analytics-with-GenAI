"""Execution-accuracy matching and the LLM client's cache/retry behaviour (no network)."""

from types import SimpleNamespace

import pytest

from genai.text_to_sql import llm_client
from genai.text_to_sql.evaluate import results_match
from genai.text_to_sql.llm_client import LLMClient


def r(columns, rows):
    return {"columns": columns, "rows": rows}


GOLD = r(["state", "on_time_rate_pct"], [["MA", 82.64], ["CE", 86.26]])


def test_same_result_in_another_order_and_column_names_matches():
    assert results_match(GOLD, r(["uf", "pct"], [["CE", 86.26], ["MA", 82.64]]))


def test_unrounded_and_fraction_values_match():
    assert results_match(GOLD, r(["s", "x"], [["MA", 0.826389], ["CE", 0.862607]]))


def test_extra_columns_are_allowed_and_columns_can_be_reordered():
    assert results_match(GOLD, r(["n", "rate", "state"], [[720, 82.64, "ma"], [1281, 86.26, "CE"]]))


def test_wrong_value_or_extra_rows_do_not_match():
    assert not results_match(GOLD, r(["s", "x"], [["MA", 80.0], ["CE", 86.26]]))
    assert not results_match(GOLD, r(["s", "x"], [["MA", 82.64], ["CE", 86.26], ["BA", 87.8]]))


def test_numeric_text_matches_numbers_and_missing_result_fails():
    assert results_match(r(["year"], [[2017]]), r(["y"], [["2017"]]))
    assert not results_match(GOLD, None)


def test_revenue_including_freight_is_not_accepted():
    assert not results_match(r(["revenue"], [[13220248.93]]), r(["x"], [[15418394.83]]))


class FakeOpenAI:
    """Mimics client.chat.completions.create; fails with HTTP 429 the first `fail` times."""

    def __init__(self, fail=0):
        self.calls, self.fail = 0, fail
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self.calls <= self.fail:
            raise type("RateLimitError", (Exception,), {"status_code": 429})("busy")
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
        message = SimpleNamespace(content="```sql\nSELECT 1\n```")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(llm_client, "MIN_SECONDS_BETWEEN_CALLS", 0)
    monkeypatch.setattr(llm_client, "RETRY_WAITS", (0, 0, 0, 0))
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)


def test_second_identical_request_comes_from_the_cache(tmp_path):
    fake = FakeOpenAI()
    client = LLMClient(model="m:free", cache_path=tmp_path / "c.jsonl", client=fake)
    msgs = [{"role": "user", "content": "q"}]
    first, second = client.complete(msgs), client.complete(msgs)
    assert fake.calls == 1 and not first.cached and second.cached
    # a fresh client reads the cache file from disk, so a rerun costs nothing
    again = LLMClient(model="m:free", cache_path=tmp_path / "c.jsonl", client=fake).complete(msgs)
    assert again.cached and fake.calls == 1


def test_rate_limit_is_retried_then_succeeds(tmp_path):
    fake = FakeOpenAI(fail=2)
    reply = LLMClient(model="m:free", cache_path=tmp_path / "c.jsonl", client=fake).complete(
        [{"role": "user", "content": "q"}]
    )
    assert fake.calls == 3 and reply.prompt_tokens == 100


def test_daily_quota_error_is_not_retried(tmp_path):
    class DailyCap(FakeOpenAI):
        def create(self, **kwargs):
            self.calls += 1
            err = type("RateLimitError", (Exception,), {"status_code": 429})
            raise err("Rate limit exceeded: free-models-per-day")

    fake = DailyCap()
    client = LLMClient(model="m:free", cache_path=tmp_path / "c.jsonl", client=fake)
    with pytest.raises(Exception, match="per-day"):
        client.complete([{"role": "user", "content": "q"}])
    assert fake.calls == 1


def test_local_ollama_model_uses_its_plain_name(tmp_path):
    fake = FakeOpenAI()
    path = tmp_path / "c.jsonl"
    client = LLMClient(model="ollama/qwen2.5-coder-16k", cache_path=path, client=fake)
    reply = client.complete([{"role": "user", "content": "q"}])
    assert client.local and fake.last_kwargs["model"] == "qwen2.5-coder-16k"
    assert reply.model == "ollama/qwen2.5-coder-16k"  # results and cache keep the full name
