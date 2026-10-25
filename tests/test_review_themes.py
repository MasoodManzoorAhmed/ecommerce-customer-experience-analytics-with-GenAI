"""Module 2 (review themes): taxonomy, label parsing, scoring and the gold/train split."""

import pandas as pd
import pytest

from genai.review_themes.data import RESULTS, TAXONOMY, THEMES
from genai.review_themes.evaluate import score
from genai.review_themes.llm_labeler import parse_labels, system_prompt
from genai.review_themes.tfidf import normalise


def test_precedence_lists_every_theme_once():
    assert sorted(TAXONOMY["precedence"]) == sorted(THEMES)
    assert TAXONOMY["precedence"][-1] == "other"


def test_prompt_names_every_theme():
    prompt = system_prompt()
    assert all(t in prompt for t in THEMES)


def test_parse_labels_handles_chatter_unknown_and_missing():
    reply = 'Sure!\n[{"id": 1, "theme": "damaged"}, {"id": 3, "theme": "spam"}]'
    assert parse_labels(reply, 3) == ["damaged", "other", "other"]
    assert parse_labels("no json here", 2) == ["other", "other"]
    assert parse_labels("[not json]", 1) == ["other"]
    cut_off = '[{"id": 1, "theme": "damaged"}, {"id": 2, "theme": "late_del'
    assert parse_labels(cut_off, 2) == ["damaged", "other"]


def test_macro_f1_weights_themes_equally():
    gold = pd.Series(["other"] * 9 + ["damaged"])
    pred = pd.Series(["other"] * 10)  # 90% accurate, but misses the rare theme
    out = score(gold, pred)
    assert out["accuracy"] == pytest.approx(0.9)
    assert out["macro_f1"] < 0.2  # (0.947 + 0) / 6 themes


def test_normalise_strips_accents_and_case():
    assert normalise("NÃO Recebi") == "nao recebi"


@pytest.mark.skipif(not (RESULTS / "gold_labels.csv").exists(), reason="split not built")
def test_gold_labels_are_valid_and_separate_from_train():
    gold = pd.read_csv(RESULTS / "gold_labels.csv")
    train = pd.read_csv(RESULTS / "train_reviews.csv")
    assert len(gold) == 200 and gold["review_id"].is_unique
    assert set(gold["theme"]) <= set(THEMES)
    assert not set(gold["order_id"]) & set(train["order_id"])


def test_app_theme_helpers_share_and_mix():
    from app.metrics import THEME_LABELS, theme_by_situation, theme_shares

    df = pd.DataFrame(
        {
            "theme": ["never_arrived", "never_arrived", "damaged", "other"],
            "situation": ["late", "not delivered", "on time", "on time"],
        }
    )
    shares = theme_shares(df)
    assert shares.iloc[0]["theme"] == "never_arrived" and shares["share"].sum() == 1
    assert shares.iloc[0]["label"] == THEME_LABELS["never_arrived"]
    mix = theme_by_situation(df)
    assert list(mix.index) == ["on time", "late", "not delivered"]  # fixed display order
    assert mix.loc["on time", "damaged"] == 0.5
    assert all(abs(mix.sum(axis=1) - 1) < 1e-9)
