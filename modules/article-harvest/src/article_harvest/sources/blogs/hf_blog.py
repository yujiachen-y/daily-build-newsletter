from __future__ import annotations

from dataclasses import replace
from html import escape

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from markdownify import markdownify as md

from ...http import get_bytes
from ...models import BlogItem, FetchContext, Source
from ...storage import Storage
from ..rss import fetch_rss

HF_BLOG_RSS_URL = "https://huggingface.co/blog/feed.xml"


def source() -> Source:
    return Source(
        id="hf-blog",
        name="Hugging Face Blog",
        kind="blog",
        method="rss",
        fetch=fetch_hf_blog,
    )


def fetch_hf_blog(ctx: FetchContext) -> list[BlogItem]:
    items = fetch_rss(ctx, HF_BLOG_RSS_URL)

    storage = Storage()
    existing = storage.existing_by_url("hf-blog")

    updated: list[BlogItem] = []
    for item in items:
        if not _should_try_html(existing.get(item.url), storage):
            updated.append(item)
            continue

        content = _fetch_hf_blog_article_markdown(ctx, item.url)
        if content and content.strip():
            updated.append(replace(item, content_markdown=content))
            continue

        updated.append(item)

    return updated


def _should_try_html(existing: dict[str, str | int | None] | None, storage: Storage) -> bool:
    if existing is None:
        return True
    content_path = existing.get("content_path")
    if not content_path:
        return True
    path = storage.data_root / str(content_path)
    if not path.exists():
        return True
    if path.stat().st_size == 0:
        return True
    preview = path.read_text(encoding="utf-8")[:800]
    if "|  |" in preview:
        return True
    if preview.lstrip().startswith("[Signup]"):
        return True
    if any(line.strip() == "|" for line in preview.splitlines()):
        return True
    return False


def _fetch_hf_blog_article_markdown(ctx: FetchContext, url: str) -> str | None:
    try:
        html = get_bytes(ctx.session, url)
    except Exception:
        return None
    return _extract_hf_blog_article_markdown(html)


def _extract_hf_blog_article_markdown(html: bytes) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("div.blog-content")
    if content is None:
        return None

    nodes = list(content.contents)
    start_index = _find_first_body_node_index(nodes)
    if start_index is None:
        return None

    parts: list[str] = []
    for node in nodes[start_index:]:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if not text:
                continue
            parts.append(f"<p>{escape(text)}</p>")
            continue

        if not isinstance(node, Tag):
            continue

        classes = set(node.get("class") or [])
        if "SVELTE_HYDRATER" in classes or "not-prose" in classes:
            continue

        if not node.get_text(strip=True) and not node.find(["img", "pre", "code"]):
            continue

        parts.append(node.decode())

    content_html = "\n".join(parts).strip()
    if not content_html:
        return None

    content_markdown = md(content_html).strip()
    if not content_markdown:
        return None
    return content_markdown + "\n"


def _find_first_body_node_index(nodes: list[object]) -> int | None:
    for idx, node in enumerate(nodes):
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if len(text) >= 80:
                return idx
            continue

        if not isinstance(node, Tag):
            continue

        classes = set(node.get("class") or [])
        if "SVELTE_HYDRATER" in classes or "not-prose" in classes:
            continue

        text = node.get_text(" ", strip=True)
        if len(text) >= 80:
            return idx
    return None
