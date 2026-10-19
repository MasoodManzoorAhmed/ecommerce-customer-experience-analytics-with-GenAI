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
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
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
# Heavily skewed numeric features (training skew > 2): candidates for a log transform
SKEWED_FEATURES = [
    "order_value",
    "freight_value",
    "freight_ratio",
    "n_items",
    "n_sellers",
    "total_weight_g",
    "total_volume_cm3",
    "seller_orders_90d",
    "seller_delivered_90d",
    "market_volume_ratio",
]


def make_logreg(
    c: float = 1.0, class_weight: str | None = None, log_skewed: bool = False
) -> Pipeline:
    """Scaled + one-hot logistic regression. All preprocessing is fitted on training data only.

    Missing numeric values are filled with the TRAINING median, and a 0/1 "was missing"
    column is added per affected feature (so the model can still learn from missingness).
    log_skewed=True applies log1p to SKEWED_FEATURES before scaling (tested on validation).
    """

    def numeric_steps(log: bool) -> Pipeline:
        steps = [("impute", SimpleImputer(strategy="median", add_indicator=True))]
        if log:
            steps.append(("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")))
        return Pipeline([*steps, ("scale", StandardScaler())])

    categorical = Pipeline(
        [
            ("to_str", FunctionTransformer(_to_str, feature_names_out="one-to-one")),
            ("onehot", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=50)),
        ]
    )
    if log_skewed:
        plain = [f for f in NUMERIC_FEATURES if f not in SKEWED_FEATURES]
        numeric = [
            ("num", numeric_steps(False), plain),
            ("log", numeric_steps(True), SKEWED_FEATURES),
        ]
    else:
        numeric = [("num", numeric_steps(False), NUMERIC_FEATURES)]
    pre = ColumnTransformer([*numeric, ("cat", categorical, CATEGORICAL_FEATURES)])
    model = LogisticRegression(C=c, class_weight=class_weight, max_iter=3000, random_state=SEED)
    return Pipeline([("pre", pre), ("model", model)])


def _to_str(x):
    """Categories -> strings for OneHotEncoder (a named function so the pipeline can be pickled)."""
    return x.astype(str)


def tune_logreg(
    x_tr,
    y_tr,
    x_va,
    y_va,
    c_grid=(0.01, 0.1, 1.0),
    weights=(None, "balanced"),
    log_options=(False, True),
) -> tuple[Pipeline, pd.DataFrame]:
    """Pick C, class weighting and the log transform by validation PR-AUC.

    class_weight=None keeps probabilities on the training base rate (interpretable);
    "balanced" up-weights late orders but inflates the probabilities.
    """
    rows, best = [], None
    for c, w, log in itertools.product(c_grid, weights, log_options):
        pipe = make_logreg(c, w, log).fit(x_tr, y_tr)
        score = average_precision_score(y_va, pipe.predict_proba(x_va)[:, 1])
        rows.append({"C": c, "class_weight": w or "none", "log_skewed": log, "valid_pr_auc": score})
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


# ----------------------------------------------------------------- robustness checks
def bootstrap_pr_auc(
    y: np.ndarray, scores: dict[str, np.ndarray], n_boot: int = 1000, seed: int = SEED
) -> pd.DataFrame:
    """Paired bootstrap of PR-AUC: every resample uses the SAME orders for every model.

    Returns each model's PR-AUC with a 95% CI, plus the CI of each model's difference from
    the first model in `scores` (if that CI excludes 0, the gap is unlikely to be noise).
    """
    rng = np.random.default_rng(seed)
    names = list(scores)
    draws = {name: [] for name in names}
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if y[idx].sum() == 0:
            continue
        for name in names:
            draws[name].append(average_precision_score(y[idx], scores[name][idx]))
    ref = np.array(draws[names[0]])
    rows = []
    for name in names:
        d = np.array(draws[name])
        diff = d - ref
        rows.append(
            {
                "model": name,
                "pr_auc": average_precision_score(y, scores[name]),
                "ci_low": np.quantile(d, 0.025),
                "ci_high": np.quantile(d, 0.975),
                f"diff_vs_{names[0]}_low": np.quantile(diff, 0.025),
                f"diff_vs_{names[0]}_high": np.quantile(diff, 0.975),
            }
        )
    return pd.DataFrame(rows).set_index("model")


def fit_rule(x_tr: pd.DataFrame, y_tr: np.ndarray, feature: str) -> dict:
    """A one-feature ranking rule; its direction and missing-value fill come from TRAINING data."""
    fill = float(x_tr[feature].median())
    s = x_tr[feature].astype(float).fillna(fill).to_numpy()
    direction = 1 if average_precision_score(y_tr, s) >= average_precision_score(y_tr, -s) else -1
    return {"feature": feature, "direction": direction, "fill": fill}


