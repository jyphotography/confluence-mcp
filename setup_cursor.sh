#!/bin/bash
# Setup script for Cursor MCP configuration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PATH="$SCRIPT_DIR/python/server.py"

echo "🔧 Setting up Confluence MCP for Cursor"
echo ""

# Check if .env file exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp "$SCRIPT_DIR/env.example" "$SCRIPT_DIR/.env"
    echo "✅ Created .env file. Please edit it with your Confluence credentials."
    echo ""
fi

# Determine Cursor config location
CURSOR_CONFIG_DIR=""
if [ -d "$HOME/.cursor" ]; then
    CURSOR_CONFIG_DIR="$HOME/.cursor"
elif [ -d "$HOME/Library/Application Support/Cursor" ]; then
    CURSOR_CONFIG_DIR="$HOME/Library/Application Support/Cursor"
else
    echo "❌ Could not find Cursor configuration directory"
    echo "   Please manually configure MCP in Cursor settings"
    exit 1
fi

MCP_CONFIG_FILE="$CURSOR_CONFIG_DIR/mcp.json"

echo "📝 Cursor MCP configuration will be written to:"
echo "   $MCP_CONFIG_FILE"
echo ""

# Read .env file
source "$SCRIPT_DIR/.env"

if [ -z "$CONFLUENCE_URL" ] || [ -z "$CONFLUENCE_EMAIL" ] || [ -z "$CONFLUENCE_API_TOKEN" ]; then
    echo "❌ Missing required values in .env file"
    echo "   Please set: CONFLUENCE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN"
    exit 1
fi

# Create MCP config JSON
CONFIG_JSON=$(cat <<EOF
{
  "mcpServers": {
    "confluence": {
      "command": "python3",
      "args": ["$SERVER_PATH"],
      "env": {
        "CONFLUENCE_URL": "$CONFLUENCE_URL",
        "CONFLUENCE_EMAIL": "$CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN": "$CONFLUENCE_API_TOKEN"
      }
    }
  }
}
EOF
)

# Check if mcp.json already exists
if [ -f "$MCP_CONFIG_FILE" ]; then
    echo "⚠️  $MCP_CONFIG_FILE already exists"
    echo ""
    echo "Current contents:"
    cat "$MCP_CONFIG_FILE"
    echo ""
    read -p "Do you want to merge with existing config? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Try to merge (this is a simple merge - you may need to edit manually)
        echo "📝 Please manually merge the confluence server config into your existing mcp.json"
        echo ""
        echo "Add this to the 'mcpServers' object:"
        echo "$CONFIG_JSON" | jq '.mcpServers.confluence'
        exit 0
    else
        echo "Skipping merge. Please configure manually."
        exit 0
    fi
fi

# Write config file
echo "$CONFIG_JSON" > "$MCP_CONFIG_FILE"

echo "✅ MCP configuration created successfully!"
echo ""
echo "📋 Next steps:"
echo "   1. Restart Cursor to load the MCP server"
echo "   2. The Confluence MCP tools should now be available"
echo ""
echo "🔍 To verify, try asking Cursor to search your Confluence pages!"







