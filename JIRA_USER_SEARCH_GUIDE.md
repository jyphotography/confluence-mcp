# Jira User Search Guide

## Summary: What Information is Needed?

**For Jira Cloud, you need the Account ID (cloud-id), NOT the email address.**

However, you can look up the Account ID from an email address using the Jira REST API.

## MCP Server Integration

**The Confluence MCP server now includes a `search_jira_tickets_by_email` tool** that automatically handles the Account ID lookup and ticket search. You can use it directly without needing to manually look up Account IDs.

**Usage in MCP:**
- Tool: `search_jira_tickets_by_email`
- Parameters:
  - `email` (required): User's email address
  - `days` (optional, default: 14): Number of days to look back
  - `search_type` (optional, default: "assignee"): "assignee", "reporter", or "all"

**Example:**
```
User: "What has user@example.com been working on?"
AI: [Uses search_jira_tickets_by_email tool automatically]
```

## How to Search for a Person's Work in Jira

### Option 1: Using Account ID (Recommended)

1. **Get the Account ID from email:**
   ```bash
   GET https://your-domain.atlassian.net/rest/api/3/user/search?query=email@domain.com
   ```
   
   Response will include:
   ```json
   {
     "accountId": "557058:xxxx-xxxx-xxxx-xxxx",
     "emailAddress": "user@example.com",
     "displayName": "User Name"
   }
   ```

2. **Use Account ID in JQL queries:**
   ```jql
   assignee = "557058:xxxx-xxxx-xxxx-xxxx"
   reporter = "557058:xxxx-xxxx-xxxx-xxxx"
   comment ~ "557058:xxxx-xxxx-xxxx-xxxx"
   ```

### Option 2: Using Email (Limited Support)

- Email addresses may not work directly in JQL queries
- Users can hide their email addresses in Jira
- **Recommendation: Always use Account ID**

## JQL Query Examples

### Find tickets assigned to a user in last 2 weeks:
```jql
updated >= '2025-01-01' AND assignee = "557058:xxxx-xxxx-xxxx-xxxx" ORDER BY updated DESC
```

### Find tickets reported by a user:
```jql
reporter = "557058:xxxx-xxxx-xxxx-xxxx" ORDER BY created DESC
```

### Find tickets where user commented:
```jql
comment ~ "557058:xxxx-xxxx-xxxx-xxxx" ORDER BY updated DESC
```

## Implementation Notes

### Current Code Status
- Existing code uses `currentUser()` which only works for the authenticated user
- To search for a specific person, you need to:
  1. Look up their Account ID from email using `/rest/api/3/user/search`
  2. Use the Account ID in JQL queries

### API Endpoints

**Get User Account ID:**
```
GET /rest/api/3/user/search?query={email}
Authorization: Basic {base64(email:api_token)}
```

**Search Issues:**
```
POST /rest/api/3/search/jql
{
  "jql": "assignee = \"{accountId}\" AND updated >= '{date}'",
  "fields": ["summary", "status", "issuetype", ...],
  "maxResults": 100
}
```

## References

- [Atlassian Support: Get Account ID](https://support.atlassian.com/atlassian-cloud/kb/get-an-atlassian-cloud-users-account-id/)
- [Jira REST API: User Search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-user-search/#api-rest-api-3-user-search-get)
- [Jira REST API: Search Issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/#api-rest-api-3-search-post)
