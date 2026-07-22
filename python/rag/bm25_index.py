"""Local BM25 keyword ranking over the same chunk corpus indexed in the vector store.

Rebuilt in memory on every query rather than persisted separately. The corpora this
project indexes (a handful of Confluence spaces) are small enough that re-tokenizing
and re-scoring per query is cheap, and it means there's exactly one source of truth
for "what's indexed" (Chroma via rag/store.py) instead of two stores that could drift
apart after edits/deletes.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from rag.store import get_all_chunks

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def bm25_search(query_text: str, top_k: int = 20, space_key: Optional[str] = None) -> List[Dict[str, Any]]:
    from rank_bm25 import BM25Okapi

    corpus = get_all_chunks(space_key=space_key)
    ids = corpus.get("ids") or []
    documents = corpus.get("documents") or []
    metadatas = corpus.get("metadatas") or []

    if not documents:
        return []

    bm25 = BM25Okapi([_tokenize(doc) for doc in documents])
    scores = bm25.get_scores(_tokenize(query_text))

    ranked_indices = sorted(range(len(documents)), key=lambda i: scores[i], reverse=True)[:top_k]

    hits: List[Dict[str, Any]] = []
    for i in ranked_indices:
        if scores[i] <= 0:
            # BM25 gives a 0 score to documents sharing no terms with the query;
            # dropping them keeps pure-keyword misses out of the fused results.
            continue
        hit = {"chunk_id": ids[i], "text": documents[i], "bm25_score": float(scores[i])}
        hit.update(metadatas[i])
        hits.append(hit)
    return hits
