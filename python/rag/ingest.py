"""Fetch, chunk, embed, and index Confluence pages into the local vector store."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from confluence_client import ConfluenceClient
from rag.chunker import chunk_confluence_storage
from rag.embeddings import embed_texts
from rag.store import delete_page, upsert_chunks


async def ingest_pages(client: ConfluenceClient, page_ids: List[str]) -> Dict[str, Any]:
    """Index (or re-index) the given Confluence page IDs. Returns a per-page summary."""
    indexed: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for page_id in page_ids:
        try:
            page = await client.get_page_content(page_id)
            body = page.get("body", {}).get("content", "")
            space = page.get("space") or {}
            title = page.get("title", "")

            chunks = chunk_confluence_storage(
                body,
                page_id=page.get("id") or page_id,
                title=title,
                space_key=space.get("key"),
                url=page.get("url", ""),
                updated=page.get("modified"),
            )

            if not chunks:
                errors.append({"page_id": page_id, "error": "No extractable text content"})
                continue

            def _embed_and_store(chunks=chunks) -> None:
                # Re-index cleanly: drop any chunks from a previous version of this page first.
                delete_page(page_id)
                embeddings = embed_texts([c.text for c in chunks])
                upsert_chunks(chunks, embeddings)

            await asyncio.to_thread(_embed_and_store)

            indexed.append({"page_id": page_id, "title": title, "chunks": len(chunks)})
        except Exception as e:
            errors.append({"page_id": page_id, "error": str(e)})

    return {
        "indexed": indexed,
        "errors": errors,
        "total_pages_indexed": len(indexed),
        "total_chunks": sum(item["chunks"] for item in indexed),
    }
