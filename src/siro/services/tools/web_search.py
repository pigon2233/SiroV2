"""Optional web search tool. Off unless `SIRO_WEB_SEARCH` names a provider.

- `brave`: Brave Search API, needs `SIRO_BRAVE_API_KEY`.
- `searxng`: a self-hosted SearXNG with JSON output, needs `SIRO_SEARXNG_URL`.

Keyless scraping (DuckDuckGo, Bing) is not offered: both answer automated
clients with a challenge page. The query leaves this machine, so the gateway
ties availability to the cloud kill switch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import httpx

from siro.ports.models import ToolDefinition

WEB_SEARCH_TOOL = "web.search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
MAX_RESULTS = 8
_TEXT_LIMIT = 300

WEB_SEARCH_DEFINITION = ToolDefinition(
    WEB_SEARCH_TOOL,
    "Search the web and return result titles, URLs and short snippets. Use it to find a "
    "page when you do not know the address, then open the best URL with "
    "browser.navigate+read before stating facts; snippets alone are not a verified source.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 200},
            "count": {"type": "integer", "minimum": 1, "maximum": MAX_RESULTS},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)


class WebSearchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WebSearch:
    provider: str
    url: str
    key: str = ""
    timeout: float = 15.0
    transport: httpx.AsyncBaseTransport | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> WebSearch | None:
        """None when search is not configured; ValueError on a half-configured provider."""
        provider = env.get("SIRO_WEB_SEARCH", "").strip().lower()
        if not provider or provider == "off":
            return None
        if provider == "brave":
            key = env.get("SIRO_BRAVE_API_KEY", "").strip()
            if not key:
                raise ValueError("SIRO_WEB_SEARCH=brave needs SIRO_BRAVE_API_KEY")
            return cls("brave", BRAVE_URL, key)
        if provider == "searxng":
            base = env.get("SIRO_SEARXNG_URL", "").strip().rstrip("/")
            if not base.startswith(("http://", "https://")):
                raise ValueError("SIRO_WEB_SEARCH=searxng needs SIRO_SEARXNG_URL")
            return cls("searxng", base + "/search")
        raise ValueError("SIRO_WEB_SEARCH must be brave, searxng or off")

    async def execute(self, arguments: dict[str, object]) -> object:
        query = arguments.get("query")
        count = arguments.get("count", 5)
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            raise ValueError("query must be 1-200 characters")
        if type(count) is not int or not 1 <= count <= MAX_RESULTS:
            raise ValueError(f"count must be an integer between 1 and {MAX_RESULTS}")
        results = await self.search(query.strip(), count)
        return {"query": query.strip(), "provider": self.provider, "results": results}

    async def search(self, query: str, count: int = 5) -> list[dict[str, str]]:
        if self.provider == "brave":
            params: dict[str, str | int] = {"q": query, "count": count}
            headers = {"Accept": "application/json", "X-Subscription-Token": self.key}
        else:
            params, headers = {"q": query, "format": "json"}, {"Accept": "application/json"}
        try:
            async with httpx.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(self.url, params=params, headers=headers)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as error:
            raise WebSearchError(f"search_http_{error.response.status_code}") from None
        except (httpx.HTTPError, ValueError):
            raise WebSearchError("search_unavailable") from None
        if not isinstance(body, dict):
            raise WebSearchError("search_bad_response")
        holder = body if self.provider == "searxng" else body.get("web")
        raw = holder.get("results") if isinstance(holder, dict) else None
        snippet_key = "description" if self.provider == "brave" else "content"
        results: list[dict[str, str]] = []
        for item in raw if isinstance(raw, list) else ():
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            results.append(
                {
                    "title": str(item.get("title") or "")[:_TEXT_LIMIT],
                    "url": url[:2000],
                    "snippet": str(item.get(snippet_key) or "")[:_TEXT_LIMIT],
                }
            )
            if len(results) >= count:
                break
        return results
