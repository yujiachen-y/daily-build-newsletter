from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag
from dateutil import parser as date_parser
from markdownify import markdownify as md

from ...errors import FetchError
from ...http import get_text
from ...models import BlogItem, FetchContext, Source

CLAUDE_BLOG_URL = "https://claude.com/blog"
CLAUDE_BLOG_LIMIT = 20


@dataclass(frozen=True)
class _Entry:
    url: str
    title: str | None = None


def source() -> Source:
    return Source(
        id="claude-blog",
        name="Claude Blog",
        kind="blog",
        method="html",
        fetch=fetch_claude_blog,
    )


def fetch_claude_blog(ctx: FetchContext) -> list[BlogItem]:
    html = get_text(ctx.session, CLAUDE_BLOG_URL)
    entries = _extract_entries(html)
    if not entries:
        raise FetchError("Claude Blog list empty")

    items: list[BlogItem] = []
    for entry in entries[:CLAUDE_BLOG_LIMIT]:
        item = _fetch_article(ctx, entry)
        if item:
            items.append(item)

    if not items:
        raise FetchError("Claude Blog returned no items")
    return items


def _extract_entries(html: str) -> list[_Entry]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("main") or soup
    entries: list[_Entry] = []
    seen: set[str] = set()

    for article in container.find_all("article"):
        anchor = _extract_article_link(article)
        if not anchor or anchor in seen:
            continue
        seen.add(anchor)
        title = _extract_card_title(article, anchor)
        entries.append(_Entry(url=anchor, title=title))

    return entries


def _extract_article_link(article: Tag) -> str | None:
    anchor = article.find("a", href=True)
    if not anchor:
        return None
    href = anchor["href"].strip()
    if not href.startswith("/blog/") or href.startswith("/blog/category/"):
        return None
    return urljoin(CLAUDE_BLOG_URL, href)


def _extract_card_title(article: Tag, anchor_url: str) -> str | None:
    title_tag = article.find(["h1", "h2", "h3"])
    if title_tag:
        title = _normalize_text(title_tag.get_text(" ", strip=True))
        if title:
            return title
    return _normalize_text(article.get_text(" ", strip=True).replace(anchor_url, "")) or None


def _fetch_article(ctx: FetchContext, entry: _Entry) -> BlogItem | None:
    html = get_text(ctx.session, entry.url)
    return _parse_article(html, entry)


def _parse_article(html: str, entry: _Entry) -> BlogItem | None:
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("main") or soup.find("article")
    if container is None:
        return None

    title = _extract_title(container, soup) or entry.title or entry.url
    published_at = _extract_published_at(soup)
    _strip_unwanted(container)

    content_html = container.decode_contents().strip()
    if not content_html:
        return None

    content_markdown = md(content_html).strip()
    if not content_markdown:
        return None

    return BlogItem(
        title=title,
        url=entry.url,
        published_at=published_at,
        content_markdown=content_markdown,
    )


def _extract_title(container: Tag, soup: BeautifulSoup) -> str | None:
    title_tag = container.find("h1") or soup.find("h1")
    if not title_tag:
        return None
    title = _normalize_text(title_tag.get_text(" ", strip=True))
    if title_tag in container.descendants:
        title_tag.decompose()
    return title or None


def _extract_published_at(soup: BeautifulSoup) -> str | None:
    for payload in _iter_jsonld(soup):
        if not isinstance(payload, dict):
            continue
        candidate = payload.get("datePublished") or payload.get("dateCreated")
        if not candidate:
            continue
        normalized = _normalize_date(str(candidate))
        if normalized:
            return normalized
    return None


def _iter_jsonld(soup: BeautifulSoup) -> Iterable[dict]:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in _flatten_jsonld(payload):
            if isinstance(item, dict):
                yield item


def _flatten_jsonld(payload: object) -> list[object]:
    if isinstance(payload, list):
        items: list[object] = []
        for entry in payload:
            items.extend(_flatten_jsonld(entry))
        return items
    if isinstance(payload, dict):
        graph = payload.get("@graph")
        if isinstance(graph, list):
            return [payload, *graph]
        return [payload]
    return []


def _normalize_date(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        parsed = date_parser.parse(candidate)
    except (ValueError, TypeError):
        return candidate
    return parsed.date().isoformat()


def _strip_unwanted(container: Tag) -> None:
    unwanted = ["script", "style", "noscript", "header", "footer", "nav", "aside"]
    for tag in container.find_all(unwanted):
        tag.decompose()


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()
