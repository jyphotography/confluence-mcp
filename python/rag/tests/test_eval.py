from rag.eval.harness import EvalCase, evaluate
from rag.eval.metrics import mean, reciprocal_rank, recall_at_k


def test_recall_at_k_counts_expected_pages_found_within_the_cutoff():
    assert recall_at_k({"a"}, ["x", "a", "y"], k=5) == 1.0
    assert recall_at_k({"a"}, ["x", "y", "a"], k=2) == 0.0
    assert recall_at_k({"a", "b"}, ["a", "x", "y"], k=5) == 0.5


def test_recall_at_k_with_no_expected_pages_is_zero_not_undefined():
    assert recall_at_k(set(), ["a", "b"], k=5) == 0.0


def test_reciprocal_rank_of_first_match():
    assert reciprocal_rank({"a"}, ["x", "y", "a"]) == 1.0 / 3
    assert reciprocal_rank({"a"}, ["a", "y"]) == 1.0
    assert reciprocal_rank({"a"}, ["x", "y"]) == 0.0


def test_mean_of_empty_iterable_is_zero():
    assert mean([]) == 0.0
    assert mean([1.0, 0.0, 0.5]) == 0.5


def test_evaluate_aggregates_across_cases_and_dispatches_query_to_search_fn():
    cases = [
        EvalCase(query="q1", expected_page_ids=["a"]),
        EvalCase(query="q2", expected_page_ids=["b"]),
    ]

    fake_results = {
        "q1": [{"page_id": "a", "chunk_id": "a:0"}],
        "q2": [{"page_id": "x", "chunk_id": "x:0"}, {"page_id": "b", "chunk_id": "b:0"}],
    }

    result = evaluate(cases, lambda query: fake_results[query], k=5)

    assert result["num_cases"] == 2
    # q1: hit at rank 1 (recall 1.0, rr 1.0); q2: hit at rank 2 (recall 1.0, rr 0.5)
    assert result["mean_recall_at_k"] == 1.0
    assert result["mrr"] == (1.0 + 0.5) / 2
    assert result["cases"][0]["query"] == "q1"
    assert result["cases"][1]["retrieved_page_ids"] == ["x", "b"]
