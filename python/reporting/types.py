from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional


DraftKind = Literal["progress", "manager_review"]


@dataclass(frozen=True)
class Draft:
    kind: DraftKind
    title: str
    content_markdown: str


@dataclass(frozen=True)
class WeeklyDraftsResult:
    week_start: date
    week_end: date
    jira_days_lookback: int
    jira_jql: Optional[str]
    drafts: list[Draft]

