#!/usr/bin/env python3
"""
Atlassian diagnostics (Jira + Confluence).

This script is safe to share: it never prints your token.

What it checks:
- Env vars present (CONFLUENCE_URL / CONFLUENCE_EMAIL / CONFLUENCE_API_TOKEN)
- Jira auth: GET /rest/api/3/myself
- Jira weekly query: POST /rest/api/3/search/jql (same JQL used by weekly drafts)
- Confluence auth: GET /wiki/rest/api/space?limit=1 (Cloud) or /rest/api/space?limit=1 (Server)
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple


def _load_env_file(path: Path) -> None:
    """
    Minimal .env loader (KEY=VALUE, ignores comments/blank lines).
    Only sets keys that aren't already in os.environ.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip("\"'")  # allow simple quoting
        os.environ.setdefault(k, v)


def _basic_auth_header(email: str, token: str) -> str:
    b64 = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return f"Basic {b64}"


def _request_json(
    method: str,
    url: str,
    auth_header: str,
    payload: Optional[dict] = None,
    timeout_s: int = 30,
) -> Tuple[int, str, Optional[dict]]:
    data = None
    headers = {"Accept": "application/json", "Authorization": auth_header}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, body, json.loads(body) if body else {}
            except json.JSONDecodeError:
                return resp.status, body, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body, None
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}", None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    _load_env_file(repo_root / ".env")

    base_url = os.getenv("CONFLUENCE_URL", "").rstrip("/")
    email = os.getenv("CONFLUENCE_EMAIL", "")
    token = os.getenv("CONFLUENCE_API_TOKEN", "")

    print("== Env ==")
    print("CONFLUENCE_URL set:", bool(base_url))
    print("CONFLUENCE_EMAIL set:", bool(email))
    print("CONFLUENCE_API_TOKEN set:", bool(token), "(len:", len(token), ")")
    if not (base_url and email and token):
        print("\nMissing env vars. Fix your `.env` or export vars then retry.")
        return 2

    auth = _basic_auth_header(email=email, token=token)

    print("\n== Jira ==")
    jira_myself_url = f"{base_url}/rest/api/3/myself"
    code, body, data = _request_json("GET", jira_myself_url, auth_header=auth)
    print("GET /rest/api/3/myself:", code)
    if code != 200:
        print("Body head:", body[:300].replace("\n", " "))
        print(
            "Hint: If this is 401/403, your token/user may not have Jira access for this site."
        )
    else:
        display = (data or {}).get("displayName") or (data or {}).get("name") or "<ok>"
        print("Authenticated as:", display)

    weekly_jql = "updated >= -14d AND assignee = currentUser() ORDER BY updated DESC"
    jira_search_url = f"{base_url}/rest/api/3/search/jql"
    payload = {"jql": weekly_jql, "fields": ["summary", "status"], "maxResults": 5}
    code2, body2, data2 = _request_json("POST", jira_search_url, auth_header=auth, payload=payload)
    print("POST /rest/api/3/search/jql:", code2)
    if code2 != 200:
        print("Body head:", body2[:300].replace("\n", " "))
    else:
        issues = (data2 or {}).get("issues") or []
        total = (data2 or {}).get("total")
        print("Weekly JQL issues returned:", len(issues), "total:", total)
        if total == 0:
            print("Note: This can be normal if you have no issues assigned/updated in last 14 days.")

    print("\n== Confluence ==")
    is_cloud = ".atlassian.net" in base_url.lower()
    confluence_api_base = f"{base_url}/wiki/rest/api" if is_cloud else f"{base_url}/rest/api"
    conf_spaces_url = f"{confluence_api_base}/space?limit=1"
    code3, body3, data3 = _request_json("GET", conf_spaces_url, auth_header=auth)
    print("GET /space?limit=1:", code3)
    if code3 != 200:
        print("Body head:", body3[:300].replace("\n", " "))
        print("Hint: For Confluence Cloud, the API base is /wiki/rest/api.")
    else:
        size = (data3 or {}).get("size")
        print("Confluence reachable; result size:", size)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

