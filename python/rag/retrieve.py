"""Query the local vector store for semantically similar Confluence chunks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rag.embeddings import embed_query
from rag.store import query as store_query


def semantic_search(query_text: str, top_k: int = 5, space_key: Optional[str] = None) -> List[Dict[str, Any]]:
    embedding = embed_query(query_text)
    return store_query(embedding, top_k=top_k, space_key=space_key)
