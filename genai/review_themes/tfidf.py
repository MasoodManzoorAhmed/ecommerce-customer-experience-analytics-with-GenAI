"""Approach 2: classic ML. TF-IDF features + logistic regression, trained on the LLM labels.

    python -m genai.review_themes.tfidf     # trains on train_llm_labels.csv, predicts gold

The LLM is the "teacher" that labels 1,500 training reviews; this cheap model is the
"student". It never sees the gold set while training, so the gold score is honest.
"""

from __future__ import annotations

import json
import sys
import time
import unicodedata

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from genai.review_themes.data import RESULTS, SEED, read_split

MODEL_PATH = RESULTS / "tfidf_model.joblib"


def normalise(text: str) -> str:
    """Lower-case and strip accents, so 'não' and 'nao' (common in reviews) are one word."""
    text = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def build() -> Pipeline:
    """Word 1-2 grams catch phrases ('nao recebi'); character 3-5 grams survive typos."""
    features = FeatureUnion(
        [
            ("words", TfidfVectorizer(preprocessor=normalise, ngram_range=(1, 2), min_df=2)),
            (
                "chars",
                TfidfVectorizer(
                    preprocessor=normalise, analyzer="char_wb", ngram_range=(3, 5), min_df=2
                ),
            ),
        ]
    )
    clf = LogisticRegression(max_iter=2000, C=5.0, class_weight="balanced", random_state=SEED)
    return Pipeline([("features", features), ("clf", clf)])


def main() -> int:
    train = read_split("train").merge(
        pd.read_csv(RESULTS / "train_llm_labels.csv"), on="review_id", validate="1:1"
    )
    gold = read_split("gold")
    model = build()
    start = time.perf_counter()
    model.fit(train["text"], train["theme"])
    fit_s = time.perf_counter() - start
    start = time.perf_counter()
    pred = model.predict(gold["text"])
    predict_s = time.perf_counter() - start
    gold[["review_id"]].assign(theme=pred).to_csv(RESULTS / "tfidf_gold.csv", index=False)
    joblib.dump(model, MODEL_PATH)
    stats = {
        "train_reviews": len(train),
        "fit_seconds": fit_s,
        "seconds_per_review": predict_s / len(gold),
    }
    (RESULTS / "tfidf_stats.json").write_text(json.dumps(stats, indent=1))
    print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
