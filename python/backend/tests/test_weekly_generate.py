import sys
from pathlib import Path
import os

import responses
from fastapi.testclient import TestClient


def _make_app():
    # Ensure backend/ is importable as top-level `app`
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    # Ensure env vars exist for Settings (aliases)
    os.environ.setdefault("CONFLUENCE_URL", "https://example.atlassian.net")
    os.environ.setdefault("CONFLUENCE_EMAIL", "user@example.com")
    os.environ.setdefault("CONFLUENCE_API_TOKEN", "test-token")
    os.environ.setdefault("SQLITE_PATH", "data/test_weekly_progress.db")

    # Import after env setup
    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    return create_app()


@responses.activate
def test_generate_weekly_drafts_smoke():
    # Mock Jira search
    responses.add(
        responses.POST,
        "https://example.atlassian.net/rest/api/3/search/jql",
        json={
            "issues": [
                {
                    "key": "ABC-1",
                    "fields": {
                        "summary": "Fix flaky test in pipeline",
                        "status": {"name": "Done"},
                        "issuetype": {"name": "Bug"},
                        "description": "Make CI stable",
                    },
                },
                {
                    "key": "ABC-2",
                    "fields": {
                        "summary": "Add weekly report endpoint",
                        "status": {"name": "To Do"},
                        "issuetype": {"name": "Task"},
                        "description": "",
                    },
                },
            ]
        },
        status=200,
    )

    app = _make_app()
    client = TestClient(app)

    resp = client.post(
        "/api/weekly-drafts/generate",
        json={
            "jira_days_lookback": 14,
            "save_to_db": False,
            "save_to_files": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "drafts" in data
    assert len(data["drafts"]) == 2
    kinds = {d["kind"] for d in data["drafts"]}
    assert kinds == {"progress", "manager_review"}

    progress = next(d for d in data["drafts"] if d["kind"] == "progress")
    assert "Weekly Progress" in progress["content_markdown"]

    review = next(d for d in data["drafts"] if d["kind"] == "manager_review")
    assert "This Week:" in review["content_markdown"]
    assert "Next Week:" in review["content_markdown"]

