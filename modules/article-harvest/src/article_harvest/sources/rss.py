from __future__ import annotations

from collections.abc import Callable
from typing import Any

import feedparser
from markdownify import markdownify as md

from ..errors import FetchError
from ..http import get_bytes
from ..models import BlogItem, FetchContext, Source


def make_rss_source(
    source_id: str,
    name: str,
    feed_url: str,
    *,
    html_to_markdown: Callable[[str], str] | None = None,
) -> Source:
    return Source(
        id=source_id,
        name=name,
        kind="blog",
        method="rss",
        fetch=lambda ctx: fetch_rss(ctx, feed_url, html_to_markdown=html_to_markdown),
    )


def fetch_rss(
    ctx: FetchContext,
    feed_url: str,
    limit: int | None = None,
    *,
    html_to_markdown: Callable[[str], str] | None = None,
) -> list[BlogItem]:
    data = feedparser.parse(get_bytes(ctx.session, feed_url))
    if data.bozo:
        raise FetchError(f"RSS parse error for {feed_url}")
    items: list[BlogItem] = []
    for entry in data.entries[:limit]:
        title = entry.get("title")
        link = entry.get("link")
        if not title or not link:
            continue
        published = entry.get("published") or entry.get("updated")
        author = entry.get("author")
        summary = entry.get("summary")
        content_html = _extract_content_html(entry)
        if content_html:
            content_markdown = (
                html_to_markdown(content_html) if html_to_markdown else md(content_html)
            )
        else:
            content_markdown = summary or ""
        items.append(
            BlogItem(
                title=str(title),
                url=str(link),
                published_at=str(published) if published else None,
                author=str(author) if author else None,
                summary=str(summary) if summary else None,
                content_markdown=content_markdown,
            )
        )
    if not items:
        raise FetchError(f"RSS feed empty for {feed_url}")
    return items


def _extract_content_html(entry: Any) -> str | None:
    content = entry.get("content")
    if isinstance(content, list) and content:
        candidate = content[0]
        if isinstance(candidate, dict) and candidate.get("value"):
            return str(candidate.get("value"))
    return entry.get("summary")
