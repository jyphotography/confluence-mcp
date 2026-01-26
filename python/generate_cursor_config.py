#!/usr/bin/env python3
"""
Generate Cursor MCP configuration from .env file
"""

import json
import os
import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]

# Try to load .env
try:
    from dotenv import load_dotenv

    env_path = workspace_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print("⚠️  No .env file found. Please create one from env.example")
        sys.exit(1)
except ImportError:
    print("⚠️  python-dotenv not installed. Install it with: pip install python-dotenv")
    print("   Or set environment variables manually.")
    sys.exit(1)

# Get values from environment
url = os.getenv("CONFLUENCE_URL")
email = os.getenv("CONFLUENCE_EMAIL")
api_token = os.getenv("CONFLUENCE_API_TOKEN")

if not all([url, email, api_token]):
    print("❌ Missing required environment variables in .env file:")
    missing = []
    if not url:
        missing.append("CONFLUENCE_URL")
    if not email:
        missing.append("CONFLUENCE_EMAIL")
    if not api_token:
        missing.append("CONFLUENCE_API_TOKEN")
    print(f"   Missing: {', '.join(missing)}")
    sys.exit(1)

# Get absolute path to python/server.py
server_path = Path(__file__).parent / "server.py"
server_abs_path = str(server_path.resolve())

# Generate config
config = {
    "mcpServers": {
        "confluence": {
            "command": "python3",
            "args": [server_abs_path],
            "env": {
                "CONFLUENCE_URL": url,
                "CONFLUENCE_EMAIL": email,
                "CONFLUENCE_API_TOKEN": api_token,
            },
        }
    }
}

# Determine Cursor config location
home = Path.home()
cursor_config_paths = [
    home / "Library" / "Application Support" / "Cursor" / "mcp.json",
    home / ".cursor" / "mcp.json",
]

cursor_config_path = None
for path in cursor_config_paths:
    if path.parent.exists():
        cursor_config_path = path
        break

if not cursor_config_path:
    print("❌ Could not determine Cursor config location")
    print("   Please manually create mcp.json in one of these locations:")
    for path in cursor_config_paths:
        print(f"   - {path}")
    print("\n📋 Here's your configuration JSON:")
    print(json.dumps(config, indent=2))
    sys.exit(1)

print(f"📝 Cursor MCP config location: {cursor_config_path}")
print()

# Check if file exists
if cursor_config_path.exists():
    try:
        with open(cursor_config_path, "r") as f:
            existing_config = json.load(f)

        if "mcpServers" in existing_config and "confluence" in existing_config.get("mcpServers", {}):
            print("⚠️  Confluence MCP server already configured!")
            print("   Current config:")
            print(json.dumps(existing_config["mcpServers"]["confluence"], indent=2))
            print()
            response = input("Replace existing configuration? (y/n): ")
            if response.lower() != "y":
                print("Cancelled.")
                sys.exit(0)

            # Merge with existing
            existing_config["mcpServers"]["confluence"] = config["mcpServers"]["confluence"]
            config = existing_config
        else:
            # Merge into existing
            if "mcpServers" not in existing_config:
                existing_config["mcpServers"] = {}
            existing_config["mcpServers"]["confluence"] = config["mcpServers"]["confluence"]
            config = existing_config
    except json.JSONDecodeError:
        print("⚠️  Existing config file is not valid JSON")
        response = input("Overwrite it? (y/n): ")
        if response.lower() != "y":
            print("Cancelled.")
            sys.exit(0)

# Write config
cursor_config_path.parent.mkdir(parents=True, exist_ok=True)
with open(cursor_config_path, "w") as f:
    json.dump(config, f, indent=2)

print("✅ Cursor MCP configuration created successfully!")
print()
print("📋 Next steps:")
print("   1. Restart Cursor completely (quit and reopen)")
print("   2. The Confluence MCP tools should now be available")
print("   3. Try asking Cursor to search your Confluence pages!")

