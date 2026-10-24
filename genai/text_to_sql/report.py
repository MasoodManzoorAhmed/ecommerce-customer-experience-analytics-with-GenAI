"""Results report for "Ask the data": accuracy-per-step chart and summary table.

Reads genai/results/text_to_sql_runs.csv (written by evaluate.py) and produces:
- genai/results/accuracy_per_step.png  (overall accuracy per improvement step + by difficulty)
- genai/results/text_to_sql_summary.csv (accuracy, difficulty split, latency, tokens
  per model x step)

    python -m genai.text_to_sql.report
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from genai.text_to_sql.evaluate import RUNS_PATH, summary  # noqa: E402
from src.db import ROOT  # noqa: E402

RESULTS = ROOT / "genai" / "results"
CHART_PATH = RESULTS / "accuracy_per_step.png"
SUMMARY_PATH = RESULTS / "text_to_sql_summary.csv"
ABLATION_MODEL = "ollama/qwen2.5-coder-16k"
STEPS = ["baseline", "a", "a+b", "a+b+c", "a+b+c+d"]
STEP_LABELS = [
    "Baseline\n(schema)",
    "+ a\ndescriptions",
    "+ b\nsemantic layer",
    "+ c\nexamples",
    "+ d\nself-correct",
]

# Validated reference palette (same as the notebook figures) and text tokens
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"


def load_runs() -> pd.DataFrame:
    runs = pd.read_csv(RUNS_PATH, keep_default_na=False)
    runs["correct"] = runs["correct"].astype(str) == "True"
    for col in ("latency_s", "prompt_tokens", "completion_tokens"):
        runs[col] = pd.to_numeric(runs[col], errors="coerce")
    return runs


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 25))
    ax.set_yticklabels([f"{v}%" for v in range(0, 101, 25)], color=INK2)


def make_chart(table: pd.DataFrame) -> None:
    rows = table.loc[ABLATION_MODEL].reindex(STEPS)
    x = range(len(STEPS))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6), facecolor=SURFACE)

    # Panel 1: one series -> no legend; every column labelled (only 5 values)
    _style(ax1)
    ax1.bar(x, rows["accuracy_pct"], width=0.45, color=BLUE)
    for i, v in zip(x, rows["accuracy_pct"], strict=True):
        ax1.text(i, v + 2, f"{v:.1f}%", ha="center", va="bottom", color=INK, fontsize=10)
    ax1.set_xticks(list(x), STEP_LABELS, fontsize=9, color=INK2)
    ax1.set_title("Execution accuracy, 46 questions", loc="left", color=INK, fontsize=11)

    # Panel 2: three series -> legend + direct labels at the line ends; same 0-100 scale
    _style(ax2)
    for col, name, color in (
        ("easy_pct", "Easy (15)", AQUA),
        ("medium_pct", "Medium (18)", BLUE),
        ("hard_pct", "Hard (13)", ORANGE),
    ):
        ax2.plot(
            x,
            rows[col],
            color=color,
            linewidth=2,
            marker="o",
            markersize=6,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            label=name,
        )
        ax2.text(
            len(STEPS) - 1 + 0.12,
            rows[col].iloc[-1],
            f"{rows[col].iloc[-1]:.0f}%",
            va="center",
            color=INK2,
            fontsize=9,
        )
    ax2.set_xticks(list(x), STEP_LABELS, fontsize=9, color=INK2)
    ax2.set_xlim(-0.3, len(STEPS) - 0.4)
    ax2.set_title("By difficulty", loc="left", color=INK, fontsize=11)
    ax2.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=INK2)

    fig.suptitle(
        "Ask the data: each improvement measured on one fixed model (local qwen2.5-coder 7B, free)",
        x=0.01,
        ha="left",
        color=INK,
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main() -> int:
    runs = load_runs()
    table = summary(runs)
    table.to_csv(SUMMARY_PATH)
    make_chart(table)
    print(table.to_string())
    print(f"-> {CHART_PATH.relative_to(ROOT)}, {SUMMARY_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
