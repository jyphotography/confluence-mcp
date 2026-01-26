# Example Usage Scenarios

This document shows how the Confluence MCP server can be used in practice.

## Scenario 1: Understanding Design Before Making Changes

**User Request:**
> "I want to update the database schema. Can you check the existing design documentation first?"

**AI Assistant Workflow:**
1. Uses `search_pages` tool with query "database schema design"
2. Reviews search results to find relevant pages
3. Uses `get_page_content` to retrieve the full design document
4. Analyzes the existing design
5. Suggests changes that align with the existing architecture

**Example Tool Calls:**
```json
// Step 1: Search for relevant pages
{
  "tool": "search_pages",
  "arguments": {
    "query": "database schema design",
    "limit": 5
  }
}

// Step 2: Get full content of the most relevant page
{
  "tool": "get_page_content",
  "arguments": {
    "page_id": "123456"
  }
}
```

## Scenario 2: Finding Related Documentation

**User Request:**
> "What documentation exists about the Beta Pipeline?"

**AI Assistant Workflow:**
1. Uses `search_by_title` to find pages with "Beta Pipeline" in the title
2. Uses `search_pages` with broader query to find related content
3. Lists all found pages with summaries
4. Can retrieve specific pages if user wants more details

## Scenario 3: Context-Aware Code Changes

**User Request:**
> "Update the payment gateway code to add support for new card types"

**AI Assistant Workflow:**
1. Uses `search_pages` to find payment gateway documentation
2. Uses `get_page_content` to read design specifications
3. Understands current card type support and validation rules
4. Suggests code changes that maintain compatibility with existing design
5. References the documentation in code comments

## Scenario 4: Discovering Available Documentation

**User Request:**
> "What documentation spaces are available?"

**AI Assistant Workflow:**
1. Uses `list_spaces` to show all accessible spaces
2. Can then search within specific spaces using `space_key` parameter
3. Helps user navigate the documentation structure

## Scenario 5: Multi-Page Context Gathering

**User Request:**
> "I need to understand the full ML pipeline architecture"

**AI Assistant Workflow:**
1. Searches for "ML pipeline" pages
2. Retrieves multiple related pages
3. Combines context from all pages
4. Provides comprehensive understanding before suggesting changes
5. Ensures changes are consistent across all related documentation

## Scenario 6: Understanding Team Member's Work

**User Request:**
> "What has user@example.com been working on in the last 2 weeks?"

**AI Assistant Workflow:**
1. Uses `search_jira_tickets_by_email` tool with the user's email
2. Tool automatically looks up the user's Account ID from their email
3. Searches for tickets assigned to or reported by that user
4. Groups results by status (In Progress, Done, To Do, etc.)
5. Provides a formatted summary of their recent work

**Example Tool Call:**
```json
{
  "tool": "search_jira_tickets_by_email",
  "arguments": {
    "email": "user@example.com",
    "days": 14,
    "search_type": "all"
  }
}
```

**Use Cases:**
- Understanding what a team member has been working on
- Preparing for team meetings or standups
- Identifying collaboration opportunities
- Tracking project progress across team members

## Best Practices

1. **Always Search First**: Before making changes, search for existing documentation
2. **Get Full Context**: Use `get_page_content` to understand complete page context
3. **Check Related Pages**: Look for related or parent pages using page metadata
4. **Respect Space Organization**: Use `space_key` to search within specific documentation spaces
5. **Version Awareness**: Check page versions to understand when documentation was last updated

## Integration with Code Changes

The MCP server enables AI assistants to:

- **Read before writing**: Understand existing patterns and conventions
- **Maintain consistency**: Ensure new code matches documented architecture
- **Reference documentation**: Link code changes to relevant documentation
- **Update documentation**: Know what needs to be updated when code changes
- **Avoid breaking changes**: Understand dependencies and relationships







