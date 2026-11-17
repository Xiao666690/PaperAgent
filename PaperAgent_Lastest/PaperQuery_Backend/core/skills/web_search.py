"""Search public web indexes and normalize snippets for the research workflow."""
from html import unescape
import os
import re
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

from core.skills.base import BaseSkill, SkillResult


class WebSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    max_results: int = Field(default=6, ge=1, le=12)


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "检索公开网页，返回标题、来源链接及网页摘要"
    input_model = WebSearchInput

    @staticmethod
    def configured() -> bool:
        return bool(os.getenv("BRAVE_SEARCH_API_KEY", "").strip() or os.getenv("SEARXNG_URL", "").strip())

    async def execute(self, data: WebSearchInput, ctx: dict) -> SkillResult:
        brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
        searx_url = os.getenv("SEARXNG_URL", "").strip()
        if not brave_key and not searx_url:
            return SkillResult(ok=False, error_code="WEB_SEARCH_UNCONFIGURED", error_message="网页搜索服务未配置")

        try:
            async with httpx.AsyncClient(timeout=12) as client:
                if brave_key:
                    provider = "Brave Search"
                    response = await client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        params={"q": data.query, "count": data.max_results, "extra_snippets": "true"},
                        headers={"X-Subscription-Token": brave_key, "Accept": "application/json"},
                    )
                    response.raise_for_status()
                    items = response.json().get("web", {}).get("results", [])
                else:
                    provider = "SearXNG"
                    response = await client.get(
                        f"{searx_url.rstrip('/')}/search",
                        params={"q": data.query, "format": "json", "categories": "general"},
                    )
                    response.raise_for_status()
                    items = response.json().get("results", [])
        except (httpx.HTTPError, ValueError):
            return SkillResult(ok=False, error_code="WEB_SEARCH_UNAVAILABLE", error_message="网页搜索服务暂时不可用")

        sources = []
        for item in items:
            url = item.get("url", "")
            try:
                parts = urlsplit(url)
            except ValueError:
                continue
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
                continue
            title = self.clean(item.get("title"))
            if not title:
                continue
            snippets = [item.get("description") or item.get("content"), *(item.get("extra_snippets") or [])]
            summary = " ".join(dict.fromkeys(filter(None, map(self.clean, snippets))))
            sources.append({"title": title[:300], "url": url, "summary": summary[:2100],
                            "provider": provider, "venue": parts.hostname, "source_type": "web"})
            if len(sources) >= data.max_results:
                break
        return SkillResult(ok=True, output={"sources": sources})

    @staticmethod
    def clean(value) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(unescape(re.sub(r"<[^>]*>", " ", value)).split())
