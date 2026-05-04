"""
Web Search tool - Search the web using Bocha search API.
"""

import os
import json
from typing import Dict, Any, Optional

import requests

from agent.tools.base_tool import BaseTool, ToolResult
from common.log import logger


# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT = 30


class WebSearch(BaseTool):
    """Tool for searching the web using Bocha search API"""

    name: str = "web_search"
    description: str = "Search the web for real-time information. Returns titles, URLs, and snippets."

    params: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string"
            },
            "count": {
                "type": "integer",
                "description": "Number of results to return (1-50, default: 10)"
            },
            "freshness": {
                "type": "string",
                "description": (
                    "Time range filter. Options: "
                    "'noLimit' (default), 'oneDay', 'oneWeek', 'oneMonth', 'oneYear', "
                    "or date range like '2025-01-01..2025-02-01'"
                )
            },
            "summary": {
                "type": "boolean",
                "description": "Whether to include text summary for each result (default: false)"
            }
        },
        "required": ["query"]
    }

    def __init__(self, config: dict = None):
        self.config = config or {}

    @staticmethod
    def is_available() -> bool:
        """Check if web search is available (BOCHA_API_KEY is configured)"""
        return bool(os.environ.get("BOCHA_API_KEY"))

    @staticmethod
    def _resolve_backend() -> Optional[str]:
        """
        Determine which search backend to use.

        :return: 'bocha' or None
        """
        if os.environ.get("BOCHA_API_KEY"):
            return "bocha"
        return None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute web search

        :param args: Search parameters (query, count, freshness, summary)
        :return: Search results
        """
        query = args.get("query", "").strip()
        if not query:
            return ToolResult.fail("Error: 'query' parameter is required")

        count = args.get("count", 10)
        freshness = args.get("freshness", "noLimit")
        summary = args.get("summary", False)

        # Validate count
        if not isinstance(count, int) or count < 1 or count > 50:
            count = 10

        # Resolve backend
        backend = self._resolve_backend()
        if not backend:
            return ToolResult.fail(
                "Error: No search API key configured. "
                "Please set BOCHA_API_KEY using env_config tool.\n"
                "  - Bocha Search: https://open.bocha.cn"
            )

        try:
            return self._search_bocha(query, count, freshness, summary)
        except requests.Timeout:
            return ToolResult.fail(f"Error: Search request timed out after {DEFAULT_TIMEOUT}s")
        except requests.ConnectionError:
            return ToolResult.fail("Error: Failed to connect to search API")
        except Exception as e:
            logger.error(f"[WebSearch] Unexpected error: {e}", exc_info=True)
            return ToolResult.fail(f"Error: Search failed - {str(e)}")

    def _search_bocha(self, query: str, count: int, freshness: str, summary: bool) -> ToolResult:
        """
        Search using Bocha API

        :param query: Search query
        :param count: Number of results
        :param freshness: Time range filter
        :param summary: Whether to include summary
        :return: Formatted search results
        """
        api_key = os.environ.get("BOCHA_API_KEY", "")
        url = "https://api.bocha.cn/v1/web-search"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "query": query,
            "count": count,
            "freshness": freshness,
            "summary": summary
        }

        logger.debug(f"[WebSearch] Bocha search: query='{query}', count={count}")

        response = requests.post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)

        if response.status_code == 401:
            return ToolResult.fail("Error: Invalid BOCHA_API_KEY. Please check your API key.")
        if response.status_code == 403:
            return ToolResult.fail("Error: Bocha API - insufficient balance. Please top up at https://open.bocha.cn")
        if response.status_code == 429:
            return ToolResult.fail("Error: Bocha API rate limit reached. Please try again later.")
        if response.status_code != 200:
            return ToolResult.fail(f"Error: Bocha API returned HTTP {response.status_code}")

        data = response.json()

        # Check API-level error code
        api_code = data.get("code")
        if api_code is not None and api_code != 200:
            msg = data.get("msg") or "Unknown error"
            return ToolResult.fail(f"Error: Bocha API error (code={api_code}): {msg}")

        # Extract and format results
        return self._format_bocha_results(data, query)

    def _format_bocha_results(self, data: dict, query: str) -> ToolResult:
        """
        Format Bocha API response into unified result structure

        :param data: Raw API response
        :param query: Original query
        :return: Formatted ToolResult
        """
        search_data = data.get("data", {})
        web_pages = search_data.get("webPages", {})
        pages = web_pages.get("value", [])

        if not pages:
            return ToolResult.success({
                "query": query,
                "backend": "bocha",
                "total": 0,
                "results": [],
                "message": "No results found"
            })

        results = []
        for page in pages:
            result = {
                "title": page.get("name", ""),
                "url": page.get("url", ""),
                "snippet": page.get("snippet", ""),
                "siteName": page.get("siteName", ""),
                "datePublished": page.get("datePublished") or page.get("dateLastCrawled", ""),
            }
            # Include summary only if present
            if page.get("summary"):
                result["summary"] = page["summary"]
            results.append(result)

        total = web_pages.get("totalEstimatedMatches", len(results))

        return ToolResult.success({
            "query": query,
            "backend": "bocha",
            "total": total,
            "count": len(results),
            "results": results
        })
