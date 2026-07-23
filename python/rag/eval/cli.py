"""CLI: compare semantic / bm25 / hybrid / rerank retrieval quality on a labeled eval set.

Usage:
    PYTHONPATH=python python3 -m rag.eval.cli path/to/eval_set.json
    PYTHONPATH=python python3 -m rag.eval.cli path/to/eval_set.json --method hybrid --k 10 -v

Requires pages to already be indexed locally (via the index_confluence_pages MCP
tool) — this only queries the existing index, it doesn't need Confluence credentials.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from rag.eval.harness import evaluate, load_eval_set


def _methods() -> Dict[str, Any]:
    # Imported lazily so `--help` doesn't require fastembed/chromadb/rank_bm25 installed.
    from rag.bm25_index import bm25_search
    from rag.hybrid import hybrid_search
    from rag.rerank import rerank_search
    from rag.retrieve import semantic_search

    return {
        "semantic": lambda query, k: semantic_search(query, top_k=k),
        "bm25": lambda query, k: bm25_search(query, top_k=k),
        "hybrid": lambda query, k: hybrid_search(query, top_k=k, candidate_k=max(k, 20)),
        "rerank": lambda query, k: rerank_search(query, top_k=k, candidate_k=max(k, 20)),
    }


def main(argv: List[str] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("eval_set", type=Path, help="Path to a JSON eval set (see eval_set.example.json)")
    parser.add_argument("--k", type=int, default=5, help="Recall@k / cutoff for ranking metrics (default: 5)")
    parser.add_argument(
        "--method",
        choices=["semantic", "bm25", "hybrid", "rerank", "all"],
        default="all",
        help="Which retrieval method to evaluate (default: all, for side-by-side comparison)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print per-query results too")
    args = parser.parse_args(argv)

    cases = load_eval_set(args.eval_set)
    all_methods = _methods()
    methods = all_methods if args.method == "all" else {args.method: all_methods[args.method]}

    print(f"{len(cases)} eval case(s), k={args.k}\n")
    print(f"{'method':10s} {'recall@k':>10s} {'mrr':>8s}")
    for name, fn in methods.items():
        result = evaluate(cases, lambda q, fn=fn: fn(q, args.k), k=args.k)
        print(f"{name:10s} {result['mean_recall_at_k']:>10.3f} {result['mrr']:>8.3f}")

        if args.verbose:
            for case in result["cases"]:
                print(
                    f"    [{case['recall_at_k']:.2f} / {case['reciprocal_rank']:.2f}] "
                    f"{case['query']!r} -> expected {case['expected_page_ids']}, "
                    f"got {case['retrieved_page_ids']}"
                )


if __name__ == "__main__":
    main()
