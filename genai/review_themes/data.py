"""Module 2 data: low-score reviews, the taxonomy, and a reproducible gold / train split.

    python -m genai.review_themes.data     # writes the splits to genai/review_themes/results/

- gold  (200): the human-verified test set, sampled in proportion to review score x
               delivery situation (late / on time / not delivered), so it mirrors the population
- train (1,500): reviews for LLM-made training labels
The two never share an order (split by order_id), and seed 42 makes the split repeatable.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import yaml

from src.db import ROOT, connect, load_named_sql

DIR = ROOT / "genai" / "review_themes"
RESULTS = DIR / "results"
TAXONOMY = yaml.safe_load((DIR / "taxonomy.yaml").read_text(encoding="utf-8"))
THEMES = list(TAXONOMY["themes"])
SEED = 42
N_GOLD, N_TRAIN = 200, 1500


def load_reviews() -> pd.DataFrame:
    sql = {q.name: q.sql for q in load_named_sql("10_review_themes.sql")}["low_score_reviews"]
    with connect(read_only=True) as con:
        df = con.execute(sql).df()
    df["text"] = df["comment_title"].fillna("") + ". " + df["comment_message"].fillna("")
    df["text"] = df["text"].str.strip(". ").str.replace(r"\s+", " ", regex=True)
    df["situation"] = np.select(
        [~df["is_delivered"].astype(bool), df["is_late"].fillna(False).astype(bool)],
        ["not delivered", "late"],
        default="on time",
    )
    return df


def read_split(name: str) -> pd.DataFrame:
    """Read gold_reviews / train_reviews; keep_default_na=False keeps the few reviews whose
    comment is only punctuation as empty text (they count as 'other'), instead of NaN."""
    return pd.read_csv(RESULTS / f"{name}_reviews.csv", keep_default_na=False)


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gold sample stratified by score x situation; train pool from orders not in gold."""
    rng = np.random.default_rng(SEED)
    strata = df.groupby(["review_score", "situation"])
    shares = strata.size() / len(df)
    gold_parts = []
    for key, group in strata:
        n = min(int(round(shares[key] * N_GOLD)), len(group))
        if n:
            gold_parts.append(group.sample(n=n, random_state=int(rng.integers(1e9))))
    gold = pd.concat(gold_parts)
    if len(gold) < N_GOLD:  # rounding can leave a gap: top up at random
        extra = df.drop(gold.index).sample(n=N_GOLD - len(gold), random_state=SEED)
        gold = pd.concat([gold, extra])
    gold = gold.head(N_GOLD)
    rest = df[~df["order_id"].isin(gold["order_id"])]
    train = rest.sample(n=N_TRAIN, random_state=SEED)
    return gold.sort_values("review_id"), train.sort_values("review_id")


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    df = load_reviews()
    gold, train = split(df)
    cols = [
        "review_id",
        "order_id",
        "review_score",
        "situation",
        "customer_state",
        "year_month",
        "text",
    ]
    gold[cols].to_csv(RESULTS / "gold_reviews.csv", index=False)
    train[cols].to_csv(RESULTS / "train_reviews.csv", index=False)
    df[cols].to_parquet(RESULTS / "all_low_score_reviews.parquet", index=False)
    print(f"low-score reviews with text: {len(df):,}")
    print("gold by score x situation:\n", gold.groupby(["review_score", "situation"]).size())
    print(
        f"train: {len(train):,}; shared orders gold/train: "
        f"{len(set(gold.order_id) & set(train.order_id))}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
