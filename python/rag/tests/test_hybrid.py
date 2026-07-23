from rag.hybrid import reciprocal_rank_fusion


def _hit(chunk_id, **extra):
    return {"chunk_id": chunk_id, "text": f"text-{chunk_id}", **extra}


def test_chunk_found_by_both_rankers_outranks_single_ranker_hits():
    vector_hits = [_hit("a", distance=0.1), _hit("b", distance=0.2), _hit("c", distance=0.3)]
    keyword_hits = [_hit("b", bm25_score=5.0), _hit("d", bm25_score=4.0)]

    fused = reciprocal_rank_fusion(
        [vector_hits, keyword_hits], rank_field_names=["vector_rank", "bm25_rank"]
    )

    assert fused[0]["chunk_id"] == "b"
    assert {h["chunk_id"] for h in fused} == {"a", "b", "c", "d"}


def test_fields_from_both_rankers_are_preserved_on_a_shared_hit():
    vector_hits = [_hit("a", distance=0.1)]
    keyword_hits = [_hit("a", bm25_score=9.0)]

    fused = reciprocal_rank_fusion(
        [vector_hits, keyword_hits], rank_field_names=["vector_rank", "bm25_rank"]
    )

    assert fused[0]["distance"] == 0.1
    assert fused[0]["bm25_score"] == 9.0
    assert fused[0]["vector_rank"] == 1
    assert fused[0]["bm25_rank"] == 1


def test_rrf_score_matches_formula():
    fused = reciprocal_rank_fusion([[_hit("a")]], rank_field_names=["vector_rank"], k=60)

    assert fused[0]["rrf_score"] == 1.0 / 61


def test_a_hit_present_in_only_one_list_is_still_returned():
    fused = reciprocal_rank_fusion(
        [[_hit("a")], []], rank_field_names=["vector_rank", "bm25_rank"]
    )

    assert len(fused) == 1
    assert fused[0]["chunk_id"] == "a"
    assert "bm25_rank" not in fused[0]


def test_results_are_sorted_by_descending_fused_score():
    # "high" ranks first in both lists; "low" only appears (second) in the vector list.
    vector_hits = [_hit("high"), _hit("low")]
    keyword_hits = [_hit("high")]

    fused = reciprocal_rank_fusion(
        [vector_hits, keyword_hits], rank_field_names=["vector_rank", "bm25_rank"]
    )

    assert [h["chunk_id"] for h in fused] == ["high", "low"]
