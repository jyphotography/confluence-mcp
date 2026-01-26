# Setup Guide: Using .env with Cursor MCP

This guide will help you set up the Confluence MCP server with a `.env` file and configure it in Cursor.

## Step 1: Create Your .env File

1. Copy the example file:
   ```bash
   cd confluence-mcp
   cp env.example .env
   ```

2. Edit the `.env` file with your Confluence credentials:
   ```bash
   # Edit .env file
   nano .env
   # or use your preferred editor
   ```

3. Fill in your values:
   ```env
   CONFLUENCE_URL=https://your-domain.atlassian.net
   CONFLUENCE_EMAIL=your-email@example.com
   CONFLUENCE_API_TOKEN=your-api-token-here
   ```

## Step 2: Test Your Configuration

Before configuring Cursor, test that your credentials work:

```bash
python3 python/test_connection.py
```

If you see ✅ messages, your credentials are correct!

## Step 3: Configure Cursor MCP

### Option A: Python Script (Easiest - Recommended)

Run the Python script that reads your `.env` and generates the Cursor config:

```bash
python3 python/generate_cursor_config.py
```

This script will:
- Read your `.env` file automatically
- Find Cursor's config directory
- Create or merge the MCP configuration
- Set up everything with your credentials

### Option B: Shell Script

Alternatively, run the shell script:

```bash
chmod +x setup_cursor.sh
./setup_cursor.sh
```

### Option B: Manual Setup

1. **Find Cursor's MCP configuration file:**
   - On macOS: `~/Library/Application Support/Cursor/mcp.json`
   - On Linux: `~/.cursor/mcp.json`
   - On Windows: `%APPDATA%\Cursor\mcp.json`

2. **Create or edit the `mcp.json` file:**

   If the file doesn't exist, create it with:
   ```json
   {
     "mcpServers": {
       "confluence": {
         "command": "python3",
         "args": ["/path/to/confluence-mcp/python/server.py"],
         "env": {
           "CONFLUENCE_URL": "https://your-domain.atlassian.net",
           "CONFLUENCE_EMAIL": "your-email@example.com",
           "CONFLUENCE_API_TOKEN": "your-api-token"
         }
       }
     }
   }
   ```

   If the file already exists, add the `"confluence"` entry to the `"mcpServers"` object.

3. **Update the paths:**
   - Replace `/path/to/confluence-mcp/python/server.py` with the actual path to your `python/server.py`
   - Update the environment variables with your actual credentials

### Option C: Using .env File (Alternative)

If you prefer, you can configure Cursor to load from `.env` by using a wrapper script. However, the direct approach (Option B) is simpler and more reliable.

## Step 4: Restart Cursor

After configuring, **restart Cursor** completely (quit and reopen) for the MCP server to be loaded.

## Step 5: Verify It Works

Once Cursor restarts, you can test the MCP server by asking Cursor:

- "Search for pages about database design in Confluence"
- "What documentation exists about the Beta Pipeline?"
- "List all Confluence spaces"

If the MCP server is working, Cursor will be able to search and retrieve your Confluence pages.

## Troubleshooting

### "Missing required environment variables" error

- Make sure your `.env` file has all three variables set
- Check that there are no extra spaces or quotes
- Verify the file is named exactly `.env` (not `env` or `.env.txt`)

### MCP server not loading in Cursor

1. Check that `mcp.json` is in the correct location
2. Verify the path to `python/server.py` is correct and absolute
3. Make sure `python3` is in your PATH
4. Check Cursor's developer console for errors (Help → Toggle Developer Tools)

### Server.py error when run directly

**This is normal!** The server is designed to run via stdio communication with Cursor, not directly. Don't run `python3 python/server.py` manually - Cursor will start it automatically.

## Security Notes

- **Never commit your `.env` file** to version control (it's in `.gitignore`)
- Keep your API token secure
- The `.env` file contains sensitive credentials - protect it with appropriate file permissions

## Next Steps

Once set up, you can:
- Ask Cursor to search your Confluence documentation
- Have Cursor read design documents before making code changes
- Use Confluence as context for AI-assisted development

See `EXAMPLE_USAGE.md` for more use cases!

