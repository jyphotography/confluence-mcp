#!/usr/bin/env python3
"""
Script to fetch and summarize Jira tickets from the last 2 weeks.
Saves summaries to 2026/YYYYMM folder structure.
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional
    pass

# Add parent directory to path to access workspace root
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

# Jira API configuration - uses same credentials as Confluence
JIRA_URL = os.getenv("CONFLUENCE_URL", os.getenv("JIRA_URL", "https://your-domain.atlassian.net"))
JIRA_EMAIL = os.getenv("CONFLUENCE_EMAIL", os.getenv("JIRA_EMAIL", "your-email@example.com"))
JIRA_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", os.getenv("JIRA_API_TOKEN", ""))

def get_jira_tickets(days: int = 14) -> List[Dict]:
    """
    Fetch Jira tickets updated in the last N days assigned to the current user.
    """
    if not JIRA_API_TOKEN:
        print("Error: JIRA_API_TOKEN or CONFLUENCE_API_TOKEN not set.")
        print("Please set it in your .env file or environment variables.")
        return []
    
    # Calculate date N days ago
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # JQL query to get tickets updated in last N days assigned to current user
    jql = f"updated >= '{date_from}' AND assignee = currentUser() ORDER BY updated DESC"
    
    # Use the new search/jql endpoint
    url = f"{JIRA_URL}/rest/api/3/search/jql"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    
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
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Jira tickets: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return []

def format_ticket(ticket: Dict) -> str:
    """Format a single ticket into a readable string."""
    key = ticket.get("key", "N/A")
    fields = ticket.get("fields", {})
    summary = fields.get("summary", "No summary")
    status = fields.get("status", {}).get("name", "Unknown")
    issue_type = fields.get("issuetype", {}).get("name", "Unknown")
    priority = fields.get("priority", {}).get("name", "Unknown")
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

def summarize_tickets(tickets: List[Dict]) -> str:
    """Create a summary of tickets grouped by status."""
    if not tickets:
        return "No tickets found for the last 2 weeks."
    
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
        f"# Jira Tickets Summary - Last 2 Weeks",
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

def main():
    print("Fetching Jira tickets from the last 2 weeks...")
    tickets = get_jira_tickets(days=14)
    
    if not tickets:
        print("No tickets found. This could mean:")
        print("1. No tickets were updated in the last 2 weeks")
        print("2. Authentication failed (check your API token)")
        print("3. Jira URL is incorrect")
        return
    
    summary = summarize_tickets(tickets)
    print("\n" + "="*80)
    print(summary)
    print("="*80)
    
    # Save to file in 2026/YYYYMM folder
    output_file = get_output_path()
    with open(output_file, "w") as f:
        f.write(summary)
    print(f"\nSummary saved to: {output_file}")

if __name__ == "__main__":
    main()

