"""Heading-aware chunking for Confluence storage-format (XHTML) page bodies.

Confluence's storage representation is an XHTML fragment (not a full document),
so top-level nodes returned by BeautifulSoup are the page's real top-level content
(headings, paragraphs, lists, tables, macros) in document order. We walk that flat
sequence, group text under the heading it falls under, and build a breadcrumb
("Page Title > Section > Subsection") for each section so retrieved chunks stay
traceable to their place in the page. Long sections are then split into
word-bounded windows with overlap so no single chunk is too large to embed well.
"""

from __future__ import annotations

from typing import List, Optional

from bs4 import BeautifulSoup

from rag.types import Chunk

_HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

DEFAULT_MAX_WORDS = 350
DEFAULT_OVERLAP_WORDS = 50


def _extract_sections(html: str, title: str) -> List[tuple[str, str]]:
    """Split a storage-format body into (heading_path, text) sections in document order."""
    soup = BeautifulSoup(html or "", "html.parser")

    sections: List[tuple[str, str]] = []
    heading_stack: List[tuple[int, str]] = []
    current_path = title
    current_parts: List[str] = []

    def flush() -> None:
        text = "\n\n".join(part for part in current_parts if part.strip())
        if text.strip():
            sections.append((current_path, text))

    for node in soup.contents:
        node_name = getattr(node, "name", None)
        if node_name in _HEADING_LEVELS:
            flush()
            level = _HEADING_LEVELS[node_name]
            heading_text = node.get_text(" ", strip=True)
            heading_stack = [h for h in heading_stack if h[0] < level]
            if heading_text:
                heading_stack.append((level, heading_text))
            current_path = " > ".join([title] + [h[1] for h in heading_stack])
            current_parts = []
        else:
            text = node.get_text("\n", strip=True) if hasattr(node, "get_text") else str(node).strip()
            if text:
                current_parts.append(text)

    flush()
    return sections


def _split_words(text: str, max_words: int, overlap_words: int) -> List[str]:
    words = text.split()
    if not words:
        return []

    windows: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        windows.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(end - overlap_words, start + 1)
    return windows


def chunk_confluence_storage(
    html: str,
    *,
    page_id: str,
    title: str,
    space_key: Optional[str] = None,
    url: str = "",
    updated: Optional[str] = None,
    max_words: int = DEFAULT_MAX_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> List[Chunk]:
    """Chunk a Confluence page body into heading-scoped, word-bounded, overlapping chunks."""
    chunks: List[Chunk] = []
    order = 0
    for heading_path, text in _extract_sections(html, title):
        for window in _split_words(text, max_words=max_words, overlap_words=overlap_words):
            chunks.append(
                Chunk(
                    chunk_id=f"{page_id}:{order}",
                    page_id=page_id,
                    title=title,
                    space_key=space_key,
                    url=url,
                    heading_path=heading_path,
                    order=order,
                    text=window,
                    updated=updated,
                )
            )
            order += 1
    return chunks
