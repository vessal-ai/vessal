"""Web search and page reading via 302AI API."""

import json
import os
import urllib.error
import urllib.request

from vessal.ark.shell.hull.skill import SkillBase


class Search(SkillBase):
    name = "search"
    description = "web search & read"

    _BASE = "https://api.302.ai"

    def __init__(self):
        super().__init__()
        self._api_key = os.environ.get("API_302AI_KEY", "")

    # -- Agent API --

    def web(self, query: str, count: int = 5) -> list[dict]:
        """Search the web, returning [{name, url, snippet, summary}]."""
        data = self._post("/unifuncs/api/web-search/search", {
            "query": query,
            "count": count,
            "page": 1,
            "summary": True,
        })
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Search failed: {data.get('message', 'unknown')}")
        results = []
        for p in data.get("data", {}).get("webPages", []):
            results.append({
                "name": p.get("name", ""),
                "url": p.get("url", ""),
                "snippet": p.get("snippet", ""),
                "summary": p.get("summary", ""),
            })
        print(f"[search] found {len(results)} result(s)")
        return results

    def read(self, url: str, lite: bool = True) -> str:
        """Fetch a web page and return its content as markdown text."""
        data = self._post("/unifuncs/api/web-reader/read", {
            "url": url,
            "format": "md",
            "liteMode": lite,
        })
        if isinstance(data, dict) and data.get("code", 0) != 0:
            raise RuntimeError(f"Read failed: {data.get('message', 'unknown')}")
        content = data.get("data", "") if isinstance(data, dict) else str(data)
        print(f"[search] read {url[:60]}{'...' if len(url) > 60 else ''} ({len(content)} chars)")
        return content

    # -- internal --

    def _post(self, path: str, body: dict) -> dict | str:
        if not self._api_key:
            raise RuntimeError("Environment variable API_302AI_KEY is not set")
        payload = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self._BASE}{path}",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {path}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}") from e