def rule_score(x: pd.DataFrame, rule: dict) -> np.ndarray:
    """Score orders with a fitted one-feature rule (higher = riskier)."""
    return rule["direction"] * x[rule["feature"]].astype(float).fillna(rule["fill"]).to_numpy()


def rule_baselines(x_tr, y_tr, x_va, y_va, features) -> tuple[pd.DataFrame, dict]:
    """Fit one rule per numeric feature on train; rank them by validation PR-AUC."""
    rows, rules = [], {}
    for feature in features:
        rule = fit_rule(x_tr, y_tr, feature)
        rules[feature] = rule
        rows.append(
            {
                "feature": feature,
                "higher_means": "more risk" if rule["direction"] > 0 else "less risk",
                "valid_pr_auc": average_precision_score(y_va, rule_score(x_va, rule)),
            }
        )
    table = pd.DataFrame(rows).sort_values("valid_pr_auc", ascending=False, ignore_index=True)
    return table, rules[table.loc[0, "feature"]]


def segment_metrics(
    segment: pd.Series, y: np.ndarray, p: np.ndarray, threshold: float, min_late: int = 20
) -> pd.DataFrame:
    """Per-segment late rate, mean predicted risk, recall/precision at the threshold, PR-AUC.

    Segments with fewer than `min_late` late orders get no PR-AUC (too few to be reliable).
    """
    df = pd.DataFrame({"segment": segment.to_numpy(), "y": y, "p": p, "flag": p >= threshold})
    rows = []
    for name, g in df.groupby("segment", observed=True):
        late = int(g["y"].sum())
        flagged = int(g["flag"].sum())
        rows.append(
            {
                "segment": name,
                "orders": len(g),
                "late": late,
                "late_rate": g["y"].mean(),
                "mean_predicted": g["p"].mean(),
                "recall": (g["flag"] & (g["y"] == 1)).sum() / late if late else np.nan,
                "precision": (g["flag"] & (g["y"] == 1)).sum() / flagged if flagged else np.nan,
                "pr_auc": average_precision_score(g["y"], g["p"]) if late >= min_late else np.nan,
            }
        )
    return pd.DataFrame(rows).set_index("segment")


def classification_summary(
    y: np.ndarray, p: np.ndarray, threshold: float, cost_fn: float = 5.0, cost_fp: float = 1.0
) -> dict[str, float]:
    """Threshold-based metrics for one model: accuracy, precision, recall, F1 and business cost.

    precision / F1 are 0 (not an error) when the model flags nothing, e.g. "always on time".
    """
    flag = (p >= threshold).astype(int)
    tp = int(((flag == 1) & (y == 1)).sum())
    fp = int(((flag == 1) & (y == 0)).sum())
    fn = int(((flag == 0) & (y == 1)).sum())
    tn = int(((flag == 0) & (y == 0)).sum())
    cost = cost_fn * fn + cost_fp * fp
    return {
        "accuracy": accuracy_score(y, flag),
        "precision": precision_score(y, flag, zero_division=0),
        "recall": recall_score(y, flag, zero_division=0),
        "f1": f1_score(y, flag, zero_division=0),
        "flagged_pct": 100 * flag.mean(),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "cost_vs_flag_none": cost / (cost_fn * (tp + fn)) if tp + fn else float("nan"),
    }


def learning_curve_scores(
    make_model, x_tr, y_tr, x_va, y_va, fractions=(0.1, 0.2, 0.4, 0.6, 0.8, 1.0), seed: int = SEED
) -> pd.DataFrame:
    """Train on growing random shares of the training data; score on train and validation.

    ROC-AUC is used for the train-vs-validation gap because, unlike PR-AUC, it doesn't move
    with the base rate (5.65% late in train vs 12.88% in validation).
    A large, persistent gap = overfitting; both low and flat = limited signal (underfitting).
    """
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(y_tr))
    rows = []
    for frac in fractions:
        idx = order[: int(round(frac * len(y_tr)))]
        model = make_model().fit(x_tr.iloc[idx], y_tr[idx])
        rows.append(
            {
                "train_share": frac,
                "train_rows": len(idx),
                "train_roc_auc": roc_auc_score(
                    y_tr[idx], model.predict_proba(x_tr.iloc[idx])[:, 1]
                ),
                "valid_roc_auc": roc_auc_score(y_va, model.predict_proba(x_va)[:, 1]),
            }
        )
    return pd.DataFrame(rows)
