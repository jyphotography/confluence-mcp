# Semantic Search (RAG)

This adds a local retrieval-augmented-search layer on top of the existing Confluence
keyword search, so the server can answer conceptual queries where the exact wording
doesn't appear in the page text (e.g. "how do we roll back a bad deploy" matching a
page titled "Incident Response Runbook" that never uses the word "rollback").

It is additive: `search_pages` (CQL/keyword) is unchanged and still the better choice
for exact-term or ID-style lookups. `semantic_search_pages` is for meaning-based
lookups. A production setup would typically query both and merge results (hybrid
search) — see [Not yet implemented](#not-yet-implemented) below.

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

Query path is the same embedding step against the query text, then a similarity
query against the same collection (`python/rag/retrieve.py`).

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

## Usage

1. Index some pages (either explicit IDs, or a keyword query to discover them first):
   - MCP tool: `index_confluence_pages` with `page_ids: ["123456"]`, or
     `query: "data pipeline", space_key: "ENG"`
2. Query them: `semantic_search_pages` with `query: "how do we roll back a bad deploy"`

The first call to either tool downloads the embedding model to the local fastembed
cache; subsequent calls are fast. The index persists across server restarts at
`data/rag_index/` (override with `RAG_INDEX_DIR`).

## Not yet implemented

This first pass covers chunking + embedding + retrieval. Planned next:

- **Reranking**: query the vector store for a larger candidate set (e.g. top 20),
  then rerank with a cross-encoder (e.g. a local bge-reranker model or a hosted
  rerank API) before returning the top 5. Retrieval and reranking are already
  separated (`retrieve.py` vs. a future `rerank.py`) so this should be additive.
- **Hybrid search**: merge `search_pages` (CQL) and `semantic_search_pages` results
  instead of treating them as two separate tools, so exact-term and conceptual
  queries both get good recall in one call.
- **Evaluation harness**: a small labeled query → expected-chunk set to track
  Recall@k / MRR as chunking, embedding model, or reranking change, plus an
  LLM-as-judge faithfulness check for `generate_weekly_drafts` output against its
  retrieved/source context.
