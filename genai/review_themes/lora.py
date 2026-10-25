"""Approach 3: fine-tune a small Portuguese transformer with LoRA, on the LLM labels.

    python -m genai.review_themes.lora train     # ~1,500 reviews, 3 epochs, CPU (~30-60 min)
    python -m genai.review_themes.lora gold      # predict the gold set with the saved adapter

Base model: BERTimbau (neuralmind/bert-base-portuguese-cased, 110M parameters), a BERT
pre-trained on Brazilian Portuguese. LoRA freezes all its weights and trains small
low-rank "adapter" matrices inside the attention layers (plus the new classifier head),
so only ~0.3% of the parameters are updated: it fits on a laptop CPU and the saved adapter
is a few MB. On a free Colab/Kaggle GPU the same script runs in a few minutes.
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd
import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from genai.review_themes.data import DIR, RESULTS, SEED, THEMES, read_split

BASE = "neuralmind/bert-base-portuguese-cased"
ADAPTER = DIR / "adapters" / "bertimbau-lora"
MAX_LEN, BATCH, EPOCHS, LR = 128, 16, 3, 3e-4
LABEL2ID = {t: i for i, t in enumerate(THEMES)}


def load_base():
    tokenizer = AutoTokenizer.from_pretrained(BASE)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE, num_labels=len(THEMES), id2label=dict(enumerate(THEMES)), label2id=LABEL2ID
    )
    return tokenizer, model


def batches(tokenizer, texts: list[str], labels: list[int] | None = None, shuffle=False):
    order = np.random.default_rng(SEED).permutation(len(texts)) if shuffle else range(len(texts))
    order = list(order)
    for start in range(0, len(order), BATCH):
        idx = order[start : start + BATCH]
        enc = tokenizer(
            [texts[i] for i in idx],
            truncation=True,
            max_length=MAX_LEN,
            padding=True,
            return_tensors="pt",
        )
        if labels is not None:
            enc["labels"] = torch.tensor([labels[i] for i in idx])
        yield enc


def train() -> dict:
    torch.manual_seed(SEED)
    df = read_split("train").merge(
        pd.read_csv(RESULTS / "train_llm_labels.csv"), on="review_id", validate="1:1"
    )
    texts, labels = df["text"].tolist(), df["theme"].map(LABEL2ID).tolist()
    tokenizer, base = load_base()
    config = LoraConfig(
        task_type="SEQ_CLS", r=8, lora_alpha=16, lora_dropout=0.1, target_modules=["query", "value"]
    )
    model = get_peft_model(base, config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    # class weights (inverse frequency) so rare themes are not ignored, like class_weight="balanced"
    counts = np.bincount(labels, minlength=len(THEMES)).clip(min=1)
    weights = torch.tensor(len(labels) / (len(THEMES) * counts), dtype=torch.float)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
    optimiser = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR)
    model.train()
    start = time.perf_counter()
    for epoch in range(EPOCHS):
        total_loss, steps = 0.0, 0
        for enc in batches(tokenizer, texts, labels, shuffle=True):
            y = enc.pop("labels")
            loss = loss_fn(model(**enc).logits, y)
            loss.backward()
            optimiser.step()
            optimiser.zero_grad()
            total_loss, steps = total_loss + loss.item(), steps + 1
        print(f"epoch {epoch + 1}/{EPOCHS}  loss {total_loss / steps:.3f}", flush=True)
    model.save_pretrained(ADAPTER)
    tokenizer.save_pretrained(ADAPTER)
    return {
        "base_model": BASE,
        "train_reviews": len(texts),
        "trainable_params": trainable,
        "total_params": total,
        "trainable_share": trainable / total,
        "train_minutes": (time.perf_counter() - start) / 60,
    }


def load_trained():
    tokenizer = AutoTokenizer.from_pretrained(ADAPTER)
    _, base = load_base()
    model = PeftModel.from_pretrained(base, ADAPTER).eval()
    return tokenizer, model


@torch.no_grad()
def predict_with_confidence(texts: list[str]) -> tuple[list[str], list[float]]:
    """Theme per text plus the model's probability for it (softmax of the logits), which
    the cascade uses to decide which reviews to send to the LLM."""
    tokenizer, model = load_trained()
    themes, confidence = [], []
    for enc in batches(tokenizer, texts):
        conf, idx = model(**enc).logits.softmax(-1).max(-1)
        themes += [THEMES[i] for i in idx.tolist()]
        confidence += conf.tolist()
    return themes, confidence


def predict(texts: list[str]) -> list[str]:
    return predict_with_confidence(texts)[0]


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "gold"
    if which == "train":
        stats = train()
        (RESULTS / "lora_train_stats.json").write_text(json.dumps(stats, indent=1))
        print(stats)
    gold = read_split("gold")
    start = time.perf_counter()
    pred = predict(gold["text"].tolist())
    seconds = (time.perf_counter() - start) / len(gold)
    gold[["review_id"]].assign(theme=pred).to_csv(RESULTS / "lora_gold.csv", index=False)
    (RESULTS / "lora_stats.json").write_text(json.dumps({"seconds_per_review": seconds}))
    print(pd.Series(pred).value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
