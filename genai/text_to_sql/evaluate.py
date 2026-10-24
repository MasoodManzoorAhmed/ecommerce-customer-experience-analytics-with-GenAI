"""Execution-accuracy evaluation of the text-to-SQL pipeline.

A generated query is CORRECT when its result matches the gold query's result:
- row order is ignored, and column names don't matter;
- extra columns in the answer are allowed (each gold column must be found in it);
- numbers match within max(0.05, 0.01%) (so 93.2269 = 93.23 and 4.2 = 4.16 at the precision
  shown), and a rate given as a fraction matches the same rate as a percentage (0.9323 = 93.23);
- text is compared case-insensitively; numeric text ('2017') matches the number 2017;
- the number of rows must be the same (a "top 5" answer with 27 rows is wrong).

Free models are rate-limited, so runs are resumable: answers are cached by the LLM client, and
--max-new-calls stops a run before it uses up the daily free quota.

    python -m genai.text_to_sql.evaluate --config baseline
    python -m genai.text_to_sql.evaluate --config baseline --ids e01,e02 --max-new-calls 10
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys

import pandas as pd

from genai.text_to_sql.eval_set import EXPECTED_PATH, load_eval_set
from genai.text_to_sql.llm_client import LLMClient
from genai.text_to_sql.pipeline import CONFIGS, answer, schema_text
from src.db import ROOT

RUNS_PATH = ROOT / "genai" / "results" / "text_to_sql_runs.csv"
SCALES = (1.0, 100.0, 0.01)


# ----------------------------------------------------------------------------- matching
def _norm(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        return text.lower()


def _equal(gold, pred, scale: float) -> bool:
    if gold is None or pred is None:
        return gold is None and pred is None
    if isinstance(gold, float) and isinstance(pred, float):
        pred = pred * scale
        return abs(gold - pred) <= max(0.05, 1e-4 * abs(gold))
    return gold == pred


def results_match(gold: dict, pred: dict | None) -> bool:
    """True if the predicted result answers the question the same way as the gold result."""
    if pred is None:
        return False
    g_rows = [[_norm(v) for v in r] for r in gold["rows"]]
    p_rows = [[_norm(v) for v in r] for r in pred["rows"]]
    if len(g_rows) != len(p_rows):
        return False
    if not g_rows:
        return True
    n_gold, n_pred = len(g_rows[0]), len(p_rows[0])
    if n_pred < n_gold:
        return False
    numeric = [all(isinstance(r[j], float) or r[j] is None for r in g_rows) for j in range(n_gold)]
    for cols in itertools.permutations(range(n_pred), n_gold):
        scale_options = [SCALES if numeric[j] else (1.0,) for j in range(n_gold)]
        for scales in itertools.product(*scale_options):
            if _rows_match(g_rows, p_rows, cols, scales):
                return True
    return False


def _rows_match(g_rows, p_rows, cols, scales) -> bool:
    """Greedy one-to-one row matching (order-insensitive) for one column mapping."""
    unused = list(range(len(p_rows)))
    for g in g_rows:
        for k in unused:
            p = p_rows[k]
            if all(
                _equal(g[j], p[c], s) for j, (c, s) in enumerate(zip(cols, scales, strict=True))
            ):
                unused.remove(k)
                break
        else:
            return False
    return True


# ----------------------------------------------------------------------------- runs
def evaluate(
    config_name: str, model: str | None, ids: list[str] | None, max_new_calls: int
) -> pd.DataFrame:
    config = CONFIGS[config_name]
    client = LLMClient(model=model)
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    items = [i for i in load_eval_set() if not ids or i.id in ids]
    schema = schema_text()
    rows, new_calls = [], 0
    for item in items:
        if new_calls >= max_new_calls:
            print(f"stopping: reached --max-new-calls {max_new_calls} (rerun later to continue)")
            break
        out = answer(item.question, client, config, schema)
        new_calls += 0 if out["cached"] else 1  # a failed call still used a request
        if out["error_stage"] == "llm":
            # e.g. the free daily quota ran out: not the model's fault, so don't score it;
            # stop here and rerun later (finished items come back from the cache for free)
            print(f"  {item.id:4s} LLM call failed, stopping: {out['error']}")
            break
        correct = out["error_stage"] == "" and results_match(expected[item.id], out["result"])
        stage = out["error_stage"] or ("" if correct else "wrong_result")
        rows.append(
            {
                "id": item.id,
                "difficulty": item.difficulty,
                "tags": ",".join(item.tags),
                "config": config.name,
                "model": client.model,
                "correct": correct,
                "error_stage": stage,
                "error": out["error"],
                "sql": out["sql"] or out["sql_raw"],
                "prompt_tokens": out["prompt_tokens"],
                "completion_tokens": out["completion_tokens"],
                "latency_s": out["latency_s"],
                "cached": out["cached"],
            }
        )
        mark = "✓" if correct else f"✗ {stage}"
        print(f"  {item.id:4s} {mark:18s} {'(cached)' if out['cached'] else ''}")
    df = pd.DataFrame(rows)
    _save(df)
    return df


def _save(df: pd.DataFrame) -> None:
    """Upsert this run's rows into the runs file (one row per id x config x model)."""
    if df.empty:
        return
    RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if RUNS_PATH.exists():
        old = pd.read_csv(RUNS_PATH)
        keys = set(zip(df["id"], df["config"], df["model"], strict=True))
        keep = [k not in keys for k in zip(old["id"], old["config"], old["model"], strict=True)]
        df = pd.concat([old[keep], df], ignore_index=True)
    df.sort_values(["model", "config", "id"]).to_csv(RUNS_PATH, index=False)


def summary(df: pd.DataFrame) -> pd.DataFrame:
    """Accuracy overall and by difficulty, plus mean latency and tokens (live calls only)."""
    g = df.groupby(["model", "config"])
    out = g.agg(answered=("id", "size"), correct=("correct", "sum"))
    out["accuracy_pct"] = (100 * out["correct"] / out["answered"]).round(1)
    for d in ("easy", "medium", "hard"):
        sub = df[df["difficulty"] == d].groupby(["model", "config"])["correct"]
        out[f"{d}_pct"] = (100 * sub.mean()).round(1)
    out["mean_latency_s"] = g["latency_s"].mean().round(2)
    out["mean_prompt_tokens"] = g["prompt_tokens"].mean().round(0)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="baseline", choices=sorted(CONFIGS))
    parser.add_argument("--model", default=None, help="defaults to LLM_MODEL in .env")
    parser.add_argument("--ids", default="", help="comma-separated item ids (default: all)")
    parser.add_argument("--max-new-calls", type=int, default=46)
    args = parser.parse_args()
    ids = [i.strip() for i in args.ids.split(",") if i.strip()] or None
    df = evaluate(args.config, args.model, ids, args.max_new_calls)
    if not df.empty:
        print(summary(df).to_string())
        print(df["error_stage"].replace("", "correct").value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
