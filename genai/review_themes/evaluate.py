"""Score theme predictions against the gold set, and measure human/Claude label agreement.

    python -m genai.review_themes.evaluate agreement   # Cohen's kappa: your blind check vs gold
    python -m genai.review_themes.evaluate report      # macro-F1 of every approach on gold

Macro-F1 = the F1 score of each theme, averaged with equal weight, so a model cannot look
good by only getting the big themes right. Cohen's kappa = agreement corrected for the
agreement two people would reach by chance (0 = chance, 1 = perfect, > 0.6 = substantial).
"""

from __future__ import annotations

import json
import sys

import pandas as pd
from sklearn.metrics import accuracy_score, cohen_kappa_score, f1_score

from genai.review_themes.data import DIR, RESULTS, THEMES

GOLD = RESULTS / "gold_labels.csv"
BLIND = DIR / "blind_check.csv"
# approach name -> prediction file on the gold set (review_id, theme)
PREDICTIONS = {
    "zero-shot LLM": RESULTS / "zero_shot_gold.csv",
    "TF-IDF + logistic regression": RESULTS / "tfidf_gold.csv",
    "LoRA fine-tuned transformer": RESULTS / "lora_gold.csv",
}


def score(gold: pd.Series, pred: pd.Series) -> dict:
    """Accuracy, macro-F1 and per-theme F1 for aligned label series."""
    per_theme = f1_score(gold, pred, labels=THEMES, average=None, zero_division=0)
    return {
        "n": len(gold),
        "accuracy": accuracy_score(gold, pred),
        "macro_f1": f1_score(gold, pred, labels=THEMES, average="macro", zero_division=0),
        **{f"f1_{t}": f for t, f in zip(THEMES, per_theme, strict=True)},
    }


def score_file(path) -> dict:
    gold = pd.read_csv(GOLD)[["review_id", "theme"]]
    pred = pd.read_csv(path)[["review_id", "theme"]]
    both = gold.merge(pred, on="review_id", suffixes=("_gold", "_pred"), validate="1:1")
    if len(both) != len(gold):
        raise ValueError(f"{path.name}: {len(both)} of {len(gold)} gold reviews predicted")
    return score(both["theme_gold"], both["theme_pred"])


def agreement() -> dict:
    """Kappa between the owner's blind labels and the gold labels (matched on the id prefix)."""
    blind = pd.read_csv(BLIND, dtype={"your_theme": str}).dropna(subset=["your_theme"])
    if blind.empty:
        raise ValueError(f"no labels yet: fill the your_theme column in {BLIND.name} and save it")
    blind["your_theme"] = blind["your_theme"].str.strip()
    unknown = sorted(set(blind["your_theme"]) - set(THEMES))
    if unknown:
        raise ValueError(f"unknown theme names in blind_check.csv: {unknown}")
    gold = pd.read_csv(GOLD)[["review_id", "theme"]]
    gold["prefix"] = gold["review_id"].str[:8]
    both = blind.merge(gold, left_on="review_id", right_on="prefix", validate="1:1")
    disagree = both.loc[both["your_theme"] != both["theme"], ["check_no", "your_theme", "theme"]]
    return {
        "n": len(both),
        "agreement": float((both["your_theme"] == both["theme"]).mean()),
        "kappa": float(cohen_kappa_score(both["your_theme"], both["theme"])),
        "disagreements": disagree.rename(columns={"theme": "gold"}).to_dict("records"),
    }


def report() -> pd.DataFrame:
    rows = []
    for name, path in PREDICTIONS.items():
        if path.exists():
            rows.append({"approach": name, **score_file(path)})
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "approach_comparison.csv", index=False)
    return table


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "report"
    if which == "agreement":
        out = agreement()
        (RESULTS / "blind_check_agreement.json").write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1))
    else:
        print(report().round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
