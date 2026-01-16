from __future__ import annotations

from dataclasses import replace

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ...http import get_bytes
from ...models import BlogItem, FetchContext, Source
from ..rss import fetch_rss

PG_RSS_URL = "http://www.aaronsw.com/2002/feeds/pgessays.rss"
PG_RSS_LIMIT = 30
PG_HTML_FETCH_LIMIT = 5


def source() -> Source:
    return Source(
        id="paul-graham",
        name="Paul Graham",
        kind="blog",
        method="rss",
        fetch=fetch_paul_graham,
    )


def fetch_paul_graham(ctx: FetchContext) -> list[BlogItem]:
    items = fetch_rss(ctx, PG_RSS_URL, limit=PG_RSS_LIMIT)

    updated: list[BlogItem] = []
    for index, item in enumerate(items):
        should_try_html = index < PG_HTML_FETCH_LIMIT and not (
            item.content_markdown and item.content_markdown.strip()
        )
        if not should_try_html:
            updated.append(item)
            continue

        content = _fetch_paul_graham_article_markdown(ctx, item.url)
        if content and content.strip():
            updated.append(replace(item, content_markdown=content))
            continue

        updated.append(item)

    return updated


def _fetch_paul_graham_article_markdown(ctx: FetchContext, url: str) -> str | None:
    try:
        html = get_bytes(ctx.session, url)
    except Exception:
        return None
    return _extract_paul_graham_article_markdown(html)


def _extract_paul_graham_article_markdown(html: bytes) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()

    body = soup.find("font", attrs={"size": "2", "face": "verdana"})
    if body is None:
        return None

    content_html = body.decode_contents()
    if not content_html.strip():
        return None

    content_markdown = md(content_html)
    if not content_markdown.strip():
        return None
    return content_markdown.strip() + "\n"
