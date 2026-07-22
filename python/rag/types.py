from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Chunk:
    """A single retrievable slice of a Confluence page, scoped to one heading section."""

    chunk_id: str
    page_id: str
    title: str
    space_key: Optional[str]
    url: str
    heading_path: str
    order: int
    text: str
    updated: Optional[str] = None
