from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag
from markdownify import markdownify as md

from ...errors import FetchError
from ...http import get_text
from ...models import BlogItem, FetchContext, Source

OPENAI_DEV_BLOG_URL = "https://developers.openai.com/blog"
OPENAI_DEV_BLOG_LIMIT = 20


@dataclass(frozen=True)
class _Entry:
    url: str


def source() -> Source:
    return Source(
        id="openai-dev-blog",
        name="OpenAI Developers Blog",
        kind="blog",
        method="html",
        fetch=fetch_openai_dev_blog,
    )


def fetch_openai_dev_blog(ctx: FetchContext) -> list[BlogItem]:
    html = get_text(ctx.session, OPENAI_DEV_BLOG_URL)
    entries = _extract_entries(html)
    if not entries:
        raise FetchError("OpenAI Developers Blog list empty")

    items: list[BlogItem] = []
    for entry in entries[:OPENAI_DEV_BLOG_LIMIT]:
        item = _fetch_article(ctx, entry.url)
        if item:
            items.append(item)

    if not items:
        raise FetchError("OpenAI Developers Blog returned no items")
    return items


def _extract_entries(html: str) -> list[_Entry]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("main") or soup
    links: list[str] = []
    for anchor in container.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href.startswith("/blog/") or href.startswith("/blog/topic"):
            continue
        links.append(urljoin(OPENAI_DEV_BLOG_URL, href))
    return [_Entry(url=url) for url in _unique(links)]


def _fetch_article(ctx: FetchContext, url: str) -> BlogItem | None:
    html = get_text(ctx.session, url)
    return _parse_article(html, url)


def _parse_article(html: str, url: str) -> BlogItem | None:
    soup = BeautifulSoup(html, "lxml")
    article = soup.find("article") or soup.find("main")
    if article is None:
        return None

    title = _extract_title(article, soup)
    _strip_unwanted(article)

    content_html = article.decode_contents().strip()
    if not content_html:
        return None

    content_markdown = md(content_html).strip()
    if not content_markdown:
        return None

    return BlogItem(
        title=title or url,
        url=url,
        content_markdown=content_markdown,
    )


def _extract_title(article: Tag, soup: BeautifulSoup) -> str | None:
    title_tag = article.find("h1") or soup.find("h1")
    if not title_tag:
        return None
    title = _normalize_text(title_tag.get_text(" ", strip=True))
    if title_tag in article.descendants:
        title_tag.decompose()
    return title or None


def _strip_unwanted(container: Tag) -> None:
    for tag in container.find_all(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
