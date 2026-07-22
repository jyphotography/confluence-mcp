"""Run a labeled eval set against any retrieval function and score it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

from rag.eval.metrics import mean, reciprocal_rank, recall_at_k


@dataclass
class EvalCase:
    query: str
    expected_page_ids: List[str]
    note: str = ""


def load_eval_set(path: Path) -> List[EvalCase]:
    """Load eval cases from a JSON file: a list of {"query", "expected_page_ids", "note"}."""
    raw = json.loads(Path(path).read_text())
    return [
        EvalCase(
            query=item["query"],
            expected_page_ids=[str(p) for p in item["expected_page_ids"]],
            note=item.get("note", ""),
        )
        for item in raw
    ]


def evaluate(
    cases: List[EvalCase],
    search_fn: Callable[[str], List[Dict[str, Any]]],
    k: int = 5,
) -> Dict[str, Any]:
    """Run `search_fn(query)` for every case and score the results against expected_page_ids.

    `search_fn` should already be bound to whichever retrieval method (and its own
    top-k / space filters) is under evaluation; this just measures ranking quality
    of whatever it returns, truncated to `k`.
    """
    per_case: List[Dict[str, Any]] = []

    for case in cases:
        hits = search_fn(case.query)
        retrieved_page_ids = [hit.get("page_id") for hit in hits]
        expected = set(case.expected_page_ids)

        per_case.append(
            {
                "query": case.query,
                "note": case.note,
                "expected_page_ids": sorted(expected),
                "retrieved_page_ids": retrieved_page_ids[:k],
                "recall_at_k": recall_at_k(expected, retrieved_page_ids, k),
                "reciprocal_rank": reciprocal_rank(expected, retrieved_page_ids),
            }
        )

    return {
        "k": k,
        "num_cases": len(per_case),
        "mean_recall_at_k": mean(c["recall_at_k"] for c in per_case),
        "mrr": mean(c["reciprocal_rank"] for c in per_case),
        "cases": per_case,
    }
