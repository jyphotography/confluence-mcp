from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class DraftKind(str, Enum):
    progress = "progress"
    manager_review = "manager_review"


class WeeklyDraft(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    week_start: date = Field(index=True)
    week_end: date = Field(index=True)
    kind: DraftKind = Field(index=True)

    title: str
    content_markdown: str

    # Provenance / debugging
    jira_days_lookback: int
    jira_jql: Optional[str] = None
    confluence_context: Optional[str] = None

