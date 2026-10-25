"""Label every low-score review and publish the result.

    python -m genai.review_themes.apply lora      # LoRA only (~30 min on CPU)
    python -m genai.review_themes.apply cascade   # LoRA + LLM for the reviews LoRA is unsure of

Cascade: LoRA labels everything; reviews where its top probability is below THRESHOLD go to
the zero-shot LLM (the most accurate approach). On the gold set this matched the LLM's
macro-F1 while sending only ~40% of reviews to it. The threshold was scanned on the gold set,
so treat it as "LLM-level quality at a fraction of the calls", not as a better score.

Writes
- DuckDB table fact_review_theme (review_id, order_id, theme, source): joins to fact_orders
- app/data/review_themes.parquet: the same plus score, state, month, LoRA label/confidence, text
LoRA predictions are saved once (results/lora_all.parquet) so the cascade reuses them, and
every LLM reply is cached, so an interrupted cascade resumes where it stopped.
"""

from __future__ import annotations

import sys
import time

import pandas as pd

from genai.review_themes.data import RESULTS
from src.db import ROOT, connect

APP_FILE = ROOT / "app" / "data" / "review_themes.parquet"
LORA_FILE = RESULTS / "lora_all.parquet"
THRESHOLD = 0.7


KEY = ["review_id", "order_id"]  # a review can cover several orders (same text), so both


def lora_labels(df: pd.DataFrame) -> pd.DataFrame:
    if LORA_FILE.exists():
        saved = pd.read_parquet(LORA_FILE)
        if "order_id" not in saved and saved["review_id"].tolist() == df["review_id"].tolist():
            saved.insert(1, "order_id", df["order_id"].to_numpy())  # file from the first run
        if set(KEY) <= set(saved) and len(saved) == len(df):
            return saved
    from genai.review_themes.lora import predict_with_confidence

    start = time.perf_counter()
    themes, conf = predict_with_confidence(df["text"].tolist())
    print(f"LoRA: {len(df):,} reviews in {(time.perf_counter() - start) / 60:.1f} min")
    out = df[KEY].assign(lora_theme=themes, lora_confidence=conf)
    out.to_parquet(LORA_FILE, index=False)
    return out


def publish(df: pd.DataFrame) -> None:
    with connect(read_only=False) as con:
        con.register("themes", df[["review_id", "order_id", "theme", "source"]])
        con.execute("CREATE OR REPLACE TABLE fact_review_theme AS SELECT * FROM themes")
        n = con.execute("SELECT COUNT(*) FROM fact_review_theme").fetchone()[0]
    df.to_parquet(APP_FILE, index=False)
    print(f"fact_review_theme: {n:,} rows; {APP_FILE.name} written")
    print(df["source"].value_counts().to_string())
    print(df["theme"].value_counts(normalize=True).round(3).to_string())


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "lora"
    df = pd.read_parquet(RESULTS / "all_low_score_reviews.parquet")
    df = df.merge(lora_labels(df), on=KEY, validate="1:1")
    df["theme"], df["source"] = df["lora_theme"], "lora"
    if mode == "cascade":
        from genai.review_themes.llm_labeler import label_reviews

        unsure = df["lora_confidence"] < THRESHOLD
        todo = df.loc[unsure].drop_duplicates("review_id")  # each review text once
        print(f"cascade: {len(todo):,} of {df['review_id'].nunique():,} reviews to the LLM")
        labels, stats = label_reviews(todo["text"].tolist())
        llm = dict(zip(todo["review_id"], labels, strict=True))
        df.loc[unsure, "theme"] = df.loc[unsure, "review_id"].map(llm)
        df.loc[unsure, "source"] = "llm"
        print(stats)
    publish(df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
