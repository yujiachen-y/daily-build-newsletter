from __future__ import annotations

from datetime import date, timedelta

from ...errors import FetchError
from ...models import AggregationItem, FetchContext, Source

GITHUB_SEARCH = "https://api.github.com/search/repositories"
GITHUB_LIMIT = 20


def source() -> Source:
    return Source(
        id="github-trending",
        name="GitHub Trending",
        kind="aggregation",
        method="api",
        fetch=fetch_github_trending,
    )


def fetch_github_trending(ctx: FetchContext) -> list[AggregationItem]:
    since = (date.today() - timedelta(days=7)).isoformat()
    query = f"created:>{since}"
    url = (
        f"{GITHUB_SEARCH}?q={query}&sort=stars&order=desc&per_page={GITHUB_LIMIT}"
    )
    response = ctx.session.get(
        url,
        timeout=20,
        headers={"Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("items") if isinstance(payload, dict) else None
    if not items:
        raise FetchError("GitHub search empty")

    entries: list[AggregationItem] = []
    for rank, item in enumerate(items[:GITHUB_LIMIT], start=1):
        if not isinstance(item, dict):
            continue
        title = item.get("full_name")
        url = item.get("html_url")
        if not title or not url:
            continue
        entries.append(
            AggregationItem(
                title=title,
                url=url,
                published_at=item.get("created_at"),
                author=(item.get("owner") or {}).get("login"),
                score=item.get("stargazers_count"),
                comments_count=None,
                rank=rank,
                discussion_url=None,
                extra={
                    "language": item.get("language"),
                    "description": item.get("description"),
                },
            )
        )
    if not entries:
        raise FetchError("GitHub search entries empty")
    return entries
