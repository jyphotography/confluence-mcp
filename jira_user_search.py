#!/usr/bin/env python3
"""
Script to search Jira tickets for a specific user by email address.
This script:
1. Looks up the user's Account ID from their email
2. Searches for their Jira tickets using the Account ID
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass
except Exception as e:
    print(f"Note: Could not load .env file: {e}", file=sys.stderr)

# Jira API configuration
JIRA_URL = os.getenv("CONFLUENCE_URL", os.getenv("JIRA_URL", "https://your-domain.atlassian.net"))
JIRA_EMAIL = os.getenv("CONFLUENCE_EMAIL", os.getenv("JIRA_EMAIL", ""))
JIRA_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", os.getenv("JIRA_API_TOKEN", ""))


def get_user_account_id(email: str) -> Optional[str]:
    """
    Look up a user's Account ID from their email address.
    
    Args:
        email: User's email address
        
    Returns:
        Account ID string or None if not found
    """
    if not all([JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
        print("❌ Error: Missing Jira credentials")
        return None
    
    url = f"{JIRA_URL}/rest/api/3/user/search"
    headers = {
        "Accept": "application/json"
    }
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
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
                account_id = user.get("accountId")
                print(f"✅ Found user: {user.get('displayName')} ({email})")
                print(f"   Account ID: {account_id}")
                return account_id
        
        # If no exact match, return first result
        if users:
            user = users[0]
            account_id = user.get("accountId")
            print(f"⚠️  No exact email match. Using: {user.get('displayName')} ({user.get('emailAddress')})")
            print(f"   Account ID: {account_id}")
            return account_id
        
        print(f"❌ No user found with email: {email}")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error looking up user: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        return None


def search_jira_tickets_by_user(account_id: str, days: int = 14, 
                                 search_type: str = "assignee") -> List[Dict]:
    """
    Search for Jira tickets by user Account ID.
    
    Args:
        account_id: User's Account ID
        days: Number of days to look back
        search_type: Type of search - "assignee", "reporter", or "all"
        
    Returns:
        List of ticket dictionaries
    """
    if not all([JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
        print("❌ Error: Missing Jira credentials")
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
    
    url = f"{JIRA_URL}/rest/api/3/search/jql"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    
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
    except requests.exceptions.RequestException as e:
        print(f"❌ Error searching Jira tickets: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        return []


def format_ticket(ticket: Dict) -> str:
    """Format a ticket for display."""
    fields = ticket.get("fields", {})
    key = ticket.get("key", "")
    summary = fields.get("summary", "No summary")
    status = fields.get("status", {}).get("name", "Unknown")
    issue_type = fields.get("issuetype", {}).get("name", "Unknown")
    updated = fields.get("updated", "")[:10] if fields.get("updated") else "Unknown"
    
    return f"[{key}] {summary} ({status}, {issue_type}, Updated: {updated})"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 jira_user_search.py <email> [days] [search_type]")
        print("  email: User's email address")
        print("  days: Number of days to look back (default: 14)")
        print("  search_type: 'assignee', 'reporter', or 'all' (default: 'assignee')")
        sys.exit(1)
    
    email = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    search_type = sys.argv[3] if len(sys.argv) > 3 else "assignee"
    
    print(f"🔍 Looking up Account ID for: {email}\n")
    account_id = get_user_account_id(email)
    
    if not account_id:
        print("\n❌ Cannot proceed without Account ID")
        sys.exit(1)
    
    print(f"\n🔍 Searching for tickets ({search_type}) in the last {days} days...\n")
    tickets = search_jira_tickets_by_user(account_id, days=days, search_type=search_type)
    
    if not tickets:
        print("No tickets found.")
        return
    
    print(f"📊 Found {len(tickets)} ticket(s):\n")
    print("=" * 80)
    
    for i, ticket in enumerate(tickets, 1):
        print(f"\n{i}. {format_ticket(ticket)}")
        fields = ticket.get("fields", {})
        
        # Show assignee and reporter
        assignee = fields.get("assignee", {})
        if assignee:
            assignee_name = assignee.get("displayName", assignee.get("emailAddress", "Unknown"))
            print(f"   👤 Assignee: {assignee_name}")
        
        reporter = fields.get("reporter", {})
        if reporter:
            reporter_name = reporter.get("displayName", reporter.get("emailAddress", "Unknown"))
            print(f"   📝 Reporter: {reporter_name}")
        
        # Show description excerpt
        description = fields.get("description", "")
        if description:
            if isinstance(description, dict):
                # Description might be in ADF format
                text = str(description)
            else:
                text = str(description)
            excerpt = text[:200].replace('\n', ' ').strip()
            if excerpt:
                print(f"   📄 {excerpt}...")
    
    print("\n" + "=" * 80)
    print(f"\n✅ Summary: Found {len(tickets)} ticket(s) for {email}")


if __name__ == "__main__":
    main()
