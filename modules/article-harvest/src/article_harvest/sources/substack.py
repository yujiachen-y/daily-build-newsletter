"""Substack RSS source that refills paid-post bodies with a subscriber session cookie.

The public feed truncates subscriber-only posts to the free preview. Substack's reader
API at substack.com returns the full body for any publication the session subscribes to,
so one ``substack.sid`` cookie (env ``SUBSTACK_SID``) covers every paid Substack.
Publication-hosted APIs do not accept that cookie, so the slug is resolved to a post id
there first, then the body is fetched from substack.com.
"""

from __future__ import annotations

import os
from dataclasses import replace
from urllib.parse import urlsplit

import requests
from markdownify import markdownify as md

from ..http import get_json
from ..models import BlogItem, FetchContext, Source
from .rss import fetch_rss

TRUNCATION_MARKER = "[Read more]("
COOKIE_ENV = "SUBSTACK_SID"
READER_API = "https://substack.com/api/v1/posts/by-id/{post_id}"


def make_substack_source(
    source_id: str,
    name: str,
    feed_url: str,
    *,
    max_age_days: int | None = 90,
) -> Source:
    """RSS source that unlocks paid posts when SUBSTACK_SID holds a subscriber cookie."""
    return Source(
        id=source_id,
        name=name,
        kind="blog",
        method="rss",
        fetch=lambda ctx: _fetch(ctx, feed_url, max_age_days),
    )


def _fetch(ctx: FetchContext, feed_url: str, max_age_days: int | None) -> list[BlogItem]:
    items = fetch_rss(ctx, feed_url, max_age_days=max_age_days)
    sid = os.environ.get(COOKIE_ENV, "").strip()
    if not sid:
        return items
    return [_unlock(ctx, item, sid) for item in items]


def _unlock(ctx: FetchContext, item: BlogItem, sid: str) -> BlogItem:
    # ponytail: an expired cookie silently leaves the free preview in place, same as today.
    if not item.content_markdown or TRUNCATION_MARKER not in item.content_markdown:
        return item
    body_html = _fetch_body_html(ctx, item.url, sid)
    if not body_html:
        return item
    return replace(item, content_markdown=md(body_html))


def _fetch_body_html(ctx: FetchContext, url: str, sid: str) -> str | None:
    post_id = _post_id(ctx, url)
    if not post_id:
        return None
    payload = _get_json(ctx, READER_API.format(post_id=post_id), cookies={"substack.sid": sid})
    post = payload.get("post") if isinstance(payload, dict) else None
    if not isinstance(post, dict):
        return None
    body_html = post.get("body_html")
    return str(body_html) if body_html else None


def _post_id(ctx: FetchContext, url: str) -> str | None:
    parts = urlsplit(url)
    slug = parts.path.rsplit("/", 1)[-1]
    if "/p/" not in parts.path or not slug:
        return None
    api_url = f"{parts.scheme}://{parts.netloc}/api/v1/posts/{slug}"
    payload = _get_json(ctx, api_url)
    post_id = payload.get("id") if isinstance(payload, dict) else None
    return str(post_id) if post_id else None


def _get_json(ctx: FetchContext, url: str, cookies: dict[str, str] | None = None) -> object:
    try:
        return get_json(ctx.session, url, cookies=cookies)
    except (requests.RequestException, ValueError):
        return None
