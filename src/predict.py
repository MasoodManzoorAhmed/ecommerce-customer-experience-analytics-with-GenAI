"""Scoring with the saved late-delivery model: probabilities, risk bands, explanations."""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

from src.features import FEATURES
from src.train import MODELS_DIR


def load_model(name: str = "late_delivery_model"):
    """Return (model, metadata) from models/."""
    model = joblib.load(MODELS_DIR / f"{name}.pkl")
    metadata = json.loads((MODELS_DIR / "metadata.json").read_text(encoding="utf-8"))
    return model, metadata


def risk_band(p: np.ndarray, threshold: float) -> np.ndarray:
    """high = at/above the cost-based threshold; medium = at least half of it; low = below."""
    return np.select([p >= threshold, p >= threshold / 2], ["high", "medium"], default="low")


def linear_contributions(pipeline, x: pd.DataFrame) -> pd.DataFrame:
    """Exact SHAP values for the logistic-regression pipeline, grouped to original features.

    For a linear model, SHAP value = coefficient * (transformed value - training mean of the
    transformed value), in log-odds. One-hot and missing-indicator columns are summed back
    into the feature they came from, so each original feature gets one number.
    """
    pre, model = pipeline.named_steps["pre"], pipeline.named_steps["model"]
    z = pre.transform(x)
    z = z.toarray() if hasattr(z, "toarray") else np.asarray(z)
    mean = np.asarray(pipeline.train_mean_, dtype=float)
    contrib = (z - mean) * model.coef_[0]
    names = pre.get_feature_names_out()
    groups = [_original_feature(n) for n in names]
    df = pd.DataFrame(contrib, columns=names, index=x.index)
    return df.T.groupby(groups).sum().T[FEATURES]


def _original_feature(transformed_name: str) -> str:
    """'num__missingindicator_seller_late_rate_90d' -> 'seller_late_rate_90d', etc."""
    name = transformed_name.split("__", 1)[1]
    name = name.removeprefix("missingindicator_")
    for feature in sorted(FEATURES, key=len, reverse=True):
        if name == feature or name.startswith(feature + "_"):
            return feature
    raise KeyError(transformed_name)


def top_drivers(contrib: pd.DataFrame, k: int = 3) -> list[str]:
    """The k features with the largest absolute contribution per order, as text."""
    values, cols = contrib.to_numpy(), np.array(contrib.columns)
    top = np.argsort(-np.abs(values), axis=1)[:, :k]
    return [
        "; ".join(f"{cols[j]} ({values[i, j]:+.2f})" for j in top[i]) for i in range(len(values))
    ]
