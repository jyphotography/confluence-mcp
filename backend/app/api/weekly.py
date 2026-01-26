from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.models import DraftKind, WeeklyDraft
from app.db.session import get_session
from app.schemas.weekly import (
    GenerateWeeklyDraftsRequest,
    GenerateWeeklyDraftsResponse,
    GeneratedDraft,
    WeeklyDraftDetail,
    WeeklyDraftListItem,
    UpdateWeeklyDraftRequest,
)


router = APIRouter(tags=["weekly"])


def _compute_week_window(today: Optional[date] = None) -> tuple[date, date]:
    """
    Compute current week as Monday..Sunday.
    """
    d = today or date.today()
    week_start = d - timedelta(days=d.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.post("/weekly-drafts/generate", response_model=GenerateWeeklyDraftsResponse)
def generate_weekly_drafts(
    payload: GenerateWeeklyDraftsRequest,
    session: Session = Depends(get_session),
) -> GenerateWeeklyDraftsResponse:
    """
    Generate two drafts:
    - Weekly progress (copy/paste to Confluence)
    - Weekly manager review (copy/paste to Confluence)
    """
    week_start, week_end = (
        (payload.week_start, payload.week_end)
        if payload.week_start and payload.week_end
        else _compute_week_window()
    )

    # Import here to keep import graph simple and to ensure sys.path adjustment in main works.
    from reporting.report_service import generate_weekly_drafts

    result = generate_weekly_drafts(
        week_start=week_start,
        week_end=week_end,
        jira_days_lookback=payload.jira_days_lookback,
        confluence_page_ids=payload.confluence_page_ids or [],
    )

    drafts_out: list[GeneratedDraft] = []
    for d in result.drafts:
        saved_id = None
        if payload.save_to_db:
            model = WeeklyDraft(
                week_start=week_start,
                week_end=week_end,
                kind=DraftKind(d.kind),
                title=d.title,
                content_markdown=d.content_markdown,
                jira_days_lookback=payload.jira_days_lookback,
                jira_jql=result.jira_jql,
                confluence_context=",".join(payload.confluence_page_ids or []) or None,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            saved_id = model.id

        saved_path = None
        if payload.save_to_files:
            out_dir = Path(__file__).resolve().parents[4] / "2026" / f"{date.today().strftime('%Y%m')}"
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{d.kind}_{week_start.strftime('%Y%m%d')}_{week_end.strftime('%Y%m%d')}.md"
            out_path = out_dir / filename
            out_path.write_text(d.content_markdown, encoding="utf-8")
            saved_path = str(out_path)

        drafts_out.append(
            GeneratedDraft(
                    kind=d.kind,
                title=d.title,
                content_markdown=d.content_markdown,
                saved_id=saved_id,
                saved_path=saved_path,
            )
        )

    return GenerateWeeklyDraftsResponse(
        week_start=week_start,
        week_end=week_end,
        jira_days_lookback=payload.jira_days_lookback,
        drafts=drafts_out,
    )


@router.get("/weekly-drafts", response_model=list[WeeklyDraftListItem])
def list_weekly_drafts(session: Session = Depends(get_session)) -> list[WeeklyDraftListItem]:
    rows = session.exec(select(WeeklyDraft).order_by(WeeklyDraft.created_at.desc())).all()
    return [
        WeeklyDraftListItem(
            id=r.id,
            kind=r.kind.value,
            title=r.title,
            week_start=r.week_start,
            week_end=r.week_end,
        )
        for r in rows
    ]


@router.get("/weekly-drafts/{draft_id}", response_model=WeeklyDraftDetail)
def get_weekly_draft(draft_id: UUID, session: Session = Depends(get_session)) -> WeeklyDraftDetail:
    row = session.get(WeeklyDraft, draft_id)
    if not row:
        raise HTTPException(status_code=404, detail="Draft not found")
    return WeeklyDraftDetail(
        id=row.id,
        kind=row.kind.value,
        title=row.title,
        week_start=row.week_start,
        week_end=row.week_end,
        content_markdown=row.content_markdown,
    )


@router.put("/weekly-drafts/{draft_id}", response_model=WeeklyDraftDetail)
def update_weekly_draft(
    draft_id: UUID, payload: UpdateWeeklyDraftRequest, session: Session = Depends(get_session)
) -> WeeklyDraftDetail:
    row = session.get(WeeklyDraft, draft_id)
    if not row:
        raise HTTPException(status_code=404, detail="Draft not found")

    if payload.title is not None:
        row.title = payload.title
    if payload.content_markdown is not None:
        row.content_markdown = payload.content_markdown

    session.add(row)
    session.commit()
    session.refresh(row)

    return WeeklyDraftDetail(
        id=row.id,
        kind=row.kind.value,
        title=row.title,
        week_start=row.week_start,
        week_end=row.week_end,
        content_markdown=row.content_markdown,
    )

