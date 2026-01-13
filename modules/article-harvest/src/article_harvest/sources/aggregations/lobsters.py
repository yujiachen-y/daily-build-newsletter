from __future__ import annotations

from ...errors import FetchError
from ...http import get_json
from ...models import AggregationItem, FetchContext, Source

LOBSTERS_URL = "https://lobste.rs/hottest.json"
LOBSTERS_LIMIT = 25


def source() -> Source:
    return Source(
        id="lobsters",
        name="Lobsters",
        kind="aggregation",
        method="api",
        fetch=fetch_lobsters,
    )


def fetch_lobsters(ctx: FetchContext) -> list[AggregationItem]:
    payload = get_json(ctx.session, LOBSTERS_URL)
    if not isinstance(payload, list):
        raise FetchError("Lobsters payload invalid")
    items: list[AggregationItem] = []
    for rank, entry in enumerate(payload[:LOBSTERS_LIMIT], start=1):
        title = entry.get("title")
        url = entry.get("url") or entry.get("comments_url")
        if not title or not url:
            continue
        submitter = entry.get("submitter_user")
        author = submitter.get("username") if isinstance(submitter, dict) else submitter
        items.append(
            AggregationItem(
                title=title,
                url=url,
                published_at=entry.get("created_at"),
                author=author if isinstance(author, str) else None,
                score=entry.get("score"),
                comments_count=entry.get("comments_count"),
                rank=rank,
                discussion_url=entry.get("comments_url"),
                extra={},
            )
        )
    if not items:
        raise FetchError("Lobsters list empty")
    return items
