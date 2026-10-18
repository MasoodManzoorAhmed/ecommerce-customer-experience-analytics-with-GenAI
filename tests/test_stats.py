"""Sanity tests for src/stats.py on data with known answers."""

import numpy as np
import pandas as pd

from src.stats import bootstrap_diff_ci, chi_square, kruskal, mann_whitney, spearman


def test_rank_biserial_extremes_and_sign():
    assert mann_whitney([5, 5, 4], [1, 2, 1])["rank_biserial"] == 1.0
    assert mann_whitney([1, 2, 1], [5, 5, 4])["rank_biserial"] == -1.0


def test_identical_groups_show_no_effect():
    res = mann_whitney([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    assert res["rank_biserial"] == 0.0
    assert res["p_value"] > 0.9


def test_bootstrap_is_reproducible_and_covers_true_diff():
    rng = np.random.default_rng(0)
    a, b = rng.normal(1.0, 1, 500), rng.normal(0.0, 1, 500)
    r1, r2 = bootstrap_diff_ci(a, b, n_boot=300), bootstrap_diff_ci(a, b, n_boot=300)
    assert r1 == r2  # fixed seed
    assert r1["ci_low"] < 1.0 < r1["ci_high"]


def test_cramers_v_zero_for_independent_table():
    table = pd.DataFrame([[50, 50], [50, 50]])
    assert chi_square(table)["cramers_v"] == 0.0


def test_kruskal_and_spearman_detect_clear_patterns():
    assert kruskal({"a": [1, 2, 3], "b": [10, 11, 12], "c": [20, 21, 22]})["p_value"] < 0.05
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40])["rho"] == 1.0
