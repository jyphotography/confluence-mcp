#!/usr/bin/env python3
"""
Script to generate a high-level weekly report from Jira tickets.
Analyzes tickets to extract business benefits and formats them for stakeholders.
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from pathlib import Path
import re

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add parent directory to path to access workspace root
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

# Jira API configuration - uses same credentials as Confluence
JIRA_URL = os.getenv("CONFLUENCE_URL", os.getenv("JIRA_URL", "https://your-domain.atlassian.net"))
JIRA_EMAIL = os.getenv("CONFLUENCE_EMAIL", os.getenv("JIRA_EMAIL", "your-email@example.com"))
JIRA_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", os.getenv("JIRA_API_TOKEN", ""))

# Status mappings for categorization
THIS_WEEK_STATUSES = ["Done", "In Progress", "In Review", "Review", "Testing"]
NEXT_WEEK_STATUSES = ["To Do", "Backlog", "Open"]


def get_jira_tickets(days: int = 14) -> List[Dict]:
    """Fetch Jira tickets updated in the last N days assigned to the current user."""
    if not JIRA_API_TOKEN:
        print("Error: JIRA_API_TOKEN or CONFLUENCE_API_TOKEN not set.")
        return []
    
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    jql = f"updated >= '{date_from}' AND assignee = currentUser() ORDER BY updated DESC"
    
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
        return []


def extract_benefit_from_ticket(ticket: Dict) -> str:
    """
    Analyze ticket to extract business benefit/value.
    Creates specific, actionable benefit statements.
    """
    fields = ticket.get("fields", {})
    summary = fields.get("summary", "")
    description = fields.get("description", "") or ""
    issue_type = fields.get("issuetype", {}).get("name", "")
    
    # Combine summary and description for analysis
    text = f"{summary} {description}".lower()
    summary_lower = summary.lower()
    
    # More specific benefit extraction based on common patterns
    benefit = None
    
    # Deployment related
    if "deploy" in summary_lower and ("aoi" in summary_lower or "model" in summary_lower):
        benefit = "Deployed AOI model to production environments for enhanced accuracy"
    elif "deploy" in summary_lower:
        benefit = f"Deployed {summary.split('Deploy')[1].strip() if 'Deploy' in summary else 'updates'} to production"
    
    # GitHub Actions / CI/CD
    elif "github" in summary_lower and ("workflow" in summary_lower or "action" in summary_lower):
        if "lambda" in summary_lower:
            benefit = "Created GitHub Actions CI/CD workflow for automated Lambda deployment"
        elif "validation" in summary_lower or "test" in summary_lower:
            benefit = "Set up automated validation workflow with GitHub Actions"
        else:
            benefit = "Enhanced CI/CD pipeline with GitHub Actions automation"
    
    # SNS / Event triggers
    elif "sns" in summary_lower or ("trigger" in summary_lower and "store" in summary_lower):
        benefit = "Added SNS topic trigger for improved event-driven architecture"
    
    # Lambda migrations
    elif "move" in summary_lower and "lambda" in summary_lower:
        if "ml-training" in summary_lower:
            benefit = "Migrated Lambda functions to ml-training repo for better code organization"
        else:
            benefit = "Reorganized Lambda functions for improved maintainability"
    
    # Pipeline improvements
    elif "pipeline" in summary_lower:
        if "beta" in summary_lower and "retry" in summary_lower:
            benefit = "Enhanced beta pipeline with improved retry logic for better reliability"
        elif "beta" in summary_lower:
            benefit = "Improved beta pipeline functionality for parallel testing"
        elif "cleanup" in summary_lower and "error" in summary_lower:
            benefit = "Enhanced pipeline error handling and cleanup processes"
        elif "cleanup" in summary_lower:
            benefit = "Optimized pipeline cleanup for better resource management"
        else:
            benefit = "Improved pipeline functionality and reliability"
    
    # Model integration
    elif "aoi" in summary_lower or ("model" in summary_lower and "integrate" in summary_lower):
        if "alignment" in summary_lower or "camera" in summary_lower:
            benefit = "Integrated AOI model results with camera alignment detection for backend consumers"
        else:
            benefit = "Integrated AOI model results into pipeline output"
    
    # Testing / Validation
    elif "test" in summary_lower or "validation" in summary_lower:
        if "stress" in summary_lower:
            benefit = "Updated stress test cases for improved test automation"
        elif "image" in summary_lower:
            benefit = "Developed image validation tool for deployment quality assurance"
        else:
            benefit = "Enhanced testing and validation processes"
    
    # SplitIntoBatch / Batch processing
    elif "split" in summary_lower and "batch" in summary_lower:
        if "image" in summary_lower or "session" in summary_lower:
            benefit = "Optimized batch processing for sessions with fewer images"
        else:
            benefit = "Improved batch processing efficiency"
    
    # Error handling
    elif "error" in summary_lower or "session error" in summary_lower:
        if "cleanup" in summary_lower:
            benefit = "Improved error handling with automatic cleanup on session errors"
        else:
            benefit = "Enhanced error handling and recovery mechanisms"
    
    # Self-sufficiency / Infrastructure
    elif "self sufficiency" in summary_lower or "self-sufficiency" in summary_lower:
        benefit = "Working on model endpoint self-sufficiency for improved independence"
    
    # If no specific pattern matched, create a benefit from the summary
    if not benefit:
        # Try to make it more benefit-focused
        if issue_type == "Story":
            # For stories, focus on what was delivered
            if "update" in summary_lower:
                benefit = f"Updated {summary.split('Update')[1].strip() if 'Update' in summary else 'system components'}"
            elif "add" in summary_lower:
                benefit = f"Added {summary.split('add')[1].strip() if 'add' in summary else 'new functionality'}"
            else:
                benefit = summary
        elif issue_type == "Task":
            benefit = summary
        else:
            benefit = summary
    
    return benefit


def categorize_tickets(tickets: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Categorize tickets into This Week and Next Week."""
    this_week = []
    next_week = []
    
    for ticket in tickets:
        status = ticket.get("fields", {}).get("status", {}).get("name", "")
        
        if any(s.lower() in status.lower() for s in THIS_WEEK_STATUSES):
            this_week.append(ticket)
        elif any(s.lower() in status.lower() for s in NEXT_WEEK_STATUSES):
            next_week.append(ticket)
        else:
            # Default to this week if status is unclear
            this_week.append(ticket)
    
    return this_week, next_week


