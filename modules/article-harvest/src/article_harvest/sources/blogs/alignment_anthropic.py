from __future__ import annotations

import re
from calendar import month_name
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from ...errors import FetchError
from ...http import get_text
from ...models import BlogItem, FetchContext, Source

ALIGNMENT_ANTHROPIC_URL = "https://alignment.anthropic.com/"
ALIGNMENT_ANTHROPIC_LIMIT = 30

_MONTH_LOOKUP = {name.lower(): idx for idx, name in enumerate(month_name) if name}


@dataclass(frozen=True)
class _Entry:
    url: str
    title: str
    published_at: str | None


def source() -> Source:
    return Source(
        id="alignment-anthropic",
        name="Alignment Science Blog (Anthropic)",
        kind="blog",
        method="html",
        fetch=fetch_alignment_anthropic,
    )


def fetch_alignment_anthropic(ctx: FetchContext) -> list[BlogItem]:
    html = get_text(ctx.session, ALIGNMENT_ANTHROPIC_URL)
    entries = _extract_entries(html)
    if not entries:
        raise FetchError("Alignment Anthropic listing empty")

    items = [
        BlogItem(
            title=entry.title,
            url=entry.url,
            published_at=entry.published_at,
        )
        for entry in entries[:ALIGNMENT_ANTHROPIC_LIMIT]
    ]
    if not items:
        raise FetchError("Alignment Anthropic returned no items")
    return items


def _extract_entries(html: str) -> list[_Entry]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("main") or soup.find("body") or soup
    entries: list[_Entry] = []
    seen: set[str] = set()
    current_published: str | None = None

    for element in container.descendants:
        if not isinstance(element, Tag):
            continue
        if _is_date_header(element):
            current_published = _parse_month_date(element.get_text(" ", strip=True))
            continue
        if element.name != "a":
            continue
        classes = element.get("class") or []
        if "note" not in classes and "paper" not in classes:
            continue
        href = (element.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(ALIGNMENT_ANTHROPIC_URL, href)
        if absolute in seen:
            continue
        title_tag = element.find(["h1", "h2", "h3"])
        title = _normalize_text(
            title_tag.get_text(" ", strip=True) if title_tag else element.get_text(" ", strip=True)
        )
        if not title:
            continue
        seen.add(absolute)
        entries.append(
            _Entry(
                url=absolute,
                title=title,
                published_at=current_published,
            )
        )

    return entries


def _is_date_header(element: Tag) -> bool:
    classes = element.get("class") or []
    return element.name == "div" and "date" in classes


def _parse_month_date(text: str) -> str | None:
    match = re.match(r"([A-Za-z]+)\s+(\d{4})", text.strip())
    if not match:
        return None
    month = _MONTH_LOOKUP.get(match.group(1).lower())
    if not month:
        return None
    year = int(match.group(2))
    return f"{year:04d}-{month:02d}-01"


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()
