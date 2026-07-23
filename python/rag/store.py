"""Local persistent vector store (Chroma) for indexed Confluence chunks.

Keeping this behind a thin module (rather than calling chromadb directly from
server.py) is what will let a future reranking step re-query the same index
without changing the ingestion or MCP tool layer.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from rag.types import Chunk

_DEFAULT_INDEX_DIR = "data/rag_index"
_COLLECTION_NAME = "confluence_chunks"

_client = None
_collection = None


def _index_dir() -> Path:
    # python/rag/store.py -> python/rag -> python -> repo root
    workspace_root = Path(__file__).resolve().parents[2]
    configured = os.getenv("RAG_INDEX_DIR", _DEFAULT_INDEX_DIR)
    path = Path(configured)
    if not path.is_absolute():
        path = workspace_root / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_collection():
    global _client, _collection
    if _collection is None:
        import chromadb

        _client = chromadb.PersistentClient(path=str(_index_dir()))
        _collection = _client.get_or_create_collection(_COLLECTION_NAME)
    return _collection


def upsert_chunks(chunks: List[Chunk], embeddings: List[List[float]]) -> int:
    if not chunks:
        return 0
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must be the same length")

    collection = _get_collection()
    collection.upsert(
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "page_id": c.page_id,
                "title": c.title,
                "space_key": c.space_key or "",
                "url": c.url,
                "heading_path": c.heading_path,
                "order": c.order,
                "updated": c.updated or "",
            }
            for c in chunks
        ],
    )
    return len(chunks)


def delete_page(page_id: str) -> None:
    """Remove all previously indexed chunks for a page (used before re-indexing it)."""
    collection = _get_collection()
    collection.delete(where={"page_id": page_id})


def get_all_chunks(space_key: Optional[str] = None) -> Dict[str, List[Any]]:
    """Return every indexed chunk's id/text/metadata, optionally filtered by space_key.

    Used by the local BM25 index (rag/bm25_index.py), which rebuilds its corpus from
    this on every query rather than maintaining a second persisted index — so it can
    never drift out of sync with what's actually in the vector store.
    """
    collection = _get_collection()
    where = {"space_key": space_key} if space_key else None
    return collection.get(where=where, include=["documents", "metadatas"])


def query(embedding: List[float], top_k: int = 5, space_key: Optional[str] = None) -> List[Dict[str, Any]]:
    collection = _get_collection()
    where = {"space_key": space_key} if space_key else None
    result = collection.query(query_embeddings=[embedding], n_results=top_k, where=where)

    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    hits: List[Dict[str, Any]] = []
    for i, chunk_id in enumerate(ids):
        hit = {"chunk_id": chunk_id, "text": docs[i], "distance": distances[i]}
        hit.update(metadatas[i])
        hits.append(hit)
    return hits
