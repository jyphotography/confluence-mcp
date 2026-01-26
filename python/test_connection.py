#!/usr/bin/env python3
"""
Test script to verify Confluence MCP server configuration.
Run this to check if your credentials and connection are working.
"""

import asyncio
import os
import sys
from pathlib import Path

from confluence_client import ConfluenceClient


async def test_connection():
    """Test the Confluence connection."""
    # Load environment variables
    url = os.getenv("CONFLUENCE_URL")
    email = os.getenv("CONFLUENCE_EMAIL")
    api_token = os.getenv("CONFLUENCE_API_TOKEN")

    if not all([url, email, api_token]):
        print("❌ Missing required environment variables!")
        print("Please set:")
        print("  - CONFLUENCE_URL")
        print("  - CONFLUENCE_EMAIL")
        print("  - CONFLUENCE_API_TOKEN")
        print("\nYou can create a .env file or export them in your shell.")
        sys.exit(1)

    print(f"🔗 Connecting to Confluence at: {url}")
    print(f"📧 Using email: {email}")
    print()

    try:
        client = ConfluenceClient(url, email, api_token)

        # Test 1: List spaces
        print("📋 Test 1: Listing spaces...")
        spaces = await client.list_spaces(limit=5)
        print(f"✅ Found {spaces['total']} accessible space(s)")
        if spaces["spaces"]:
            print("   Sample spaces:")
            for space in spaces["spaces"][:3]:
                print(f"   - {space['name']} ({space['key']})")
        print()

        # Test 2: Search for pages
        print("🔍 Test 2: Searching for pages...")
        results = await client.search_pages("test", limit=3)
        print(f"✅ Search successful! Found {results['total_results']} page(s) matching 'test'")
        if results["pages"]:
            print("   Sample pages:")
            for page in results["pages"][:3]:
                print(f"   - {page['title']} (ID: {page['id']})")
        print()

        # Test 3: Get a specific page (if we found one)
        if results["pages"]:
            page_id = results["pages"][0]["id"]
            print(f"📄 Test 3: Getting page content for ID {page_id}...")
            page = await client.get_page(page_id)
            print(f"✅ Retrieved page: {page['title']}")
            print(f"   URL: {page['url']}")
            print()

        await client.close()
        print("✅ All tests passed! Your Confluence MCP server is configured correctly.")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Verify your CONFLUENCE_URL is correct (include https://)")
        print("2. Check that your API token is valid")
        print("3. Ensure your email matches your Confluence account")
        print("4. Verify you have network access to your Confluence instance")
        sys.exit(1)


if __name__ == "__main__":
    # Try to load .env file if it exists
    try:
        from dotenv import load_dotenv

        workspace_root = Path(__file__).resolve().parents[1]
        load_dotenv(workspace_root / ".env", override=False)
    except ImportError:
        # dotenv is optional
        pass

    asyncio.run(test_connection())

