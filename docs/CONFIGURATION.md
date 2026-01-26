# Confluence MCP Server Configuration Guide

> **📖 For detailed setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md)**

## Quick Setup

### Step 1: Create .env File

```bash
cd confluence-mcp
cp env.example .env
# Edit .env with your credentials
```

### Step 2: Configure Cursor

**Option A: Automated (Recommended)**
```bash
./setup_cursor.sh
```

**Option B: Manual Configuration**

Add to your Cursor MCP configuration file:
- macOS: `~/Library/Application Support/Cursor/mcp.json`
- Linux: `~/.cursor/mcp.json`
- Windows: `%APPDATA%\Cursor\mcp.json`

```json
{
  "mcpServers": {
    "confluence": {
      "command": "python3",
      "args": ["/absolute/path/to/confluence-mcp/python/server.py"],
      "env": {
        "CONFLUENCE_URL": "https://your-domain.atlassian.net",
        "CONFLUENCE_EMAIL": "your-email@example.com",
        "CONFLUENCE_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

**Important:** Replace `/absolute/path/to/confluence-mcp/python/server.py` with the actual absolute path to your `python/server.py` file.

### Step 3: Restart Cursor

After configuration, restart Cursor completely for the MCP server to load.

## Setting Up in Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "confluence": {
      "command": "python3",
      "args": ["/absolute/path/to/confluence-mcp/python/server.py"],
      "env": {
        "CONFLUENCE_URL": "https://your-domain.atlassian.net",
        "CONFLUENCE_EMAIL": "your-email@example.com",
        "CONFLUENCE_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

## Getting Your Confluence API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a label (e.g., "MCP Server")
4. Copy the token immediately (you won't be able to see it again)
5. Use this token in your configuration

## Testing the Server

You can test the server manually:

```bash
cd confluence-mcp
python3 python/server.py
```

The server communicates via stdio, so it's designed to be used by MCP clients, not directly.

## Troubleshooting

### "Missing required environment variables" error
- Ensure all three environment variables are set: `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`
- Check that there are no extra spaces or quotes in your values

### Authentication errors
- Verify your API token is correct
- Make sure your email matches your Confluence account email
- For Confluence Server, you may need to use username instead of email

### Connection errors
- Verify your Confluence URL is correct (include `https://`)
- Check that your Confluence instance is accessible
- For Confluence Server, ensure REST API is enabled

### Permission errors
- The API token inherits permissions from the user account
- Ensure the account has permission to view the spaces/pages you're trying to access
