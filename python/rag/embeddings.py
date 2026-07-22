"""Local text embeddings via fastembed (ONNX runtime, no GPU/torch, no external API key).

The model is downloaded once to a local cache on first use. Override with
RAG_EMBEDDING_MODEL to swap in a different fastembed-supported model.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List

_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


@lru_cache(maxsize=1)
def _get_model():
    from fastembed import TextEmbedding

    model_name = os.getenv("RAG_EMBEDDING_MODEL", _DEFAULT_MODEL)
    return TextEmbedding(model_name=model_name)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts. Returns one vector per input text, same order."""
    if not texts:
        return []
    model = _get_model()
    return [vector.tolist() for vector in model.embed(texts)]


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]
