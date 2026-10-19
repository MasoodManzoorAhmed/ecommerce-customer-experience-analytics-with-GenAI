"""Tests for the robustness helpers in src/train.py (synthetic data)."""

import numpy as np
import pandas as pd

from src.train import bootstrap_pr_auc, fit_rule, rule_score, segment_metrics


def test_bootstrap_is_paired_and_reproducible():
    rng = np.random.default_rng(1)
    y = (rng.random(2000) < 0.1).astype(int)
    good = y + rng.normal(0, 0.5, 2000)
    noise = rng.normal(0, 1, 2000)
    a = bootstrap_pr_auc(y, {"good": good, "noise": noise}, n_boot=200)
    b = bootstrap_pr_auc(y, {"good": good, "noise": noise}, n_boot=200)
    pd.testing.assert_frame_equal(a, b)
    assert a.loc["good", "ci_low"] <= a.loc["good", "pr_auc"] <= a.loc["good", "ci_high"]
    # the informative score is clearly better: the difference CI is entirely below 0 for noise
    assert a.loc["noise", "diff_vs_good_high"] < 0


def test_rule_direction_learned_from_training_data():
    x = pd.DataFrame({"f": [1.0, 2.0, 3.0, 4.0, np.nan]})
    y = np.array([1, 1, 0, 0, 0])  # LOW values are risky
    rule = fit_rule(x.iloc[:4], y[:4], "f")
    assert rule["direction"] == -1
    scores = rule_score(x, rule)
    assert scores[0] > scores[3]  # value 1 scores riskier than value 4
    assert not np.isnan(scores).any()  # missing filled with the training median


def test_segment_metrics_counts():
    seg = pd.Series(["a", "a", "b", "b"])
    y = np.array([1, 0, 1, 0])
    p = np.array([0.9, 0.1, 0.2, 0.8])
    out = segment_metrics(seg, y, p, threshold=0.5, min_late=1)
    assert out.loc["a", "recall"] == 1.0 and out.loc["b", "recall"] == 0.0
    assert out.loc["b", "precision"] == 0.0
