from rag import rerank as rerank_module


class _FakeCrossEncoder:
    def __init__(self, scores):
        self._scores = scores

    def rerank(self, query, documents):
        return iter(self._scores)


def test_rerank_reorders_by_score_and_caps_at_top_k(monkeypatch):
    candidates = [
        {"chunk_id": "a", "text": "a", "distance": 0.1},
        {"chunk_id": "b", "text": "b", "distance": 0.2},
        {"chunk_id": "c", "text": "c", "distance": 0.3},
    ]
    # The cross-encoder disagrees with retrieval order: "b" should win despite
    # being retrieved last.
    monkeypatch.setattr(rerank_module, "_get_reranker", lambda: _FakeCrossEncoder([0.1, 0.9, 0.5]))

    result = rerank_module.rerank("query", candidates, top_k=2)

    assert [r["chunk_id"] for r in result] == ["b", "c"]
    assert result[0]["rerank_score"] == 0.9


def test_rerank_preserves_retrieval_fields_alongside_the_new_score(monkeypatch):
    candidates = [{"chunk_id": "a", "text": "a", "distance": 0.1, "bm25_score": 3.0}]
    monkeypatch.setattr(rerank_module, "_get_reranker", lambda: _FakeCrossEncoder([0.7]))

    result = rerank_module.rerank("query", candidates, top_k=5)

    assert result[0]["distance"] == 0.1
    assert result[0]["bm25_score"] == 3.0
    assert result[0]["rerank_score"] == 0.7


def test_rerank_skips_model_load_for_empty_candidates(monkeypatch):
    def _fail():
        raise AssertionError("reranker should not be loaded for an empty candidate list")

    monkeypatch.setattr(rerank_module, "_get_reranker", _fail)

    assert rerank_module.rerank("query", [], top_k=5) == []
