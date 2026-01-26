from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

import os
import re
import sys
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from reporting.types import Draft, WeeklyDraftsResult


# Load `.env` for backend usage (uvicorn won't load it automatically).
try:
    from dotenv import load_dotenv

    # report_service.py -> reporting -> python -> repo root
    _env_path = Path(__file__).resolve().parents[2] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass


THIS_WEEK_STATUSES = ["Done", "In Progress", "In Review", "Review", "Testing"]
NEXT_WEEK_STATUSES = ["To Do", "Backlog", "Open"]

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
_JINJA = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(enabled_extensions=(), default_for_string=False, default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _jira_base() -> tuple[str, str, str]:
    jira_url = os.getenv("CONFLUENCE_URL", os.getenv("JIRA_URL", ""))
    jira_email = os.getenv("CONFLUENCE_EMAIL", os.getenv("JIRA_EMAIL", ""))
    jira_api_token = os.getenv("CONFLUENCE_API_TOKEN", os.getenv("JIRA_API_TOKEN", ""))
    return jira_url.rstrip("/"), jira_email, jira_api_token


def _jira_search(jql: str, fields: list[str]) -> list[dict[str, Any]]:
    jira_url, jira_email, jira_api_token = _jira_base()
    if not all([jira_url, jira_email, jira_api_token]):
        return []

    url = f"{jira_url}/rest/api/3/search/jql"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {"jql": jql, "fields": fields, "maxResults": 100}

    try:
        resp = requests.post(url, headers=headers, auth=(jira_email, jira_api_token), json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json().get("issues", [])
    except requests.exceptions.RequestException as e:
        # Intentionally minimal: helps debug "empty weekly Jira" without leaking secrets.
        # Enable by setting DEBUG_JIRA=1.
        if os.getenv("DEBUG_JIRA") == "1":
            status = getattr(getattr(e, "response", None), "status_code", None)
            print(f"[report_service] Jira request failed status={status}: {e}", file=sys.stderr)
        return []


def _extract_benefit(summary: str, description: str) -> str:
    """
    Heuristic “business benefit” extraction.
    Intentionally simple + deterministic; user edits the final draft in UI.
    """
    summary_l = summary.lower()
    text_l = f"{summary} {description}".lower()

    if "deploy" in summary_l:
        return f"Deployed: {summary}"
    if "fix" in summary_l or "bug" in summary_l:
        return f"Improved reliability by addressing: {summary}"
    if "optimiz" in text_l or "performance" in text_l:
        return f"Improved performance: {summary}"
    if "test" in summary_l or "validation" in summary_l:
        return f"Improved quality checks: {summary}"
    if "refactor" in summary_l or "cleanup" in summary_l:
        return f"Improved maintainability: {summary}"
    return summary


def _ticket_url(key: str) -> Optional[str]:
    jira_url, _, _ = _jira_base()
    if not jira_url:
        return None
    return f"{jira_url}/browse/{key}"


def _confluence_base() -> tuple[str, str, str, str]:
    base_url = os.getenv("CONFLUENCE_URL", "").rstrip("/")
    email = os.getenv("CONFLUENCE_EMAIL", "")
    token = os.getenv("CONFLUENCE_API_TOKEN", "")
    if ".atlassian.net" in base_url.lower():
        api_base = f"{base_url}/wiki/rest/api"
    else:
        api_base = f"{base_url}/rest/api"
    return base_url, api_base, email, token


def _strip_html(s: str, max_len: int = 180) -> str:
    txt = re.sub(r"<[^>]+>", " ", s)
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) > max_len:
        return txt[: max_len - 1].rstrip() + "…"
    return txt


def _get_confluence_context(page_ids: list[str]) -> list[dict[str, str]]:
    if not page_ids:
        return []
    base_url, api_base, email, token = _confluence_base()
    if not all([base_url, api_base, email, token]):
        return []

    out: list[dict[str, str]] = []
    headers = {"Accept": "application/json"}
    for pid in page_ids:
        try:
            resp = requests.get(
                f"{api_base}/content/{pid}",
                headers=headers,
                auth=(email, token),
                params={"expand": "body.storage,version,space"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            title = data.get("title") or pid
            webui = (data.get("_links") or {}).get("webui") or ""
            url = f"{base_url}{webui}" if webui else base_url
            body = (((data.get("body") or {}).get("storage") or {}).get("value")) or ""
            excerpt = _strip_html(body)
            out.append({"id": pid, "title": title, "url": url, "excerpt": excerpt})
        except requests.exceptions.RequestException:
            continue
    return out


def _format_ticket_bullets(tickets: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for t in tickets:
        key = t.get("key", "")
        fields = t.get("fields", {}) or {}
        summary = fields.get("summary", "No summary")
        status = (fields.get("status") or {}).get("name", "Unknown")
        issue_type = (fields.get("issuetype") or {}).get("name", "Unknown")
        url = _ticket_url(key)
        if url:
            out.append(f"- [{key}] {summary} ({issue_type} · {status}) — {url}")
        else:
            out.append(f"- [{key}] {summary} ({issue_type} · {status})")
    return out


def _categorize(tickets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    this_week: list[dict[str, Any]] = []
    next_week: list[dict[str, Any]] = []
    for t in tickets:
        status = ((t.get("fields") or {}).get("status") or {}).get("name", "")
        if any(s.lower() in status.lower() for s in THIS_WEEK_STATUSES):
            this_week.append(t)
        elif any(s.lower() in status.lower() for s in NEXT_WEEK_STATUSES):
            next_week.append(t)
        else:
            this_week.append(t)
    return this_week, next_week


def _dedupe_benefits(tickets: list[dict[str, Any]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for t in tickets:
        key = t.get("key", "")
        fields = t.get("fields", {}) or {}
        summary = fields.get("summary", "")
        description = fields.get("description") or ""
        benefit = _extract_benefit(summary=summary, description=str(description))
        norm = re.sub(r"\s+", " ", benefit.strip().lower())
        if norm in seen:
            continue
        seen.add(norm)
        out.append((benefit, key))
    return out


def _ticket_summaries(tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tickets:
        key = t.get("key", "")
        fields = t.get("fields", {}) or {}
        out.append(
            {
                "key": key,
                "summary": fields.get("summary", "No summary"),
                "status": (fields.get("status") or {}).get("name", "Unknown"),
                "issue_type": (fields.get("issuetype") or {}).get("name", "Unknown"),
                "url": _ticket_url(key),
            }
        )
    return out


def _render_template(template_name: str, **ctx: Any) -> str:
    tpl = _JINJA.get_template(template_name)
    return tpl.render(**ctx).strip() + "\n"


def generate_weekly_drafts(
    week_start: date,
    week_end: date,
    jira_days_lookback: int = 14,
    confluence_page_ids: Optional[list[str]] = None,
) -> WeeklyDraftsResult:
    """
    Core shared generator used by both:
    - FastAPI backend
    - MCP server tool calls
    """
    date_from = (datetime.now() - timedelta(days=jira_days_lookback)).strftime("%Y-%m-%d")
    jql = f"updated >= '{date_from}' AND assignee = currentUser() ORDER BY updated DESC"

    tickets = _jira_search(
        jql=jql,
        fields=["summary", "status", "issuetype", "priority", "updated", "created", "description", "project"],
    )

    this_week, next_week = _categorize(tickets)
    confluence_context = _get_confluence_context(confluence_page_ids or [])

    progress_title = f"Weekly Progress: {week_start.isoformat()} → {week_end.isoformat()}"
    review_title = f"Weekly Review (Manager): {week_start.isoformat()} → {week_end.isoformat()}"

    highlights: list[str] = [benefit for benefit, _ in _dedupe_benefits(this_week)]
    next_week_bullets: list[str] = [benefit for benefit, _ in _dedupe_benefits(next_week)]

    drafts = [
        Draft(
            kind="progress",
            title=progress_title,
            content_markdown=_render_template(
                "progress.md.j2",
                week_start=week_start.isoformat(),
                week_end=week_end.isoformat(),
                highlights=[
                    f"{benefit} ({key}{f' — {_ticket_url(key)}' if _ticket_url(key) else ''})"
                    for benefit, key in _dedupe_benefits(this_week)
                ],
                this_week_tickets=_ticket_summaries(this_week),
                next_week_tickets=_ticket_summaries(next_week),
                confluence_context=confluence_context,
            ),
        ),
        Draft(
            kind="manager_review",
            title=review_title,
            content_markdown=_render_template(
                "manager_review.md.j2",
                week_start=week_start.isoformat(),
                week_end=week_end.isoformat(),
                this_week=highlights,
                next_week=next_week_bullets,
            ),
        ),
    ]

    return WeeklyDraftsResult(
        week_start=week_start,
        week_end=week_end,
        jira_days_lookback=jira_days_lookback,
        jira_jql=jql,
        drafts=drafts,
    )

