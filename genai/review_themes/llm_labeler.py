"""LLM theme labelling: used for the zero-shot approach AND to create training labels.

Reviews are sent in batches (20 per request) with the taxonomy definitions and precedence
rule; the model answers with a JSON list of {"id", "theme"}. Batching keeps a free/local model
fast (and inside any request quota); every reply is cached by the LLM client.

    python -m genai.review_themes.llm_labeler gold     # zero-shot predictions on the gold set
    python -m genai.review_themes.llm_labeler train    # training labels for TF-IDF / LoRA
    python -m genai.review_themes.llm_labeler second   # independent 2nd annotator on gold
"""

from __future__ import annotations

import json
import re
import sys

import yaml

from genai.review_themes.data import RESULTS, TAXONOMY, THEMES, read_split
from genai.text_to_sql.llm_client import LLMClient

MODEL = "ollama/qwen2.5-coder-16k"
SECOND = "cohere/north-mini-code:free"  # a different model family, for the agreement check
CACHE = RESULTS / "llm_cache.jsonl"
BATCH = 20

SYSTEM = """You classify Brazilian e-commerce customer reviews (in Portuguese)
into ONE complaint theme.

Themes (definition and typical Portuguese cues):
{themes}

If a review mentions several problems, choose the first theme in this order that applies:
{precedence}

Reply with ONLY a JSON list, one object per review, in the same order:
[{{"id": <review number>, "theme": "<theme name>"}}, ...]
Use only these theme names: {names}."""


def system_prompt() -> str:
    themes = yaml.safe_dump(TAXONOMY["themes"], allow_unicode=True, sort_keys=False)
    return SYSTEM.format(
        themes=themes,
        precedence=" > ".join(TAXONOMY["precedence"]),
        names=", ".join(THEMES),
    )


PAIR = re.compile(r'\{\s*"id"\s*:\s*"?(\d+)"?\s*,\s*"theme"\s*:\s*"([^"]+)"\s*\}')


def parse_labels(text: str, n: int) -> list[str]:
    """Theme per review from the model's JSON; unknown or missing answers become 'other'.
    Reads each {"id", "theme"} pair on its own, so a reply cut off mid-list still keeps
    every complete answer before the cut."""
    labels = ["other"] * n
    for num, theme in PAIR.findall(text):
        i, theme = int(num) - 1, theme.strip()
        if 0 <= i < n and theme in THEMES:
            labels[i] = theme
    return labels


def max_tokens(model: str) -> int:
    """Hosted free models "think" before answering and the thinking counts towards the
    limit, so they get a bigger budget than the local model (which answers directly)."""
    return 1500 if model.startswith("ollama/") else 6000


def label_reviews(texts: list[str], model: str = MODEL) -> tuple[list[str], dict]:
    """Label texts in batches; returns the labels and simple run statistics."""
    client = LLMClient(model=model, cache_path=CACHE)
    system = system_prompt()
    labels, latency, tokens, unparsed = [], 0.0, 0, 0
    for start in range(0, len(texts), BATCH):
        batch = texts[start : start + BATCH]
        body = "\n".join(f"{i}. {t[:600]}" for i, t in enumerate(batch, start=1))
        reply = client.complete(
            [{"role": "system", "content": system}, {"role": "user", "content": body}],
            max_tokens=max_tokens(model),
        )
        batch_labels = parse_labels(reply.text, len(batch))
        unparsed += int(len(PAIR.findall(reply.text)) < len(batch))
        labels += batch_labels
        latency += reply.latency_s
        tokens += reply.prompt_tokens + reply.completion_tokens
        print(f"  {start + len(batch):>5}/{len(texts)}", flush=True)
    stats = {
        "reviews": len(texts),
        "requests": -(-len(texts) // BATCH),
        "seconds_per_review": latency / max(len(texts), 1),
        "tokens_per_review": tokens / max(len(texts), 1),
        "incomplete_batches": unparsed,
    }
    return labels, stats


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "gold"
    if which == "second":  # independent second annotator for the gold-label agreement check
        df, model, path = read_split("gold"), SECOND, "second_annotator_gold"
    elif which == "gold":
        df, model, path = read_split("gold"), MODEL, "zero_shot_gold"
    else:
        df, model, path = read_split("train"), MODEL, "train_llm_labels"
    labels, stats = label_reviews(df["text"].tolist(), model=model)
    out = df[["review_id"]].assign(theme=labels)
    out.to_csv(RESULTS / f"{path}.csv", index=False)
    stats["model"] = model
    (RESULTS / f"llm_stats_{which}.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    print(out["theme"].value_counts().to_string())
    print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