def group_similar_benefits(tickets: List[Dict]) -> List[Tuple[str, str]]:
    """Extract and deduplicate benefits from tickets, returning (benefit, ticket_key) tuples."""
    benefits = []
    seen_benefits = set()
    
    for ticket in tickets:
        benefit = extract_benefit_from_ticket(ticket)
        ticket_key = ticket.get("key", "")
        
        # Normalize for deduplication (case-insensitive, ignore minor variations)
        normalized = benefit.lower().strip()
        
        # Skip if we've seen a very similar benefit
        if normalized not in seen_benefits:
            # Check for similar benefits (fuzzy matching)
            is_duplicate = False
            for seen in seen_benefits:
                # If benefits are very similar (one contains the other or vice versa)
                if len(normalized) > 20 and len(seen) > 20:
                    if normalized in seen or seen in normalized:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                benefits.append((benefit, ticket_key))
                seen_benefits.add(normalized)
    
    return benefits


def format_weekly_report(this_week_tickets: List[Dict], next_week_tickets: List[Dict]) -> str:
    """Format tickets into a high-level weekly report with bullet points and ticket numbers."""
    lines = []
    
    # This Week section
    lines.append("This Week:")
    lines.append("")
    
    if this_week_tickets:
        benefits = group_similar_benefits(this_week_tickets)
        for benefit, ticket_key in benefits:
            lines.append(f"• {benefit} [{ticket_key}]")
    else:
        lines.append("• No tickets completed this week.")
    
    lines.append("")
    lines.append("Next Week:")
    lines.append("")
    
    if next_week_tickets:
        benefits = group_similar_benefits(next_week_tickets)
        for benefit, ticket_key in benefits:
            lines.append(f"• {benefit} [{ticket_key}]")
    else:
        lines.append("• No tickets planned for next week.")
    
    return "\n".join(lines)


def get_output_path() -> Path:
    """Get the output path in 2026/YYYYMM format."""
    now = datetime.now()
    year = now.year
    month = now.strftime("%m")
    
    output_dir = workspace_root / "2026" / f"{year}{month}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"weekly_report_{now.strftime('%Y%m%d')}.md"
    return output_dir / filename


def generate_weekly_report(days: int = 14, save_to_file: bool = True) -> str:
    """Generate weekly report - can be called from MCP server or standalone."""
    tickets = get_jira_tickets(days=days)
    
    if not tickets:
        return "No tickets found for the specified time period."
    
    this_week, next_week = categorize_tickets(tickets)
    
    report = format_weekly_report(this_week, next_week)
    
    if save_to_file:
        output_file = get_output_path()
        try:
            with open(output_file, "w") as f:
                f.write(report)
            report += f"\n\n✅ Weekly report saved to: {output_file}"
        except Exception as e:
            report += f"\n\n⚠️ Warning: Could not save to file: {e}"
    
    return report


def main():
    print("Fetching Jira tickets and generating weekly report...")
    result = generate_weekly_report(days=14, save_to_file=True)
    
    print("\n" + "="*80)
    print(result)
    print("="*80)


if __name__ == "__main__":
    main()

