from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WeekRange(BaseModel):
    week_start: date
    week_end: date


class GenerateWeeklyDraftsRequest(BaseModel):
    """
    Generate drafts for a given week window.

    - If `week_start/week_end` are omitted, backend computes the current week (Mon-Sun) window.
    - `jira_days_lookback` controls which tickets to fetch (default: 14, matches existing MCP tools).
    """

    week_start: Optional[date] = None
    week_end: Optional[date] = None
    jira_days_lookback: int = Field(default=14, ge=1, le=90)
    confluence_page_ids: Optional[list[str]] = None
    save_to_db: bool = True
    save_to_files: bool = True


class GeneratedDraft(BaseModel):
    kind: str  # "progress" | "manager_review"
    title: str
    content_markdown: str
    saved_id: Optional[UUID] = None
    saved_path: Optional[str] = None


class GenerateWeeklyDraftsResponse(BaseModel):
    week_start: date
    week_end: date
    jira_days_lookback: int
    drafts: list[GeneratedDraft]


class WeeklyDraftListItem(BaseModel):
    id: UUID
    kind: str
    title: str
    week_start: date
    week_end: date


class WeeklyDraftDetail(BaseModel):
    id: UUID
    kind: str
    title: str
    week_start: date
    week_end: date
    content_markdown: str


class UpdateWeeklyDraftRequest(BaseModel):
    title: Optional[str] = None
    content_markdown: Optional[str] = None

