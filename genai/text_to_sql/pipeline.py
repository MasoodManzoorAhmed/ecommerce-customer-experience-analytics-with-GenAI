"""Question -> SQL -> guardrails -> read-only execution.

The prompt is assembled from optional parts, so each improvement step can be switched on and
measured on its own (ARCHITECTURE §5):
  baseline: rules + schema (table and column names with types) + question
  a: column descriptions   b: semantic layer   c: few-shot examples   d: self-correction retry
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from genai.text_to_sql.eval_set import ALLOWED_TABLES
from genai.text_to_sql.guardrails import GuardrailError, check_sql, extract_sql, run_safely
from genai.text_to_sql.llm_client import LLMClient
from src.db import ROOT, connect

SEMANTIC_LAYER_PATH = ROOT / "genai" / "semantic_layer.yaml"
# Free "reasoning" models spend hidden thinking tokens before the SQL; 800 cut answers off
MAX_TOKENS = 4000

SYSTEM_PROMPT = """You are an expert data analyst.
Write ONE DuckDB SQL query that answers the user's question.
Rules:
- Use only the tables and columns listed below.
- Return a single SELECT query (CTEs allowed). Never modify data.
- Return only the columns needed to answer the question.
- Reply with the SQL inside a ```sql code block and nothing else."""


@dataclass(frozen=True)
class Config:
    """Which prompt parts are switched on."""

    name: str = "baseline"
    descriptions: bool = False  # step a
    semantic_layer: bool = False  # step b
    examples: bool = False  # step c
    self_correct: bool = False  # step d


CONFIGS = {"baseline": Config("baseline")}


def schema_text() -> str:
    """'table(column TYPE, ...)' for every allowed table, read from the database itself."""
    lines = []
    with connect(read_only=True) as con:
        for table in sorted(ALLOWED_TABLES):
            cols = con.execute(f"DESCRIBE {table}").fetchall()
            lines.append(f"{table}(" + ", ".join(f"{c[0]} {c[1]}" for c in cols) + ")")
    return "\n".join(lines)


def semantic_layer_text() -> str:
    return SEMANTIC_LAYER_PATH.read_text(encoding="utf-8")


def build_messages(question: str, config: Config, schema: str) -> list[dict]:
    parts = [SYSTEM_PROMPT, "Schema:\n" + schema]
    if config.descriptions or config.examples or config.self_correct:
        raise NotImplementedError("steps a, c and d are built after the baseline is measured")
    if config.semantic_layer:
        layer = yaml.safe_load(semantic_layer_text())
        parts.append(
            "Business definitions (semantic layer):\n" + yaml.safe_dump(layer, sort_keys=False)
        )
    return [
        {"role": "system", "content": "\n\n".join(parts)},
        {"role": "user", "content": question},
    ]


def answer(question: str, client: LLMClient, config: Config, schema: str | None = None) -> dict:
    """Run the whole pipeline for one question. Never raises: failures are reported per stage."""
    out = {
        "question": question,
        "model": client.model,
        "config": config.name,
        "sql_raw": "",
        "sql": "",
        "result": None,
        "error_stage": "",
        "error": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "latency_s": 0.0,
        "cached": False,
    }
    messages = build_messages(question, config, schema or schema_text())
    try:
        reply = client.complete(messages, max_tokens=MAX_TOKENS)
    except Exception as err:  # noqa: BLE001 - reported, not raised
        out.update(error_stage="llm", error=f"{type(err).__name__}: {str(err)[:200]}")
        return out
    out.update(
        sql_raw=reply.text,
        prompt_tokens=reply.prompt_tokens,
        completion_tokens=reply.completion_tokens,
        latency_s=reply.latency_s,
        cached=reply.cached,
    )
    try:
        out["sql"] = check_sql(extract_sql(reply.text))
    except GuardrailError as err:
        out.update(error_stage="guardrail", error=str(err))
        return out
    try:
        out["result"] = run_safely(out["sql"])
    except Exception as err:  # noqa: BLE001 - SQL errors are part of what we measure
        out.update(error_stage="execution", error=f"{type(err).__name__}: {str(err)[:200]}")
    return out
