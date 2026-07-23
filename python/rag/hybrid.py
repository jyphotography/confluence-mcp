"""Hybrid retrieval: local BM25 keyword search + vector semantic search, merged by
Reciprocal Rank Fusion (RRF) so results with strong support from either ranker (or
both) surface, without needing the two rankers' raw scores to be on the same scale.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rag.bm25_index import bm25_search
from rag.retrieve import semantic_search

RRF_K = 60  # smoothing constant from the original RRF paper (Cormack et al., 2009)


def reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    *,
    rank_field_names: List[str],
    k: int = RRF_K,
) -> List[Dict[str, Any]]:
    """Merge ranked hit lists (each a list of dicts keyed by 'chunk_id') via RRF.

    Each list contributes 1/(k + rank) to a chunk's fused score; a chunk absent
    from a list simply doesn't get that list's contribution. Fields from every
    list a chunk appears in are preserved (e.g. a chunk found by both rankers
    keeps its vector `distance`, its `bm25_score`, and both rank fields).
    """
    fused: Dict[str, Dict[str, Any]] = {}

    for ranked_list, rank_field in zip(ranked_lists, rank_field_names):
        for rank, hit in enumerate(ranked_list, start=1):
            chunk_id = hit["chunk_id"]
            entry = fused.get(chunk_id)
            if entry is None:
                entry = dict(hit)
                entry["rrf_score"] = 0.0
                fused[chunk_id] = entry
            else:
                for key, value in hit.items():
                    entry.setdefault(key, value)
            entry["rrf_score"] += 1.0 / (k + rank)
            entry[rank_field] = rank

    return sorted(fused.values(), key=lambda hit: hit["rrf_score"], reverse=True)


def hybrid_search(
    query_text: str,
    top_k: int = 5,
    space_key: Optional[str] = None,
    candidate_k: int = 20,
) -> List[Dict[str, Any]]:
    vector_hits = semantic_search(query_text, top_k=candidate_k, space_key=space_key)
    keyword_hits = bm25_search(query_text, top_k=candidate_k, space_key=space_key)

    fused = reciprocal_rank_fusion(
        [vector_hits, keyword_hits],
        rank_field_names=["vector_rank", "bm25_rank"],
    )
    return fused[:top_k]
