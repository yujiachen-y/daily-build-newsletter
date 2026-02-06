from __future__ import annotations

from ...models import BlogItem, FetchContext, Source
from ..rss import fetch_rss

VERCEL_BLOG_FEED = "https://vercel.com/atom"
VERCEL_BLOG_LIMIT = 40


def source() -> Source:
    return Source(
        id="vercel-blog",
        name="Vercel Blog",
        kind="blog",
        method="rss",
        fetch=fetch_vercel_blog,
    )


def fetch_vercel_blog(ctx: FetchContext) -> list[BlogItem]:
    return fetch_rss(ctx, VERCEL_BLOG_FEED, limit=VERCEL_BLOG_LIMIT)
