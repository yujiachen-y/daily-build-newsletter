from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...errors import FetchError
from ...http import get_text
from ...models import AggregationItem, FetchContext, Source

GITHUB_TRENDING_URL = "https://github.com/trending"
GITHUB_LIMIT = 25


def source() -> Source:
    return Source(
        id="github-trending",
        name="GitHub Trending",
        kind="aggregation",
        method="scrape",
        fetch=fetch_github_trending,
    )


def _parse_stars_today(text: str) -> int | None:
    """Extract the 'N stars today' count from an article row."""
    m = re.search(r"([\d,]+)\s+stars\s+today", text)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


def _parse_total_stars(text: str) -> int | None:
    """Parse a compact star count like '1,234' or '31,269'."""
    cleaned = text.strip().replace(",", "")
    try:
        return int(cleaned)
    except ValueError:
        return None


def fetch_github_trending(ctx: FetchContext) -> list[AggregationItem]:
    html = get_text(ctx.session, GITHUB_TRENDING_URL, timeout=20)
    soup = BeautifulSoup(html, "html.parser")

    rows = soup.select("article.Box-row")
    if not rows:
        raise FetchError("GitHub Trending: no article rows found")

    entries: list[AggregationItem] = []
    for rank, row in enumerate(rows[:GITHUB_LIMIT], start=1):
        # Repo name: h2 > a with href like /owner/repo
        h2 = row.select_one("h2 a")
        if not h2:
            continue
        href = h2.get("href", "").strip()
        if not href:
            continue
        full_name = "/".join(s.strip() for s in href.strip("/").split("/")[:2])
        url = f"https://github.com/{full_name}"

        # Description
        desc_el = row.select_one("p")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Language
        lang_el = row.select_one("[itemprop='programmingLanguage']")
        language = lang_el.get_text(strip=True) if lang_el else None

        # Total stars: first <a> in the inline div that links to /owner/repo/stargazers
        total_stars = None
        star_link = row.select_one(f"a[href='/{full_name}/stargazers']")
        if star_link:
            total_stars = _parse_total_stars(star_link.get_text())

        # Stars today
        stars_today = _parse_stars_today(row.get_text())

        # Author (repo owner)
        owner = full_name.split("/")[0] if "/" in full_name else None

        entries.append(
            AggregationItem(
                title=full_name,
                url=url,
                published_at=None,
                author=owner,
                score=total_stars,
                comments_count=None,
                rank=rank,
                discussion_url=None,
                extra={
                    "language": language,
                    "description": description,
                    "stars_today": stars_today,
                },
            )
        )

    if not entries:
        raise FetchError("GitHub Trending: parsed zero entries")
    return entries
