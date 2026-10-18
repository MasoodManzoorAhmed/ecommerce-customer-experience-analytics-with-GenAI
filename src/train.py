"""Model training, evaluation and cost-based threshold selection for late-delivery prediction."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from src.features import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, TARGET

SEED = 42
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


def xy(table: pd.DataFrame, split: str) -> tuple[pd.DataFrame, np.ndarray]:
    """Feature matrix and target for one split."""
    part = table[table["split"] == split]
    return part[FEATURES], part[TARGET].to_numpy()


def evaluate(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    """PR-AUC (primary), ROC-AUC, base rate, and PR-AUC lift over random ranking."""
    pr_auc = average_precision_score(y, p)
    return {
        "pr_auc": float(pr_auc),
        "roc_auc": float(roc_auc_score(y, p)),
        "base_rate": float(y.mean()),
        "pr_auc_lift": float(pr_auc / y.mean()),
    }


# ----------------------------------------------------------------- baseline
def make_logreg(c: float = 1.0, class_weight: str | None = None) -> Pipeline:
    """Scaled + one-hot logistic regression. All preprocessing is fitted on training data only."""
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("to_str", FunctionTransformer(_to_str, feature_names_out="one-to-one")),
            ("onehot", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=50)),
        ]
    )
    pre = ColumnTransformer(
        [("num", numeric, NUMERIC_FEATURES), ("cat", categorical, CATEGORICAL_FEATURES)]
    )
    model = LogisticRegression(C=c, class_weight=class_weight, max_iter=3000, random_state=SEED)
    return Pipeline([("pre", pre), ("model", model)])


def _to_str(x):
    """Categories -> strings for OneHotEncoder (a named function so the pipeline can be pickled)."""
    return x.astype(str)


def tune_logreg(
    x_tr, y_tr, x_va, y_va, c_grid=(0.01, 0.1, 1.0), weights=(None, "balanced")
) -> tuple[Pipeline, pd.DataFrame]:
    """Pick C and class weighting by validation PR-AUC; return the best pipeline and the table.

    class_weight=None keeps probabilities on the training base rate (interpretable);
    "balanced" up-weights late orders but inflates the probabilities.
    """
    rows, best = [], None
    for c, w in itertools.product(c_grid, weights):
        pipe = make_logreg(c, w).fit(x_tr, y_tr)
        score = average_precision_score(y_va, pipe.predict_proba(x_va)[:, 1])
        rows.append({"C": c, "class_weight": w or "none", "valid_pr_auc": score})
        if best is None or score > best[0]:
            best = (score, pipe)
    table = pd.DataFrame(rows).sort_values("valid_pr_auc", ascending=False, ignore_index=True)
    return best[1], table


def attach_train_mean(pipeline: Pipeline, x_tr: pd.DataFrame) -> Pipeline:
    """Store the mean of the transformed TRAINING matrix (the SHAP baseline for a linear model)."""
    z = pipeline.named_steps["pre"].transform(x_tr)
    z = z.toarray() if hasattr(z, "toarray") else np.asarray(z)
    pipeline.train_mean_ = z.mean(axis=0)
    return pipeline


# ----------------------------------------------------------------- LightGBM
def tune_lgbm(
    x_tr,
    y_tr,
    x_va,
    y_va,
    num_leaves=(7, 15, 31, 63),
    min_child_samples=(20, 100, 500),
    weighted=(False, True),
) -> tuple[lgb.LGBMClassifier, pd.DataFrame]:
    """Small grid search; each config uses early stopping on validation PR-AUC.

    weighted=True sets scale_pos_weight = negatives / positives (class imbalance correction).
    """
    pos_weight = float((y_tr == 0).sum() / (y_tr == 1).sum())
    rows, best = [], None
    for leaves, mcs, w in itertools.product(num_leaves, min_child_samples, weighted):
        model = lgb.LGBMClassifier(
            n_estimators=3000,
            learning_rate=0.03,
            num_leaves=leaves,
            min_child_samples=mcs,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            scale_pos_weight=pos_weight if w else 1.0,
            random_state=SEED,
            verbose=-1,
        )
        model.fit(
            x_tr,
            y_tr,
            eval_X=(x_va,),
            eval_y=(y_va,),
            eval_metric="average_precision",
            callbacks=[lgb.early_stopping(100, verbose=False)],
        )
        score = average_precision_score(y_va, model.predict_proba(x_va)[:, 1])
        rows.append(
            {
                "num_leaves": leaves,
                "min_child_samples": mcs,
                "class_weighted": w,
                "best_iteration": model.best_iteration_,
                "valid_pr_auc": score,
            }
        )
        if best is None or score > best[0]:
            best = (score, model)
    return best[1], pd.DataFrame(rows).sort_values(
        "valid_pr_auc", ascending=False, ignore_index=True
    )


# ----------------------------------------------------------------- threshold
def cost_curve(y: np.ndarray, p: np.ndarray, cost_fn: float, cost_fp: float) -> pd.DataFrame:
    """Expected cost = cost_fn * FN + cost_fp * FP for every candidate threshold."""
    thresholds = np.unique(np.quantile(p, np.linspace(0, 1, 1001)))
    rows = []
    for t in thresholds:
        flag = p >= t
        tp = int((flag & (y == 1)).sum())
        fp = int((flag & (y == 0)).sum())
        fn = int((~flag & (y == 1)).sum())
        rows.append(
            {
                "threshold": float(t),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "cost": cost_fn * fn + cost_fp * fp,
                "precision": tp / (tp + fp) if tp + fp else np.nan,
                "recall": tp / (tp + fn) if tp + fn else np.nan,
            }
        )
    return pd.DataFrame(rows)


def choose_threshold(y, p, cost_fn: float = 5.0, cost_fp: float = 1.0) -> dict[str, float]:
    """Threshold with the lowest expected cost, plus the cost of the two no-model policies."""
    curve = cost_curve(y, p, cost_fn, cost_fp)
    best = curve.loc[curve["cost"].idxmin()]
    return {
        "threshold": float(best["threshold"]),
        "cost": float(best["cost"]),
        "precision": float(best["precision"]),
        "recall": float(best["recall"]),
        "cost_flag_none": float(cost_fn * (y == 1).sum()),
        "cost_flag_all": float(cost_fp * (y == 0).sum()),
    }


def confusion_at(y: np.ndarray, p: np.ndarray, threshold: float, cost_fn=5.0, cost_fp=1.0) -> dict:
    """Confusion matrix, precision, recall and cost at a fixed threshold."""
    flag = p >= threshold
    tp = int((flag & (y == 1)).sum())
    fp = int((flag & (y == 0)).sum())
    fn = int((~flag & (y == 1)).sum())
    tn = int((~flag & (y == 0)).sum())
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else float("nan"),
        "recall": tp / (tp + fn) if tp + fn else float("nan"),
        "flagged_pct": 100 * flag.mean(),
        "cost": cost_fn * fn + cost_fp * fp,
        "cost_flag_none": cost_fn * (tp + fn),
        "cost_flag_all": cost_fp * (fp + tn),
    }


# ----------------------------------------------------------------- artefacts
def save_artifacts(model, metadata: dict, name: str = "late_delivery_model") -> tuple[Path, Path]:
    """Save the model (joblib) and its metadata (JSON) to models/."""
    MODELS_DIR.mkdir(exist_ok=True)
    model_path = MODELS_DIR / f"{name}.pkl"
    meta_path = MODELS_DIR / "metadata.json"
    joblib.dump(model, model_path)
    meta_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    return model_path, meta_path
