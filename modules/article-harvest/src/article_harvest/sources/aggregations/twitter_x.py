from __future__ import annotations

import os

from ...errors import FetchError
from ...models import AggregationItem, FetchContext, Source

APIFY_API_BASE = "https://api.apify.com/v2"
ACTOR_ID = "sovereigntaylor~twitter-scraper"
MAX_ITEMS_PER_RUN = 50
RESULT_LIMIT = 20

DEFAULT_HANDLES = [
    "karpathy",
    "AndrewYNg",
    "ylecun",
    "jimfan_",
    "swaborhm",
]


def source() -> Source:
    return Source(
        id="twitter-x",
        name="Twitter/X (Apify)",
        kind="aggregation",
        method="api",
        fetch=fetch_twitter_x,
        enabled=bool(os.environ.get("APIFY_API_TOKEN")),
    )


def fetch_twitter_x(ctx: FetchContext) -> list[AggregationItem]:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise FetchError("APIFY_API_TOKEN environment variable not set")

    handles = _get_handles()
    tweets = _run_actor(ctx, token, handles)

    tweets.sort(key=_engagement, reverse=True)

    items: list[AggregationItem] = []
    for rank, tweet in enumerate(tweets[:RESULT_LIMIT], start=1):
        item = _parse_tweet(tweet, rank)
        if item:
            items.append(item)

    if not items:
        raise FetchError("No parseable tweets from Apify")

    return items


def _get_handles() -> list[str]:
    env_handles = os.environ.get("TWITTER_HANDLES")
    if env_handles:
        return [h.strip() for h in env_handles.split(",") if h.strip()]
    return list(DEFAULT_HANDLES)


def _run_actor(ctx: FetchContext, token: str, handles: list[str]) -> list[dict]:
    url = f"{APIFY_API_BASE}/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    run_input = {
        "handles": handles,
        "maxItems": MAX_ITEMS_PER_RUN,
    }

    resp = ctx.session.post(url, params={"token": token}, json=run_input, timeout=180)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        raise FetchError("Apify tweet scraper returned unexpected format")

    # Filter out non-tweet items and retweets
    tweets = [t for t in data if t.get("type") == "tweet" and not t.get("isRetweet")]
    if not tweets:
        raise FetchError("Apify tweet scraper returned no tweets")

    return tweets


def _engagement(tweet: dict) -> int:
    likes = tweet.get("likes") or 0
    retweets = tweet.get("retweets") or 0
    return int(likes) + int(retweets)


def _parse_tweet(tweet: dict, rank: int) -> AggregationItem | None:
    text = tweet.get("text") or ""
    if not text:
        return None

    first_line = text.split("\n")[0]
    title = first_line if len(first_line) <= 100 else first_line[:100] + "\u2026"

    author = tweet.get("username")
    url = tweet.get("tweetUrl") or ""
    if not url and author:
        tweet_id = tweet.get("tweetId")
        if tweet_id:
            url = f"https://x.com/{author}/status/{tweet_id}"

    likes = int(tweet.get("likes") or 0)
    retweets = int(tweet.get("retweets") or 0)
    replies = int(tweet.get("replies") or 0)

    return AggregationItem(
        title=title,
        url=url,
        published_at=tweet.get("date"),
        author=author,
        score=likes,
        comments_count=replies,
        rank=rank,
        discussion_url=url,
        extra={
            "retweets": retweets,
            "likes": likes,
            "quotes": int(tweet.get("quotes") or 0),
            "full_text": text,
            "language": tweet.get("language"),
        },
    )
