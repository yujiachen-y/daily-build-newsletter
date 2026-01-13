from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from ...errors import FetchError
from ...http import get_json
from ...models import AggregationComment, AggregationItem, FetchContext, Source

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
HN_DISCUSSION = "https://news.ycombinator.com/item?id={item_id}"
HN_LIMIT = 10
HN_SEED_LIMIT = 20
HN_COMMENT_LIMIT = 20


def source() -> Source:
    return Source(
        id="hn",
        name="Hacker News",
        kind="aggregation",
        method="api",
        fetch=fetch_hn,
    )


def fetch_hn(ctx: FetchContext) -> list[AggregationItem]:
    top_ids = get_json(ctx.session, f"{HN_API_BASE}/topstories.json")
    if not isinstance(top_ids, list):
        raise FetchError("HN topstories payload invalid")

    candidates: list[tuple[AggregationItem, list[int]]] = []
    for story_id in top_ids[:HN_SEED_LIMIT]:
        candidate = _fetch_story(ctx, story_id)
        if not candidate:
            continue
        candidates.append(candidate)

    if not candidates:
        raise FetchError("HN list empty")

    sorted_items = sorted(
        candidates,
        key=lambda entry: entry[0].comments_count or 0,
        reverse=True,
    )
    ranked: list[AggregationItem] = []
    for rank, (item, kids) in enumerate(sorted_items[:HN_LIMIT], start=1):
        comments = _fetch_comments(ctx, kids)
        ranked.append(
            AggregationItem(
                title=item.title,
                url=item.url,
                published_at=item.published_at,
                author=item.author,
                score=item.score,
                comments_count=item.comments_count,
                rank=rank,
                discussion_url=item.discussion_url,
                comments=comments,
                extra=item.extra,
            )
        )
    return ranked


def _fetch_story(ctx: FetchContext, story_id: int) -> tuple[AggregationItem, list[int]] | None:
    payload = get_json(ctx.session, f"{HN_API_BASE}/item/{story_id}.json")
    if not isinstance(payload, dict):
        return None
    if payload.get("type") != "story":
        return None
    title = payload.get("title")
    if not title:
        return None
    url = payload.get("url") or HN_DISCUSSION.format(item_id=story_id)
    kids = payload.get("kids") or []
    return (
        AggregationItem(
            title=title,
            url=url,
            published_at=_iso_from_unix(payload.get("time")),
            author=payload.get("by"),
            score=payload.get("score"),
            comments_count=payload.get("descendants") or 0,
            rank=None,
            discussion_url=HN_DISCUSSION.format(item_id=story_id),
            comments=[],
            extra={},
        ),
        kids,
    )


def _fetch_comments(ctx: FetchContext, root_ids: list[int]) -> list[AggregationComment]:
    comments: list[AggregationComment] = []
    queue: deque[int] = deque(root_ids)
    while queue and len(comments) < HN_COMMENT_LIMIT:
        comment_id = queue.popleft()
        payload = get_json(ctx.session, f"{HN_API_BASE}/item/{comment_id}.json")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "comment":
            continue
        text_html = payload.get("text")
        text = _strip_html(text_html) if text_html else "[deleted]"
        comments.append(
            AggregationComment(
                author=payload.get("by"),
                published_at=_iso_from_unix(payload.get("time")),
                text=text,
            )
        )
        for kid_id in payload.get("kids") or []:
            if len(comments) + len(queue) >= HN_COMMENT_LIMIT:
                break
            queue.append(kid_id)
    return comments


def _strip_html(value: str) -> str:
    return BeautifulSoup(value, "lxml").get_text(" ", strip=True)


def _iso_from_unix(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    try:
        dt = datetime.fromtimestamp(int(seconds), tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None
