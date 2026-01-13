from __future__ import annotations

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ...errors import FetchError
from ...http import get_json
from ...models import BlogItem, FetchContext, Source

FOUNDERS_FUND_URL = "https://foundersfund.com/wp-json/wp/v2/posts?categories=21&per_page=30"


def source() -> Source:
    return Source(
        id="founders-fund-anatomy",
        name="Founders Fund Anatomy of Next",
        kind="blog",
        method="api",
        fetch=fetch_founders_fund,
    )


def fetch_founders_fund(ctx: FetchContext) -> list[BlogItem]:
    payload = get_json(ctx.session, FOUNDERS_FUND_URL)
    if not isinstance(payload, list):
        raise FetchError("Founders Fund payload invalid")
    items: list[BlogItem] = []
    for post in payload:
        title_html = (post.get("title") or {}).get("rendered")
        link = post.get("link")
        if not title_html or not link:
            continue
        title = _strip_tags(title_html)
        excerpt_html = (post.get("excerpt") or {}).get("rendered")
        content_html = (post.get("content") or {}).get("rendered")
        items.append(
            BlogItem(
                title=title,
                url=link,
                published_at=post.get("date"),
                author=None,
                summary=md(excerpt_html) if excerpt_html else None,
                content_markdown=md(content_html) if content_html else None,
            )
        )
    if not items:
        raise FetchError("Founders Fund list empty")
    return items


def _strip_tags(value: str) -> str:
    return BeautifulSoup(value, "lxml").get_text(" ", strip=True)
