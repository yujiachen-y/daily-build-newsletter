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

PI_BLOG_URL = "https://www.physicalintelligence.company/blog"
PI_LIMIT = 30

_MONTH_LOOKUP = {name.lower(): idx for idx, name in enumerate(month_name) if name}
_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(\d{4})\b"
)
# Next.js routing artifacts that show up in href="/blog/..." but aren't real posts.
_SLUG_BLOCKLIST = {"page", "category", "tag"}


@dataclass(frozen=True)
class _Entry:
    url: str
    title: str
    published_at: str | None


def source() -> Source:
    return Source(
        id="physical-intelligence",
        name="Physical Intelligence (π) Blog",
        kind="blog",
        method="html",
        fetch=fetch_physical_intelligence,
    )


def fetch_physical_intelligence(ctx: FetchContext) -> list[BlogItem]:
    html = get_text(ctx.session, PI_BLOG_URL)
    entries = _extract_entries(html)
    if not entries:
        raise FetchError("Physical Intelligence listing empty")

    items = [
        BlogItem(title=entry.title, url=entry.url, published_at=entry.published_at)
        for entry in entries[:PI_LIMIT]
    ]
    if not items:
        raise FetchError("Physical Intelligence returned no items")
    return items


def _extract_entries(html: str) -> list[_Entry]:
    soup = BeautifulSoup(html, "lxml")
    entries: list[_Entry] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href.startswith("/blog/"):
            continue
        slug = href[len("/blog/") :].split("/", 1)[0].split("?", 1)[0]
        if not slug or slug.split("-", 1)[0] in _SLUG_BLOCKLIST:
            continue
        absolute = urljoin(PI_BLOG_URL, href)
        if absolute in seen:
            continue

        title = _extract_title(anchor)
        if not title:
            continue
        published = _extract_date(anchor)

        seen.add(absolute)
        entries.append(_Entry(url=absolute, title=title, published_at=published))

    return entries


def _extract_title(anchor: Tag) -> str | None:
    # The card markup nests the clean title inside a div carrying a `title="..."` attribute.
    titled = anchor.find(lambda tag: isinstance(tag, Tag) and tag.has_attr("title"))
    if isinstance(titled, Tag):
        candidate = _normalize_text(str(titled.get("title", "")))
        if candidate:
            return candidate
    # Fallback: strip the trailing date+description from the anchor text.
    text = _normalize_text(anchor.get_text(" ", strip=True))
    if not text:
        return None
    match = _DATE_RE.search(text)
    return _normalize_text(text[: match.start()]) if match else text


def _extract_date(anchor: Tag) -> str | None:
    match = _DATE_RE.search(anchor.get_text(" ", strip=True))
    if not match:
        return None
    month = _MONTH_LOOKUP.get(match.group(1).lower())
    if not month:
        return None
    day = int(match.group(2))
    year = int(match.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()
