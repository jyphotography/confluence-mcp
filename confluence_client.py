"""
Confluence API Client
Handles all interactions with the Confluence REST API.
"""

import base64
from typing import Optional, Dict, Any
import httpx


class ConfluenceClient:
    """Client for interacting with Confluence REST API."""
    
    def __init__(self, base_url: str, email: str, api_token: str):
        """
        Initialize the Confluence client.
        
        Args:
            base_url: Confluence instance URL (e.g., https://your-domain.atlassian.net)
            email: Confluence email/username
            api_token: Confluence API token
        """
        self.base_url = base_url.rstrip('/')
        self.email = email
        self.api_token = api_token
        
        # Detect if this is Confluence Cloud (contains .atlassian.net)
        # Cloud uses /wiki/rest/api/, Server uses /rest/api/
        if '.atlassian.net' in self.base_url.lower():
            self.api_base_path = "/wiki/rest/api"
        else:
            self.api_base_path = "/rest/api"
        
        # Create basic auth header
        credentials = f"{email}:{api_token}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0
        )
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request to the Confluence API."""
        # Remove leading slash from endpoint if present, then construct full path
        endpoint_clean = endpoint.lstrip('/')
        url = f"{self.api_base_path}/{endpoint_clean}"
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    
    async def search_pages(
        self,
        query: str,
        space_key: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for pages using Confluence CQL (Confluence Query Language).
        
        Args:
            query: Search query
            space_key: Optional space key to limit search
            limit: Maximum number of results
        
        Returns:
            Dictionary containing search results
        """
        # Build CQL query
        cql_query = f"text ~ \"{query}\""
        if space_key:
            cql_query = f"space = {space_key} AND {cql_query}"
        
        params = {
            "cql": cql_query,
            "limit": limit,
            "expand": "space,version"
        }
        
        result = await self._request("GET", "/content/search", params=params)
        
        # Format results for easier consumption
        formatted_results = {
            "query": query,
            "total_results": result.get("size", 0),
            "pages": []
        }
        
        for page in result.get("results", []):
            formatted_results["pages"].append({
                "id": page.get("id"),
                "title": page.get("title"),
                "type": page.get("type"),
                "space": {
                    "key": page.get("space", {}).get("key"),
                    "name": page.get("space", {}).get("name")
                } if page.get("space") else None,
                "url": f"{self.base_url}{page.get('_links', {}).get('webui', '')}",
                "version": page.get("version", {}).get("number") if page.get("version") else None,
                "excerpt": page.get("excerpt", "").replace("<br/>", "\n")
            })
        
        return formatted_results
    
    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Get a page by ID.
        
        Args:
            page_id: The page ID
        
        Returns:
            Page metadata
        """
        result = await self._request(
            "GET",
            f"/content/{page_id}",
            params={"expand": "space,version,ancestors"}
        )
        
        return {
            "id": result.get("id"),
            "title": result.get("title"),
            "type": result.get("type"),
            "space": {
                "key": result.get("space", {}).get("key"),
                "name": result.get("space", {}).get("name")
            } if result.get("space") else None,
            "url": f"{self.base_url}{result.get('_links', {}).get('webui', '')}",
            "version": {
                "number": result.get("version", {}).get("number"),
                "by": result.get("version", {}).get("by", {}).get("displayName"),
                "when": result.get("version", {}).get("when")
            } if result.get("version") else None,
            "ancestors": [
                {"id": a.get("id"), "title": a.get("title")}
                for a in result.get("ancestors", [])
            ]
        }
    
    async def get_page_content(
        self,
        page_id: str,
        expand: str = "body.storage,version,space"
    ) -> Dict[str, Any]:
        """
        Get full page content including body.
        
        Args:
            page_id: The page ID
            expand: Comma-separated list of fields to expand
        
        Returns:
            Full page content
        """
        result = await self._request(
            "GET",
            f"/content/{page_id}",
            params={"expand": expand}
        )
        
        # Extract body content
        body_storage = result.get("body", {}).get("storage", {})
        body_content = body_storage.get("value", "") if body_storage else ""
        
        return {
            "id": result.get("id"),
            "title": result.get("title"),
            "type": result.get("type"),
            "space": {
                "key": result.get("space", {}).get("key"),
                "name": result.get("space", {}).get("name")
            } if result.get("space") else None,
            "url": f"{self.base_url}{result.get('_links', {}).get('webui', '')}",
            "version": {
                "number": result.get("version", {}).get("number"),
                "by": result.get("version", {}).get("by", {}).get("displayName"),
                "when": result.get("version", {}).get("when")
            } if result.get("version") else None,
            "body": {
                "format": body_storage.get("representation", ""),
                "content": body_content
            },
            "created": result.get("version", {}).get("when"),
            "modified": result.get("version", {}).get("when")
        }
    
    async def list_spaces(self, limit: int = 50) -> Dict[str, Any]:
        """
        List all accessible spaces.
        
        Args:
            limit: Maximum number of spaces to return
        
        Returns:
            List of spaces
        """
        result = await self._request(
            "GET",
            "/space",
            params={"limit": limit, "expand": "homepage"}
        )
        
        formatted_spaces = {
            "total": result.get("size", 0),
            "spaces": []
        }
        
        for space in result.get("results", []):
            formatted_spaces["spaces"].append({
                "key": space.get("key"),
                "name": space.get("name"),
                "type": space.get("type"),
                "url": f"{self.base_url}{space.get('_links', {}).get('webui', '')}",
                "homepage_id": space.get("homepage", {}).get("id") if space.get("homepage") else None
            })
        
        return formatted_spaces
    
    async def search_by_title(
        self,
        title: str,
        space_key: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for pages by title.
        
        Args:
            title: Page title to search for
            space_key: Optional space key to limit search
            limit: Maximum number of results
        
        Returns:
            Dictionary containing search results
        """
        # Build CQL query for title search
        cql_query = f"title ~ \"{title}\""
        if space_key:
            cql_query = f"space = {space_key} AND {cql_query}"
        
        params = {
            "cql": cql_query,
            "limit": limit,
            "expand": "space,version"
        }
        
        result = await self._request("GET", "/content/search", params=params)
        
        # Format results
        formatted_results = {
            "title_query": title,
            "total_results": result.get("size", 0),
            "pages": []
        }
        
        for page in result.get("results", []):
            formatted_results["pages"].append({
                "id": page.get("id"),
                "title": page.get("title"),
                "type": page.get("type"),
                "space": {
                    "key": page.get("space", {}).get("key"),
                    "name": page.get("space", {}).get("name")
                } if page.get("space") else None,
                "url": f"{self.base_url}{page.get('_links', {}).get('webui', '')}",
                "version": page.get("version", {}).get("number") if page.get("version") else None
            })
        
        return formatted_results
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

