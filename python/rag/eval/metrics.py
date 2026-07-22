"""Pure ranking-quality metrics, independent of how the ranked list was produced.

Matching is done at page level, not chunk level: an eval case says "this query
should surface page X", not "this exact chunk", since that's the granularity a
human labeling queries against real pages would naturally reason in.
"""

from __future__ import annotations

from typing import Iterable, List, Set


def recall_at_k(expected_page_ids: Set[str], retrieved_page_ids: List[str], k: int) -> float:
    """Fraction of expected pages present anywhere in the top-k retrieved page IDs."""
    if not expected_page_ids:
        return 0.0
    top_k = set(retrieved_page_ids[:k])
    return len(expected_page_ids & top_k) / len(expected_page_ids)


def reciprocal_rank(expected_page_ids: Set[str], retrieved_page_ids: List[str]) -> float:
    """1/rank of the first retrieved page that's in expected_page_ids, else 0."""
    for rank, page_id in enumerate(retrieved_page_ids, start=1):
        if page_id in expected_page_ids:
            return 1.0 / rank
    return 0.0


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
