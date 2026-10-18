"""Statistical tests with effect sizes, used by the EDA notebook.

Each function returns a plain dict so results can be shown as a table and logged.
A p-value says whether a difference is likely real; the effect size says how big it is.
With ~95k orders almost everything is "significant", so effect sizes carry the story.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd
from scipy import stats

SEED = 42


def mann_whitney(a: Sequence[float], b: Sequence[float]) -> dict[str, float]:
    """Two-sided Mann-Whitney U test of a vs b, with rank-biserial correlation.

    rank_biserial = P(a > b) - P(a < b): +1 means every a beats every b, 0 means no difference.
    Suited to ordinal, skewed data such as 1-5 star review scores (no normality assumption).
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    u_a, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {
        "n_a": len(a),
        "n_b": len(b),
        "mean_a": float(a.mean()),
        "mean_b": float(b.mean()),
        "median_a": float(np.median(a)),
        "median_b": float(np.median(b)),
        "u_statistic": float(u_a),
        "p_value": float(p),
        "rank_biserial": float(2 * u_a / (len(a) * len(b)) - 1),
    }


def bootstrap_diff_ci(
    a: Sequence[float],
    b: Sequence[float],
    stat: Callable[[np.ndarray], float] = np.mean,
    n_boot: int = 2000,
    level: float = 0.95,
    seed: int = SEED,
) -> dict[str, float]:
    """Percentile bootstrap confidence interval for stat(a) - stat(b)."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    diffs = np.array(
        [
            stat(rng.choice(a, len(a), replace=True)) - stat(rng.choice(b, len(b), replace=True))
            for _ in range(n_boot)
        ]
    )
    alpha = (1 - level) / 2
    return {
        "diff": float(stat(a) - stat(b)),
        "ci_low": float(np.quantile(diffs, alpha)),
        "ci_high": float(np.quantile(diffs, 1 - alpha)),
        "level": level,
        "n_boot": n_boot,
    }


def chi_square(table: pd.DataFrame) -> dict[str, float]:
    """Chi-square test of independence, with Cramer's V effect size (0 = none, 1 = perfect)."""
    chi2, p, dof, _ = stats.chi2_contingency(table.to_numpy())
    n = table.to_numpy().sum()
    k = min(table.shape) - 1
    return {
        "chi2": float(chi2),
        "p_value": float(p),
        "dof": int(dof),
        "cramers_v": float(np.sqrt(chi2 / (n * k))) if k > 0 else 0.0,
    }


def kruskal(groups: dict[str, Sequence[float]]) -> dict[str, float]:
    """Kruskal-Wallis H test across several groups, with epsilon-squared effect size (0..1)."""
    arrays = [np.asarray(g, dtype=float) for g in groups.values()]
    h, p = stats.kruskal(*arrays)
    n = sum(len(g) for g in arrays)
    return {"h_statistic": float(h), "p_value": float(p), "epsilon_squared": float(h / (n - 1))}


def spearman(x: Sequence[float], y: Sequence[float]) -> dict[str, float]:
    """Spearman rank correlation (monotonic relationship, robust to outliers)."""
    rho, p = stats.spearmanr(x, y)
    return {"rho": float(rho), "p_value": float(p), "n": len(x)}
