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
DESCRIPTIONS_PATH = ROOT / "genai" / "text_to_sql" / "schema_descriptions.yaml"
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


CONFIGS = {
    "baseline": Config("baseline"),
    "a": Config("a", descriptions=True),
    "a+b": Config("a+b", descriptions=True, semantic_layer=True),
    "a+b+c": Config("a+b+c", descriptions=True, semantic_layer=True, examples=True),
}
MAX_LISTED_VALUES = 30  # text columns with at most this many distinct values get a value list


def schema_text() -> str:
    """'table(column TYPE, ...)' for every allowed table, read from the database itself."""
    lines = []
    with connect(read_only=True) as con:
        for table in sorted(ALLOWED_TABLES):
            cols = con.execute(f"DESCRIBE {table}").fetchall()
            lines.append(f"{table}(" + ", ".join(f"{c[0]} {c[1]}" for c in cols) + ")")
    return "\n".join(lines)


def schema_for(config: Config) -> str:
    """The schema part of the prompt for a configuration (plain, or described for step a)."""
    return described_schema_text() if config.descriptions else schema_text()


def load_descriptions() -> dict:
    return yaml.safe_load(DESCRIPTIONS_PATH.read_text(encoding="utf-8"))["tables"]


def described_schema_text() -> str:
    """Step a: every table and column with its meaning, plus the stored values of short text
    columns (read live from the database, e.g. order_status, state codes, payment methods)."""
    descriptions = load_descriptions()
    blocks = []
    with connect(read_only=True) as con:
        for table in sorted(ALLOWED_TABLES):
            info = descriptions[table]
            lines = [f"TABLE {table}: {' '.join(info['description'].split())}"]
            for name, col_type, *_ in con.execute(f"DESCRIBE {table}").fetchall():
                text = " ".join(info["columns"][name].split())
                if col_type == "VARCHAR":
                    values = con.execute(
                        f"SELECT DISTINCT {name} FROM {table} WHERE {name} IS NOT NULL "
                        f"ORDER BY 1 LIMIT {MAX_LISTED_VALUES + 1}"
                    ).fetchall()
                    if len(values) <= MAX_LISTED_VALUES:
                        text += " Values: " + ", ".join(repr(v[0]) for v in values) + "."
                lines.append(f"  - {name} {col_type}: {text}")
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def semantic_layer_text() -> str:
    return SEMANTIC_LAYER_PATH.read_text(encoding="utf-8")


def build_messages(question: str, config: Config, schema: str) -> list[dict]:
    """`schema` is schema_text() for the baseline or described_schema_text() for step a."""
    parts = [SYSTEM_PROMPT, "Schema:\n" + schema]
    if config.self_correct:
        raise NotImplementedError("step d is built after step a+b+c is measured")
    if config.semantic_layer:
        layer = yaml.safe_load(semantic_layer_text())
        parts.append(
            "Business definitions (semantic layer):\n" + yaml.safe_dump(layer, sort_keys=False)
        )
    if config.examples:
        from genai.text_to_sql.retriever import examples_text  # loads the embedding model

        parts.append("Examples of similar solved questions:\n\n" + examples_text(question))
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
    messages = build_messages(question, config, schema or schema_for(config))
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
