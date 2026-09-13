from __future__ import annotations

import re

from bs4 import BeautifulSoup
from bs4.element import Tag
from dateutil import parser as date_parser
from markdownify import markdownify as md

from ...errors import FetchError
from ...http import get_text
from ...models import BlogItem, FetchContext, Source

# Anthropic 官方 API changelog：细粒度的能力变更（新 endpoint、新 beta header、SDK 方法），
# 比 claude.com/blog 早也比它细——博客只发大新闻，这里才有 "client.beta.files" 这种。
# OpenAI 侧没有对应物：platform.openai.com/docs/changelog 是客户端渲染的，抓不到内容，
# 所以那边走 openai-node 的 releases（见 github_releases.py）。
ANTHROPIC_API_RELEASE_NOTES_URL = "https://docs.claude.com/en/release-notes/api"

# ponytail: 页面一次给 209 个日期分节（倒序）。日报只关心最近的，取 10 个约覆盖两个月。
ANTHROPIC_RELEASE_NOTES_LIMIT = 10

_DATE_RE = re.compile(r"([A-Z][a-z]+\s+\d{1,2},\s+20\d\d)")


def source() -> Source:
    return Source(
        id="anthropic-api-release-notes",
        name="Anthropic API Release Notes",
        kind="blog",
        method="html",
        fetch=fetch_anthropic_api_release_notes,
    )


def fetch_anthropic_api_release_notes(ctx: FetchContext) -> list[BlogItem]:
    soup = BeautifulSoup(get_text(ctx.session, ANTHROPIC_API_RELEASE_NOTES_URL), "lxml")

    items: list[BlogItem] = []
    for heading in soup.find_all("h3", id=True):
        published_at = _heading_date(heading)
        if not published_at:
            continue
        item = _build_item(heading, published_at)
        if item:
            items.append(item)
        if len(items) >= ANTHROPIC_RELEASE_NOTES_LIMIT:
            break

    if not items:
        raise FetchError("Anthropic API release notes: no dated sections found")
    return items


def _build_item(heading: Tag, published_at: str) -> BlogItem | None:
    body = _section_markdown(heading)
    if not body:
        return None
    # find_all("h3", id=True) 已保证 id 存在
    return BlogItem(
        title=f"Anthropic API Release Notes — {published_at}",
        url=f"{ANTHROPIC_API_RELEASE_NOTES_URL}#{heading['id']}",
        published_at=published_at,
        content_markdown=body,
    )


def _section_markdown(heading: Tag) -> str | None:
    """取这个日期标题到下一个日期标题之间的内容。"""
    parts: list[str] = []
    for sibling in heading.find_next_siblings():
        if isinstance(sibling, Tag) and sibling.name == "h3":
            break
        parts.append(str(sibling))
    if not parts:
        return None
    return md("".join(parts)).strip() or None


def _heading_date(heading: Tag) -> str | None:
    """标题形如 'September 3, 2026'，尾随一个锚点按钮的 span。"""
    match = _DATE_RE.search(heading.get_text(" ", strip=True))
    if not match:
        return None
    try:
        return date_parser.parse(match.group(1)).date().isoformat()
    except (ValueError, OverflowError):
        return None
