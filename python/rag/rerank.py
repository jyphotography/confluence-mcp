"""Cross-encoder reranking over hybrid-search candidates.

Retrieval (BM25 + vector, fused by RRF) is optimized for recall over a candidate
set; a cross-encoder scores each (query, candidate) pair jointly, which is slower
per-pair but far more precise, so it's used to re-order a small candidate set
rather than to search the whole index. Runs locally via fastembed's ONNX
cross-encoder support (no external API key, consistent with rag/embeddings.py).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from rag.hybrid import hybrid_search

_DEFAULT_RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _get_reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    model_name = os.getenv("RAG_RERANK_MODEL", _DEFAULT_RERANK_MODEL)
    return TextCrossEncoder(model_name=model_name)


def rerank(query_text: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """Re-score and re-order candidates for a query. Adds a `rerank_score` field."""
    if not candidates:
        return []

    model = _get_reranker()
    scores = list(model.rerank(query_text, [c["text"] for c in candidates]))

    scored = [{**candidate, "rerank_score": float(score)} for candidate, score in zip(candidates, scores)]
    scored.sort(key=lambda c: c["rerank_score"], reverse=True)
    return scored[:top_k]


def rerank_search(
    query_text: str,
    top_k: int = 5,
    space_key: Optional[str] = None,
    candidate_k: int = 20,
) -> List[Dict[str, Any]]:
    """Hybrid-search for `candidate_k` candidates, then cross-encoder rerank to `top_k`."""
    candidates = hybrid_search(query_text, top_k=candidate_k, space_key=space_key, candidate_k=candidate_k)
    return rerank(query_text, candidates, top_k=top_k)
