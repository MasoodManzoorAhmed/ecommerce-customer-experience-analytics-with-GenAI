"""LLM access for "Ask the data": OpenRouter through the OpenAI-compatible client.

Built for FREE models (US$0 budget), which are rate-limited:
- every response is cached on disk (genai/results/llm_cache.jsonl), keyed by a hash of the
  model + messages + settings, so re-running an evaluation costs no new requests;
- 429 / 5xx / timeouts are retried with exponential backoff;
- a minimum gap between live calls keeps us under the per-minute limit;
- tokens and latency are recorded for the model comparison (cost per query is US$0).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.db import ROOT

CACHE_PATH = ROOT / "genai" / "results" / "llm_cache.jsonl"
DEFAULT_MODEL = "cohere/north-mini-code:free"
COMPARISON_MODEL = "google/gemma-4-31b-it:free"
# Local open-source model served by Ollama on this laptop: free, offline, no request limits.
# "qwen2.5-coder-16k" = qwen2.5-coder:7b with a 16k-token context window (genai/ollama/Modelfile),
# because Ollama's default window would silently cut off the longer prompts of steps a-d.
LOCAL_MODEL = "ollama/qwen2.5-coder-16k"
OLLAMA_BASE_URL = "http://localhost:11434/v1"
MIN_SECONDS_BETWEEN_CALLS = 3.5  # free tier: about 20 requests per minute
RETRY_WAITS = (5, 15, 45, 90)  # seconds before each retry


@dataclass
class LLMReply:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float  # of the original live call (also reported for cached replies)
    cached: bool


def cache_key(model: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LLMClient:
    """Chat completions with a disk cache, retries and pacing."""

    def __init__(self, model: str | None = None, cache_path: Path = CACHE_PATH, client=None):
        load_dotenv(ROOT / ".env")
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_MODEL
        self.local = self.model.startswith("ollama/")  # no key, no pacing, no quota
        self.cache_path = cache_path
        self._cache = self._load_cache()
        self._client = client  # injected in tests; created lazily otherwise
        self._last_call = 0.0

    def _load_cache(self) -> dict[str, dict]:
        cache = {}
        if self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    cache[entry["key"]] = entry
        return cache

    def _openai(self):
        if self._client is None:
            from openai import OpenAI

            if self.local:  # Ollama speaks the same OpenAI format; it ignores the key
                self._client = OpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL, timeout=600)
            else:
                self._client = OpenAI(
                    api_key=os.environ["OPENROUTER_API_KEY"],
                    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                    timeout=120,
                )
        return self._client

    @property
    def api_model(self) -> str:
        """Model name as the server knows it ('ollama/' only marks a local model here)."""
        return self.model.removeprefix("ollama/")

    def complete(
        self, messages: list[dict], temperature: float = 0.0, max_tokens: int = 800
    ) -> LLMReply:
        key = cache_key(self.model, messages, temperature, max_tokens)
        if key in self._cache:
            return LLMReply(**{**self._cache[key]["reply"], "cached": True})
        reply = self._call_with_retries(messages, temperature, max_tokens)
        entry = {"key": key, "model": self.model, "reply": asdict(reply)}
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._cache[key] = entry
        return reply

    def _call_with_retries(self, messages, temperature, max_tokens) -> LLMReply:
        last_error: Exception | None = None
        for attempt in range(len(RETRY_WAITS) + 1):
            gap = 0 if self.local else MIN_SECONDS_BETWEEN_CALLS
            wait = self._last_call + gap - time.time()
            if wait > 0:
                time.sleep(wait)
            start = time.time()
            self._last_call = start
            try:
                resp = self._openai().chat.completions.create(
                    model=self.api_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                usage = resp.usage
                return LLMReply(
                    text=(resp.choices[0].message.content or "").strip(),
                    model=self.model,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    latency_s=round(time.time() - start, 2),
                    cached=False,
                )
            except Exception as err:  # noqa: BLE001 - classify below
                last_error = err
                if not _retryable(err) or attempt == len(RETRY_WAITS):
                    raise
                time.sleep(RETRY_WAITS[attempt])
        raise RuntimeError("unreachable") from last_error


def _retryable(err: Exception) -> bool:
    """Rate limits, server errors and timeouts are worth retrying; bad requests are not."""
    if "per-day" in str(err):
        return False  # the free DAILY quota is used up: waiting minutes won't help
    status = getattr(err, "status_code", None)
    if status is not None:
        return status == 429 or status >= 500
    return type(err).__name__ in {"APITimeoutError", "APIConnectionError", "TimeoutError"}
