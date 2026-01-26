#!/usr/bin/env python3
"""Quick script to search Confluence pages"""

import asyncio
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    workspace_root = Path(__file__).resolve().parents[1]
    load_dotenv(workspace_root / ".env")
except ImportError:
    pass

from confluence_client import ConfluenceClient


async def search(query: str, limit: int = 10):
    client = ConfluenceClient(
        os.getenv("CONFLUENCE_URL"),
        os.getenv("CONFLUENCE_EMAIL"),
        os.getenv("CONFLUENCE_API_TOKEN"),
    )

    results = await client.search_pages(query, limit=limit)
    print(f'🔍 Found {results["total_results"]} page(s) matching "{query}":\n')

    for i, page in enumerate(results["pages"], 1):
        print(f'{i}. {page["title"]}')
        if page.get("space"):
            print(f'   📁 Space: {page["space"]["name"]} ({page["space"]["key"]})')
        print(f'   🔗 URL: {page["url"]}')
        if page.get("excerpt"):
            excerpt = page["excerpt"][:200].replace("\n", " ").strip()
            if excerpt:
                print(f"   📄 {excerpt}...")
        print()

    await client.close()


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "database design"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    asyncio.run(search(query, limit))

