"""Deterministic semantic ranking backends."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol


class Embedder(Protocol):
    """Text embedder interface."""

    name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts as vectors."""


class SentenceBertEmbedder:
    """Lazy Sentence-BERT embedder used for reported experiments."""

    name = "sbert"

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise ImportError(
                "Sentence-BERT requires the optional dependency: "
                "pip install -e 'component4[semantic]'"
            ) from error
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return normalized Sentence-BERT vectors."""
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]


class LexicalEmbedder:
    """Deterministic character 3-gram and token TF embedder for tests."""

    name = "lexical"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return L2-normalized sparse lexical vectors."""
        features = [self._features(text) for text in texts]
        vocabulary = sorted({key for item in features for key in item})
        vectors = [[item.get(key, 0.0) for key in vocabulary] for item in features]
        return [_normalize(vector) for vector in vectors]

    @staticmethod
    def _features(text: str) -> Counter[str]:
        normalized = " ".join(text.lower().split())
        tokens = normalized.split()
        features = Counter(tokens)
        compact = f"  {normalized}  "
        features.update(compact[index : index + 3] for index in range(max(0, len(compact) - 2)))
        return features


def cosine(first: list[float], second: list[float]) -> float:
    """Return cosine similarity for two vectors."""
    if not first or not second:
        return 0.0
    return sum(left * right for left, right in zip(first, second))


def rank(query_text: str, candidates: list[tuple[int, str]], embedder: Embedder) -> list[tuple[int, float]]:
    """Rank candidates by descending similarity and document order."""
    vectors = embedder.embed([query_text] + [text for _, text in candidates])
    query = vectors[0]
    ranked = [
        (index, cosine(query, vector))
        for (index, _), vector in zip(candidates, vectors[1:])
    ]
    return sorted(ranked, key=lambda item: (-item[1], item[0]))


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else [0.0 for _ in vector]
