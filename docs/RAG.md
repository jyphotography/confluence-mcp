# Semantic Search (RAG)

This adds a local retrieval-augmented-search layer on top of the existing Confluence
keyword search, so the server can answer conceptual queries where the exact wording
doesn't appear in the page text (e.g. "how do we roll back a bad deploy" matching a
page titled "Incident Response Runbook" that never uses the word "rollback").

It is additive: `search_pages` (CQL/keyword against Confluence's own API) is
unchanged and still the right choice for exact-term or ID-style lookups against
pages you haven't indexed. Four new tools operate on the local index instead:

- `semantic_search_pages` — pure vector search
- `bm25_search_pages` — pure local keyword search over the same indexed chunks
  (not Confluence's CQL — see [Why a local BM25 index](#why-a-local-bm25-index-not-confluence-cql))
- `hybrid_search_pages` — the two merged via Reciprocal Rank Fusion
- `rerank_search_pages` — `hybrid_search_pages`'s candidates, re-scored by a local
  cross-encoder; highest precision, higher latency. Recommended default when result
  quality matters more than speed.

## Pipeline

```
Confluence page (storage-format XHTML)
        │
        ▼
  chunk_confluence_storage()   python/rag/chunker.py
  heading-aware split, ~350 words/chunk, 50-word overlap
        │
        ▼
  embed_texts()                python/rag/embeddings.py
  fastembed, local ONNX model (BAAI/bge-small-en-v1.5 by default)
        │
        ▼
  upsert_chunks()               python/rag/store.py
  Chroma PersistentClient, stored at data/rag_index/ (gitignored)
```

At query time:

```
                     ┌─ semantic_search()  rag/retrieve.py  ─┐
query_text ──────────┤                                       ├── reciprocal_rank_fusion() ── rerank()
                     └─ bm25_search()      rag/bm25_index.py ─┘   rag/hybrid.py             rag/rerank.py
```

`semantic_search_pages` and `bm25_search_pages` each expose one branch directly;
`hybrid_search_pages` runs both (as `candidate_k` candidates each) and fuses them;
`rerank_search_pages` takes hybrid's fused candidates and re-scores them with a
cross-encoder before truncating to `top_k`.

### Why heading-aware chunking

Confluence's storage representation is an XHTML *fragment*, so a page's headings,
paragraphs, tables, and macros are top-level siblings in document order — no need to
walk a nested DOM. The chunker groups body text under the heading it falls under and
builds a breadcrumb (`"Page Title > Section > Subsection"`) per chunk, so a retrieved
chunk is traceable back to where it lives on the page, not just which page. Sections
longer than `max_words` are further split into overlapping windows so no single chunk
is too large to embed well or too broad to be a precise match.

### Why fastembed + Chroma

Both run fully locally: no external API key, no server process to stand up, and no
GPU/torch dependency (fastembed uses ONNX Runtime). That keeps the tool usable out of
the box for anyone who clones the repo, at the cost of embedding quality/speed you'd
get from a larger hosted model — swap `RAG_EMBEDDING_MODEL` (see `env.example`) if you
want a different fastembed-supported model, or replace `python/rag/embeddings.py` and
`python/rag/store.py` to point at a hosted embedding API / vector DB.

### Why a local BM25 index, not Confluence CQL

The obvious "keyword" half of hybrid search would be the existing `search_pages`
(Confluence's CQL search). It isn't used here because RRF fusion needs a *rank* per
list, and Confluence's search API doesn't return one on a scale that's meaningful to
fuse with vector distances — and it's a second network round-trip per query with its
own latency and rate limits. `rag/bm25_index.py` instead runs `rank_bm25`
(`BM25Okapi`) directly over the chunk text already sitting in Chroma, rebuilding the
corpus from `store.get_all_chunks()` on every call rather than persisting a second
index — for the corpus sizes this project targets (a handful of spaces), retokenizing
per query is cheap and guarantees BM25 never drifts out of sync with what's actually
indexed. The tradeoff: it only searches pages you've explicitly indexed, unlike
`search_pages`, which searches all of Confluence.

### RRF, not a weighted score blend

Vector distance and BM25 score live on incomparable scales (and BM25's scale shifts
with corpus size), so averaging them directly would be arbitrary. Reciprocal Rank
Fusion (`rag/hybrid.py`) sidesteps that by fusing on *rank* instead of raw score: each
list contributes `1 / (60 + rank)` to a chunk's fused score, so a chunk ranked highly
by either ranker — and especially one ranked highly by both — floats to the top,
without needing the two scores to be normalized against each other.

### Why rerank on top of hybrid, instead of just returning hybrid's results

RRF only ever reorders what BM25 and vector search already ranked highly — it can't
notice that a candidate is actually a poor match for the query, because neither
ranker looks at the query and the candidate *together*. A cross-encoder does: it runs
the query and each candidate through the model jointly, which is much more accurate
but too slow to run over an entire index. So `rerank_search_pages` uses hybrid search
to cheaply narrow the whole index down to `candidate_k` plausible candidates, then
spends the expensive joint-scoring step only on that small set
(`fastembed.rerank.cross_encoder.TextCrossEncoder`, default model
`Xenova/ms-marco-MiniLM-L-6-v2`, same "local, no API key" approach as the embedding
model).

## Usage

1. Index some pages (either explicit IDs, or a keyword query to discover them first):
   - MCP tool: `index_confluence_pages` with `page_ids: ["123456"]`, or
     `query: "data pipeline", space_key: "ENG"`
2. Query them, in increasing order of precision (and latency):
   - `bm25_search_pages` / `semantic_search_pages` — single-ranker, mainly useful for
     comparison/debugging
   - `hybrid_search_pages` — combined BM25 + vector via RRF
   - `rerank_search_pages` — hybrid's candidates, cross-encoder reranked; recommended
     default when quality matters more than latency

The first call to any of these downloads the relevant model (embedding or
cross-encoder) to the local fastembed cache; subsequent calls are fast. The index
persists across server restarts at `data/rag_index/` (override with `RAG_INDEX_DIR`).

## Evaluating retrieval quality

`python/rag/eval/` scores any of the four search methods against a labeled set of
`{query, expected_page_ids}` cases, matching at page level (not exact chunk) since
that's the granularity a human labeling queries against real pages naturally reasons
in. Metrics are Recall@k (what fraction of the expected pages showed up in the top k)
and MRR (how high the first correct page ranked, averaged over all queries) —
`python/rag/eval/metrics.py`.

```bash
# Build your own eval_set.json (see eval_set.example.json for the format) from
# real queries you've tried against your own indexed pages, then:
PYTHONPATH=python python3 -m rag.eval.cli python/rag/eval/eval_set.example.json -v
```

This runs all four methods against the same eval set and prints Recall@k/MRR
side by side, so a chunking, embedding-model, or reranking change has a number to
check against instead of eyeballing a few example queries. There's no eval set
checked into the repo beyond the example/template — it's specific to whatever
Confluence pages you've actually indexed and needs real page IDs to be meaningful.

## Not yet implemented

- **LLM-as-judge faithfulness check**: score `generate_weekly_drafts` output against
  its retrieved/source Jira + Confluence context, to catch drafts that state things
  the source data doesn't support. This is a different kind of eval than
  Recall@k/MRR above — it's about generation, not retrieval.
