"""Evaluation set for "Ask the data": load, validate, and produce the expected results.

The questions and gold SQL live in genai/eval/text_to_sql_eval.yaml. Running this module
executes every gold query on a read-only connection and writes the expected results to
genai/eval/text_to_sql_expected.json, which the evaluator compares model answers against.

    python -m genai.text_to_sql.eval_set
"""

from __future__ import annotations

import datetime as dt
import decimal
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

from src.db import ROOT, connect

EVAL_PATH = ROOT / "genai" / "eval" / "text_to_sql_eval.yaml"
EXPECTED_PATH = ROOT / "genai" / "eval" / "text_to_sql_expected.json"

# The star schema the assistant may query (staging views and raw tables are off limits)
ALLOWED_TABLES = frozenset(
    {
        "fact_orders",
        "fact_order_items",
        "dim_customer",
        "dim_seller",
        "dim_product",
        "dim_date",
        "fact_order_risk",
    }
)
DIFFICULTIES = ("easy", "medium", "hard")


@dataclass(frozen=True)
class EvalItem:
    id: str
    question: str
    gold_sql: str
    difficulty: str
    tags: tuple[str, ...]


def load_eval_set(path: Path = EVAL_PATH) -> list[EvalItem]:
    """Read the YAML file and validate it (unique ids, known difficulty, non-empty fields)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["items"]
    items = [
        EvalItem(
            id=r["id"],
            question=" ".join(r["question"].split()),
            gold_sql=r["gold_sql"].strip(),
            difficulty=r["difficulty"],
            tags=tuple(r["tags"]),
        )
        for r in raw
    ]
    ids = [i.id for i in items]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate ids: {sorted(duplicates)}")
    for item in items:
        if item.difficulty not in DIFFICULTIES:
            raise ValueError(f"{item.id}: unknown difficulty {item.difficulty!r}")
        if not item.question or not item.gold_sql:
            raise ValueError(f"{item.id}: empty question or SQL")
    return items


def tables_used(sql: str) -> set[str]:
    """Real tables a query reads (CTE names excluded), parsed with sqlglot."""
    tree = sqlglot.parse_one(sql, read="duckdb")
    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    return {t.name for t in tree.find_all(exp.Table)} - ctes


def _plain(value):
    """Database value -> JSON-safe value (Decimal -> float, dates -> ISO text)."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def run_query(con, sql: str) -> dict:
    """Execute SQL and return {'columns': [...], 'rows': [[...], ...]} with plain values."""
    cur = con.execute(sql)
    columns = [d[0] for d in cur.description]
    rows = [[_plain(v) for v in row] for row in cur.fetchall()]
    return {"columns": columns, "rows": rows}


def build_expected(items: list[EvalItem]) -> dict[str, dict]:
    """Run every gold query (read-only) and collect its result."""
    with connect(read_only=True) as con:
        return {item.id: run_query(con, item.gold_sql) for item in items}


def main() -> int:
    items = load_eval_set()
    bad = {i.id: sorted(tables_used(i.gold_sql) - ALLOWED_TABLES) for i in items}
    bad = {k: v for k, v in bad.items() if v}
    if bad:
        print(f"gold SQL uses tables outside the allowed list: {bad}")
        return 1
    expected = build_expected(items)
    EXPECTED_PATH.write_text(json.dumps(expected, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = {d: sum(i.difficulty == d for i in items) for d in DIFFICULTIES}
    print(f"{len(items)} items {counts} -> {EXPECTED_PATH.relative_to(ROOT)}")
    for item in items:
        result = expected[item.id]
        preview = result["rows"][:3]
        print(f"  {item.id:4s} {len(result['rows']):>3} row(s)  {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
