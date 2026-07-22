# Semantic Search (RAG)

This adds a local retrieval-augmented-search layer on top of the existing Confluence
keyword search, so the server can answer conceptual queries where the exact wording
doesn't appear in the page text (e.g. "how do we roll back a bad deploy" matching a
page titled "Incident Response Runbook" that never uses the word "rollback").

It is additive: `search_pages` (CQL/keyword against Confluence's own API) is
unchanged and still the right choice for exact-term or ID-style lookups against
pages you haven't indexed. Three new tools operate on the local index instead:

- `semantic_search_pages` — pure vector search
- `bm25_search_pages` — pure local keyword search over the same indexed chunks
  (not Confluence's CQL — see [Why a local BM25 index](#why-a-local-bm25-index-not-confluence-cql))
- `hybrid_search_pages` — the two merged via Reciprocal Rank Fusion; the best
  default once pages are indexed

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
query_text ──────────┤                                       ├── reciprocal_rank_fusion()
                     └─ bm25_search()      rag/bm25_index.py ─┘   rag/hybrid.py
```

`semantic_search_pages` and `bm25_search_pages` each expose one branch directly;
`hybrid_search_pages` runs both (as `candidate_k` candidates each) and fuses them.

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

## Usage

1. Index some pages (either explicit IDs, or a keyword query to discover them first):
   - MCP tool: `index_confluence_pages` with `page_ids: ["123456"]`, or
     `query: "data pipeline", space_key: "ENG"`
2. Query them:
   - `hybrid_search_pages` — combined BM25 + vector, recommended default
   - `semantic_search_pages` — vector only
   - `bm25_search_pages` — local BM25 only

The first call to any of these downloads the embedding model to the local fastembed
cache; subsequent calls are fast. The index persists across server restarts at
`data/rag_index/` (override with `RAG_INDEX_DIR`).

## Not yet implemented

This pass covers chunking + embedding + retrieval + hybrid (BM25 + vector) search.
Planned next:

- **Reranking**: pull a larger candidate set from `hybrid_search_pages` (e.g. top 20
  via `candidate_k`), then rerank with a cross-encoder (e.g. a local bge-reranker
  model or a hosted rerank API) before returning the top 5.
- **Evaluation harness**: a small labeled query → expected-chunk set to track
  Recall@k / MRR across `semantic_search_pages` / `bm25_search_pages` /
  `hybrid_search_pages`, so chunking, embedding model, or reranking changes have a
  number to check against instead of eyeballing results. Also an LLM-as-judge
  faithfulness check for `generate_weekly_drafts` output against its retrieved/source
  context.
