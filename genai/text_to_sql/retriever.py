"""Step c: pick the solved examples most similar to a new question (few-shot retrieval).

Each example question is turned into an embedding: a list of 384 numbers from the
sentence-transformers model all-MiniLM-L6-v2 that captures what the sentence MEANS, so
"revenue in each quarter" lands close to "revenue in each year" even with different words.
Similarity = cosine similarity of the two embeddings (1 = same meaning, 0 = unrelated).
The model is small (about 90 MB), runs on the CPU and is loaded from the local cache, offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import yaml

from src.db import ROOT

EXAMPLES_PATH = ROOT / "genai" / "text_to_sql" / "examples.yaml"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 3


@dataclass(frozen=True)
class Example:
    question: str
    sql: str


def load_examples() -> list[Example]:
    raw = yaml.safe_load(EXAMPLES_PATH.read_text(encoding="utf-8"))["examples"]
    return [Example(" ".join(r["question"].split()), r["sql"].strip()) for r in raw]


@lru_cache(maxsize=1)
def _encoder():
    from sentence_transformers import SentenceTransformer

    try:  # offline: use the copy already in the Hugging Face cache
        return SentenceTransformer(EMBEDDING_MODEL, device="cpu", local_files_only=True)
    except OSError:
        return SentenceTransformer(EMBEDDING_MODEL, device="cpu")


def embed(texts: list[str]) -> np.ndarray:
    """Unit-length embeddings, so a dot product equals cosine similarity."""
    return np.asarray(_encoder().encode(texts, normalize_embeddings=True))


class ExampleRetriever:
    """Embeds the examples once; returns the top-k most similar for each question."""

    def __init__(self, examples: list[Example] | None = None):
        self.examples = examples if examples is not None else load_examples()
        self._vectors = embed([e.question for e in self.examples])

    def top_k(self, question: str, k: int = TOP_K) -> list[tuple[Example, float]]:
        scores = self._vectors @ embed([question])[0]
        best = np.argsort(-scores)[:k]
        return [(self.examples[i], float(scores[i])) for i in best]


@lru_cache(maxsize=1)
def default_retriever() -> ExampleRetriever:
    return ExampleRetriever()


def examples_text(question: str, k: int = TOP_K) -> str:
    """The few-shot block for the prompt: the k most similar solved questions with their SQL."""
    blocks = [
        f"Question: {ex.question}\n```sql\n{ex.sql}\n```"
        for ex, _ in default_retriever().top_k(question, k)
    ]
    return "\n\n".join(blocks)
