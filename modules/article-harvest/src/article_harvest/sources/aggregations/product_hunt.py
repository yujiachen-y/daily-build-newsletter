from __future__ import annotations

import feedparser

from ...errors import FetchError
from ...http import get_bytes
from ...models import AggregationItem, FetchContext, Source

PRODUCT_HUNT_FEED = "https://www.producthunt.com/feed"
PRODUCT_HUNT_LIMIT = 20


def source() -> Source:
    return Source(
        id="product-hunt",
        name="Product Hunt",
        kind="aggregation",
        method="rss",
        fetch=fetch_product_hunt,
    )


def fetch_product_hunt(ctx: FetchContext) -> list[AggregationItem]:
    feed = feedparser.parse(get_bytes(ctx.session, PRODUCT_HUNT_FEED))
    if feed.bozo:
        raise FetchError("Product Hunt RSS parse error")
    items: list[AggregationItem] = []
    for rank, entry in enumerate(feed.entries[:PRODUCT_HUNT_LIMIT], start=1):
        title = entry.get("title")
        link = entry.get("link")
        if not title or not link:
            continue
        items.append(
            AggregationItem(
                title=title,
                url=link,
                published_at=entry.get("published"),
                author=None,
                score=None,
                comments_count=None,
                rank=rank,
                discussion_url=None,
                extra={},
            )
        )
    if not items:
        raise FetchError("Product Hunt list empty")
    return items
