#!/usr/bin/env python3
"""
Confluence MCP Server
A Model Context Protocol server for searching and retrieving Confluence pages.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
import requests
from datetime import date

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

# Repo root (used for imports + reading .env + saving files)
workspace_root = Path(__file__).resolve().parents[1]

# Ensure repo-root modules are importable even when the process cwd is elsewhere
# (e.g., MCP clients often launch with cwd != repo root).
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    env_path = workspace_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv is optional
    pass

# Import the Confluence client
from confluence_client import ConfluenceClient
from reporting.report_service import generate_weekly_drafts as generate_weekly_drafts_shared


# Initialize the MCP server
app = Server("confluence-mcp")

# Initialize Confluence client
confluence_client: Optional[ConfluenceClient] = None

def get_confluence_client() -> ConfluenceClient:
    """Get or create the Confluence client instance."""
    global confluence_client
    if confluence_client is None:
        url = os.getenv("CONFLUENCE_URL")
        email = os.getenv("CONFLUENCE_EMAIL")
        api_token = os.getenv("CONFLUENCE_API_TOKEN")
        
        if not all([url, email, api_token]):
            raise ValueError(
                "Missing required environment variables: "
                "CONFLUENCE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN"
            )
        
        confluence_client = ConfluenceClient(url, email, api_token)
    
    return confluence_client


# Jira API helper functions
def get_jira_tickets(days: int = 14) -> list[dict]:
    """Fetch Jira tickets updated in the last N days assigned to the current user."""
    jira_url = os.getenv("CONFLUENCE_URL", os.getenv("JIRA_URL", ""))
    jira_email = os.getenv("CONFLUENCE_EMAIL", os.getenv("JIRA_EMAIL", ""))
    jira_api_token = os.getenv("CONFLUENCE_API_TOKEN", os.getenv("JIRA_API_TOKEN", ""))
    
    if not all([jira_url, jira_email, jira_api_token]):
        return []
    
    # Calculate date N days ago
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # JQL query to get tickets updated in last N days assigned to current user
    jql = f"updated >= '{date_from}' AND assignee = currentUser() ORDER BY updated DESC"
    
    # Use the new search/jql endpoint
    url = f"{jira_url}/rest/api/3/search/jql"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (jira_email, jira_api_token)
    
    payload = {
        "jql": jql,
        "fields": ["summary", "status", "issuetype", "priority", "updated", "created", "description", "project"],
        "maxResults": 100
    }
    
    try:
        response = requests.post(url, headers=headers, auth=auth, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("issues", [])
    except requests.exceptions.RequestException:
        return []


def get_user_account_id(email: str) -> Optional[str]:
    """
    Look up a user's Account ID from their email address.
    
    Args:
        email: User's email address
        
    Returns:
        Account ID string or None if not found
    """
    jira_url = os.getenv("CONFLUENCE_URL", os.getenv("JIRA_URL", ""))
    jira_email = os.getenv("CONFLUENCE_EMAIL", os.getenv("JIRA_EMAIL", ""))
    jira_api_token = os.getenv("CONFLUENCE_API_TOKEN", os.getenv("JIRA_API_TOKEN", ""))
    
    if not all([jira_url, jira_email, jira_api_token]):
        return None
    
    url = f"{jira_url}/rest/api/3/user/search"
    headers = {
        "Accept": "application/json"
    }
    auth = (jira_email, jira_api_token)
    params = {
        "query": email
    }
    
    try:
        response = requests.get(url, headers=headers, auth=auth, params=params)
        response.raise_for_status()
        users = response.json()
        
        # Find exact email match
        for user in users:
            if user.get("emailAddress", "").lower() == email.lower():
                return user.get("accountId")
        
        # If no exact match, return first result
        if users:
            return users[0].get("accountId")
        
        return None
        
    except requests.exceptions.RequestException:
        return None


def search_jira_tickets_by_user(account_id: str, days: int = 14, 
                                 search_type: str = "assignee") -> list[dict]:
    """
    Search for Jira tickets by user Account ID.
    
    Args:
        account_id: User's Account ID
        days: Number of days to look back
        search_type: Type of search - "assignee", "reporter", or "all"
        
    Returns:
        List of ticket dictionaries
    """
    jira_url = os.getenv("CONFLUENCE_URL", os.getenv("JIRA_URL", ""))
    jira_email = os.getenv("CONFLUENCE_EMAIL", os.getenv("JIRA_EMAIL", ""))
    jira_api_token = os.getenv("CONFLUENCE_API_TOKEN", os.getenv("JIRA_API_TOKEN", ""))
    
    if not all([jira_url, jira_email, jira_api_token]):
        return []
    
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Build JQL query based on search type
    if search_type == "assignee":
        jql = f'updated >= "{date_from}" AND assignee = "{account_id}" ORDER BY updated DESC'
    elif search_type == "reporter":
        jql = f'updated >= "{date_from}" AND reporter = "{account_id}" ORDER BY updated DESC'
    elif search_type == "all":
        jql = f'updated >= "{date_from}" AND (assignee = "{account_id}" OR reporter = "{account_id}") ORDER BY updated DESC'
    else:
        jql = f'updated >= "{date_from}" AND assignee = "{account_id}" ORDER BY updated DESC'
    
    url = f"{jira_url}/rest/api/3/search/jql"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (jira_email, jira_api_token)
    
    payload = {
        "jql": jql,
        "fields": ["summary", "status", "issuetype", "priority", "updated", "created", 
                   "description", "project", "assignee", "reporter"],
        "maxResults": 100
    }
    
    try:
        response = requests.post(url, headers=headers, auth=auth, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("issues", [])
    except requests.exceptions.RequestException:
        return []


def search_jira_tickets_by_email(email: str, days: int = 14, 
                                  search_type: str = "assignee") -> dict:
    """
    Search for Jira tickets by user email address.
    First looks up the Account ID, then searches for tickets.
    
    Args:
        email: User's email address
        days: Number of days to look back
        search_type: Type of search - "assignee", "reporter", or "all"
        
    Returns:
        Dictionary with user info and tickets
    """
    account_id = get_user_account_id(email)
    
    if not account_id:
        return {
            "error": f"Could not find user with email: {email}",
            "user_email": email,
            "account_id": None,
            "tickets": []
        }
    
    tickets = search_jira_tickets_by_user(account_id, days=days, search_type=search_type)
    
    return {
        "user_email": email,
        "account_id": account_id,
        "search_type": search_type,
        "days": days,
        "total_tickets": len(tickets),
        "tickets": tickets
    }


def format_ticket(ticket: dict) -> str:
    """Format a single ticket into a readable string."""
    key = ticket.get("key", "N/A")
    fields = ticket.get("fields", {})
    summary = fields.get("summary", "No summary")
    status = fields.get("status", {}).get("name", "Unknown")
    issue_type = fields.get("issuetype", {}).get("name", "Unknown")
    updated = fields.get("updated", "")
    
    # Format date
    if updated:
        try:
            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            updated_str = dt.strftime("%Y-%m-%d")
        except:
            updated_str = updated[:10] if len(updated) >= 10 else updated
    else:
        updated_str = "N/A"
    
    return f"• [{key}] {summary} ({issue_type} - {status}) - Updated: {updated_str}"


def summarize_tickets(tickets: list[dict]) -> str:
    """Create a summary of tickets grouped by status."""
    if not tickets:
        return "No tickets found for the specified time period."
    
    # Group by status
    by_status = {}
    by_type = {}
    
    for ticket in tickets:
        status = ticket.get("fields", {}).get("status", {}).get("name", "Unknown")
        issue_type = ticket.get("fields", {}).get("issuetype", {}).get("name", "Unknown")
        
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(ticket)
        
        if issue_type not in by_type:
            by_type[issue_type] = []
        by_type[issue_type].append(ticket)
    
    summary_lines = [
        f"# Jira Tickets Summary - Last {len(tickets)} tickets found",
        f"Total Tickets: {len(tickets)}\n",
        "## By Status:",
    ]
    
    for status, status_tickets in sorted(by_status.items()):
        summary_lines.append(f"\n### {status} ({len(status_tickets)} tickets)")
        for ticket in status_tickets:
            summary_lines.append(format_ticket(ticket))
    
    summary_lines.append("\n## By Issue Type:")
    for issue_type, type_tickets in sorted(by_type.items()):
        summary_lines.append(f"\n### {issue_type} ({len(type_tickets)} tickets)")
        for ticket in type_tickets:
            summary_lines.append(format_ticket(ticket))
    
    return "\n".join(summary_lines)


def get_output_path() -> Path:
    """Get the output path in 2026/YYYYMM format."""
    now = datetime.now()
    year = now.year
    month = now.strftime("%m")
    
    # Create path: workspace_root/2026/YYYYMM
    output_dir = workspace_root / "2026" / f"{year}{month}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Filename: jira_summary_YYYYMMDD.md
    filename = f"jira_summary_{now.strftime('%Y%m%d')}.md"
    return output_dir / filename


def get_jira_summary(days: int = 14, save_to_file: bool = True) -> str:
    """Get Jira summary and optionally save to file."""
    tickets = get_jira_tickets(days=days)
    
    if not tickets:
        return "No tickets found. This could mean:\n1. No tickets were updated in the specified time period\n2. Authentication failed (check your API token)\n3. Jira URL is incorrect"
    
    summary = summarize_tickets(tickets)
    
    if save_to_file:
        output_file = get_output_path()
        try:
            with open(output_file, "w") as f:
                f.write(summary)
            summary += f"\n\n✅ Summary saved to: {output_file}"
        except Exception as e:
            summary += f"\n\n⚠️ Warning: Could not save to file: {e}"
    
    return summary


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="search_pages",
            description=(
                "Search for Confluence pages by query. Returns a list of matching pages "
                "with their titles, IDs, and snippets. Useful for finding relevant documentation "
                "before making changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find pages (searches in title and content)"
                    },
                    "space_key": {
                        "type": "string",
                        "description": "Optional: Limit search to a specific space key"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_page",
            description=(
                "Get a specific Confluence page by its ID. Returns page metadata including "
                "title, space, version, and URL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "The Confluence page ID"
                    }
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="get_page_content",
            description=(
                "Get the full content of a Confluence page including body text. "
                "This is useful for understanding the complete context of a page before making changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "The Confluence page ID"
                    },
                    "expand": {
                        "type": "string",
                        "description": "Comma-separated list of fields to expand (default: body.storage,version,space)",
                        "default": "body.storage,version,space"
                    }
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="list_spaces",
            description=(
                "List all Confluence spaces accessible to the authenticated user. "
                "Useful for discovering available documentation spaces."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of spaces to return (default: 50)",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="search_by_title",
            description=(
                "Search for Confluence pages by title (exact or partial match). "
                "More precise than general search when you know the page title."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Page title to search for (supports partial matches)"
                    },
                    "space_key": {
                        "type": "string",
                        "description": "Optional: Limit search to a specific space key"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="get_jira_summary",
            description=(
                "Get a summary of Jira tickets assigned to the current user from the last N days. "
                "Returns a formatted summary grouped by status and issue type, and saves it to "
                "2026/YYYYMM folder structure. Uses the same Atlassian credentials as Confluence."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back for tickets (default: 14)",
                        "default": 14
                    },
                    "save_to_file": {
                        "type": "boolean",
                        "description": "Whether to save the summary to a file (default: true)",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="get_jira_weekly_report",
            description=(
                "Generate a high-level weekly report from Jira tickets with business benefits. "
                "Analyzes tickets to extract value propositions and formats them for stakeholders. "
                "Categorizes tickets into 'This Week' (Done/In Progress/In Review) and 'Next Week' (To Do). "
                "Saves to 2026/YYYYMM/weekly_report_YYYYMMDD.md"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back for tickets (default: 14)",
                        "default": 14
                    },
                    "save_to_file": {
                        "type": "boolean",
                        "description": "Whether to save the report to a file (default: true)",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="search_jira_tickets_by_email",
            description=(
                "Search for Jira tickets by a specific user's email address. "
                "Automatically looks up the user's Account ID from their email, then searches for their tickets. "
                "Can search by assignee, reporter, or both. Useful for understanding what a team member has been working on."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "User's email address (e.g., user@example.com)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back for tickets (default: 14)",
                        "default": 14
                    },
                    "search_type": {
                        "type": "string",
                        "description": "Type of search: 'assignee' (tickets assigned to user), 'reporter' (tickets reported by user), or 'all' (both) (default: 'assignee')",
                        "enum": ["assignee", "reporter", "all"],
                        "default": "assignee"
                    }
                },
                "required": ["email"]
            }
        )
        ,
        Tool(
            name="generate_weekly_drafts",
            description=(
                "Generate two manager-ready markdown drafts for the selected week window: "
                "a weekly progress update and a weekly manager review. Optionally saves to "
                "the local 2026/YYYYMM folder and to the SQLite drafts DB used by the backend."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "week_start": {
                        "type": "string",
                        "description": "Optional ISO date (YYYY-MM-DD). If omitted, uses current week Monday."
                    },
                    "week_end": {
                        "type": "string",
                        "description": "Optional ISO date (YYYY-MM-DD). If omitted, uses current week Sunday."
                    },
                    "jira_days_lookback": {
                        "type": "integer",
                        "description": "How many days of Jira updates to consider (default: 14)",
                        "default": 14
                    },
                    "confluence_page_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional Confluence page IDs to include as context links/excerpts"
                    },
                    "save_to_files": {
                        "type": "boolean",
                        "description": "Save drafts to 2026/YYYYMM folder (default: true)",
                        "default": True
                    },
                    "save_to_db": {
                        "type": "boolean",
                        "description": "Save drafts to SQLite DB (default: true)",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="index_confluence_pages",
            description=(
                "Chunk and embed Confluence pages into the local semantic search index. "
                "Provide explicit page_ids, or a keyword query (optionally scoped to a space) "
                "to discover and index matching pages in one step via the existing CQL search. "
                "Re-indexing a page replaces its previously indexed chunks. Run this before "
                "using semantic_search_pages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Explicit Confluence page IDs to index"
                    },
                    "query": {
                        "type": "string",
                        "description": "Keyword query used to discover pages to index when page_ids is omitted"
                    },
                    "space_key": {
                        "type": "string",
                        "description": "Optional: limit discovery query to a specific space key"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max pages to discover via query (default: 20)",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="semantic_search_pages",
            description=(
                "Semantic (vector) search over previously indexed Confluence page chunks. "
                "Complements search_pages (keyword/CQL): use this for conceptual or "
                "natural-language queries where the exact wording may not appear in the page "
                "text. Returns chunk text with page title, URL, and heading breadcrumb for "
                "citation. Pages must be indexed first via index_confluence_pages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language search query"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of chunks to return (default: 5)",
                        "default": 5
                    },
                    "space_key": {
                        "type": "string",
                        "description": "Optional: restrict results to a space key"
                    }
                },
                "required": ["query"]
            }
        )
    ]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources (Confluence spaces)."""
    try:
        client = get_confluence_client()
        spaces = await client.list_spaces(limit=20)
        
        resources = []
        for space in spaces.get("spaces", []):
            resources.append(Resource(
                uri=f"confluence://space/{space['key']}",
                name=f"Space: {space['name']}",
                description=f"Confluence space: {space['name']} ({space['key']})",
                mimeType="application/json"
            ))
        
        return resources
    except Exception as e:
        # If we can't list spaces, return empty list
        return []


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    client = get_confluence_client()
    
    try:
        if name == "search_pages":
            query = arguments.get("query")
            space_key = arguments.get("space_key")
            limit = arguments.get("limit", 10)
            
            results = await client.search_pages(query, space_key=space_key, limit=limit)
            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]
        
        elif name == "get_page":
            page_id = arguments.get("page_id")
            result = await client.get_page(page_id)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "get_page_content":
            page_id = arguments.get("page_id")
            expand = arguments.get("expand", "body.storage,version,space")
            result = await client.get_page_content(page_id, expand=expand)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "list_spaces":
            limit = arguments.get("limit", 50)
            results = await client.list_spaces(limit=limit)
            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]
        
        elif name == "search_by_title":
            title = arguments.get("title")
            space_key = arguments.get("space_key")
            limit = arguments.get("limit", 10)
            results = await client.search_by_title(title, space_key=space_key, limit=limit)
            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]
        
        elif name == "get_jira_summary":
            # Run Jira API calls in executor since requests is synchronous
            days = arguments.get("days", 14)
            save_to_file = arguments.get("save_to_file", True)
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: get_jira_summary(days=days, save_to_file=save_to_file)
            )
            
            return [TextContent(
                type="text",
                text=result
            )]
        
        elif name == "get_jira_weekly_report":
            # Import and run weekly report generation
            days = arguments.get("days", 14)
            save_to_file = arguments.get("save_to_file", True)
            
            # Import the weekly report function
            from jira_weekly_report import generate_weekly_report
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: generate_weekly_report(days=days, save_to_file=save_to_file)
            )
            
            return [TextContent(
                type="text",
                text=result
            )]
        
        elif name == "search_jira_tickets_by_email":
            email = arguments.get("email")
            days = arguments.get("days", 14)
            search_type = arguments.get("search_type", "assignee")
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: search_jira_tickets_by_email(email=email, days=days, search_type=search_type)
            )
            
            # Format the result nicely
            if "error" in result:
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            
            # Create a formatted summary
            tickets = result.get("tickets", [])
            summary_lines = [
                f"# Jira Tickets for {result['user_email']}",
                f"Account ID: {result['account_id']}",
                f"Search Type: {search_type}",
                f"Time Period: Last {days} days",
                f"Total Tickets: {result['total_tickets']}\n",
                "## Tickets:\n"
            ]
            
            # Group by status
            by_status = {}
            for ticket in tickets:
                status = ticket.get("fields", {}).get("status", {}).get("name", "Unknown")
                if status not in by_status:
                    by_status[status] = []
                by_status[status].append(ticket)
            
            for status, status_tickets in sorted(by_status.items()):
                summary_lines.append(f"\n### {status} ({len(status_tickets)} tickets)")
                for ticket in status_tickets:
                    summary_lines.append(format_ticket(ticket))
            
            summary_text = "\n".join(summary_lines)
            
            return [TextContent(
                type="text",
                text=summary_text
            )]

        elif name == "generate_weekly_drafts":
            week_start_s = arguments.get("week_start")
            week_end_s = arguments.get("week_end")
            jira_days_lookback = int(arguments.get("jira_days_lookback", 14))
            confluence_page_ids = arguments.get("confluence_page_ids") or []
            save_to_files = bool(arguments.get("save_to_files", True))
            save_to_db = bool(arguments.get("save_to_db", True))

            def _parse_iso(s: Optional[str]) -> Optional[date]:
                if not s:
                    return None
                return date.fromisoformat(s)

            ws = _parse_iso(week_start_s)
            we = _parse_iso(week_end_s)
            if not (ws and we):
                today = date.today()
                ws = today - timedelta(days=today.weekday())
                we = ws + timedelta(days=6)

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: generate_weekly_drafts_shared(
                    week_start=ws, week_end=we, jira_days_lookback=jira_days_lookback, confluence_page_ids=confluence_page_ids
                ),
            )

            saved = []
            # Optional DB save via backend models (shared sqlite)
            if save_to_db:
                try:
                    from backend.app.db.session import init_db, get_session
                    from backend.app.db.models import WeeklyDraft, DraftKind

                    init_db()
                    with get_session() as session:
                        for d in result.drafts:
                            row = WeeklyDraft(
                                week_start=ws,
                                week_end=we,
                                kind=DraftKind(d.kind),
                                title=d.title,
                                content_markdown=d.content_markdown,
                                jira_days_lookback=jira_days_lookback,
                                jira_jql=result.jira_jql,
                                confluence_context=",".join(confluence_page_ids) or None,
                            )
                            session.add(row)
                            session.commit()
                            session.refresh(row)
                            saved.append({"kind": d.kind, "id": str(row.id)})
                except Exception as e:
                    saved.append({"error": f"DB save failed: {e}"})

            file_paths = []
            if save_to_files:
                out_dir = workspace_root / "2026" / f"{date.today().strftime('%Y%m')}"
                out_dir.mkdir(parents=True, exist_ok=True)
                for d in result.drafts:
                    filename = f"{d.kind}_{ws.strftime('%Y%m%d')}_{we.strftime('%Y%m%d')}.md"
                    out_path = out_dir / filename
                    out_path.write_text(d.content_markdown, encoding="utf-8")
                    file_paths.append(str(out_path))

            payload = {
                "week_start": ws.isoformat(),
                "week_end": we.isoformat(),
                "jira_days_lookback": jira_days_lookback,
                "jira_jql": result.jira_jql,
                "drafts": [{"kind": d.kind, "title": d.title, "content_markdown": d.content_markdown} for d in result.drafts],
                "saved_db": saved,
                "saved_files": file_paths,
            }

            return [TextContent(type="text", text=json.dumps(payload, indent=2))]

        elif name == "index_confluence_pages":
            page_ids = list(arguments.get("page_ids") or [])
            discover_query = arguments.get("query")
            space_key = arguments.get("space_key")
            limit = arguments.get("limit", 20)

            if not page_ids and discover_query:
                discovered = await client.search_pages(discover_query, space_key=space_key, limit=limit)
                page_ids = [p["id"] for p in discovered.get("pages", []) if p.get("id")]

            if not page_ids:
                return [TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": "Provide page_ids, or a query to discover pages to index"}, indent=2
                    )
                )]

            from rag.ingest import ingest_pages

            result = await ingest_pages(client, page_ids)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "semantic_search_pages":
            query_text = arguments.get("query")
            top_k = arguments.get("top_k", 5)
            space_key = arguments.get("space_key")

            from rag.retrieve import semantic_search

            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: semantic_search(query_text, top_k=top_k, space_key=space_key)
            )
            return [TextContent(
                type="text",
                text=json.dumps({"query": query_text, "results": results}, indent=2)
            )]

        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        error_msg = f"Error executing tool {name}: {str(e)}"
        return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]


async def main():
    """Main entry point for the MCP server."""
    # Validate environment variables
    try:
        get_confluence_client()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

