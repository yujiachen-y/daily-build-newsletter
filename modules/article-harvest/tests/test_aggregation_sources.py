from __future__ import annotations

from datetime import datetime

from article_harvest.models import FetchContext
from article_harvest.sources.aggregations.github_trending import fetch_github_trending
from article_harvest.sources.aggregations.hf_papers import fetch_hf_papers
from article_harvest.sources.aggregations.hn import _iso_from_unix, _strip_html, fetch_hn
from article_harvest.sources.aggregations.lobsters import fetch_lobsters
from article_harvest.sources.aggregations.product_hunt import fetch_product_hunt
from article_harvest.sources.aggregations.releasebot import (
    _decode_devalue_data,
    fetch_releasebot,
)

# -- helpers --


class _DummyResponse:
    def __init__(self, *, text="", content=b"", json_data=None):
        self.text = text
        self.content = content
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class _DummySession:
    """Minimal session stub with optional URL-keyed routing."""

    def __init__(self, responses=None, default=None):
        self._responses = responses or {}
        self._default = default
        self.headers = {}

    def get(self, url, **kwargs):
        if url in self._responses:
            return self._responses[url]
        if self._default is not None:
            return self._default
        raise ValueError(f"Unmocked URL: {url}")


def _ctx(session):
    return FetchContext(session=session, run_id="test", now=datetime.utcnow())


# -- HF Papers --


def test_fetch_hf_papers():
    payload = [
        {
            "title": "Paper One",
            "publishedAt": "2026-01-01",
            "numComments": 5,
            "paper": {
                "id": "abc123",
                "title": "Paper One",
                "upvotes": 42,
                "authors": [{"name": "Alice"}],
            },
        },
        {
            "title": "Paper Two",
            "paper": {
                "id": "def456",
                "title": "Paper Two",
                "upvotes": 10,
                "authors": [],
            },
        },
    ]
    session = _DummySession(default=_DummyResponse(json_data=payload))
    items = fetch_hf_papers(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "Paper One"
    assert items[0].rank == 1
    assert items[0].author == "Alice"
    assert items[0].score == 42
    assert items[0].url == "https://huggingface.co/papers/abc123"
    assert items[1].rank == 2
    assert items[1].author is None


# -- GitHub Trending --


def test_fetch_github_trending():
    payload = {
        "items": [
            {
                "full_name": "user/repo1",
                "html_url": "https://github.com/user/repo1",
                "created_at": "2026-01-01",
                "owner": {"login": "user"},
                "stargazers_count": 100,
                "language": "Python",
                "description": "A cool repo",
            },
            {
                "full_name": "org/repo2",
                "html_url": "https://github.com/org/repo2",
                "created_at": "2026-01-02",
                "owner": {"login": "org"},
                "stargazers_count": 50,
                "language": "Rust",
                "description": "Another repo",
            },
        ]
    }
    session = _DummySession(default=_DummyResponse(json_data=payload))
    items = fetch_github_trending(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "user/repo1"
    assert items[0].author == "user"
    assert items[0].score == 100
    assert items[0].extra.get("language") == "Python"
    assert items[1].rank == 2


# -- Lobsters --


def test_fetch_lobsters():
    payload = [
        {
            "title": "Story 1",
            "url": "https://example.com/1",
            "created_at": "2026-01-01",
            "submitter_user": {"username": "alice"},
            "score": 10,
            "comments_count": 5,
            "comments_url": "https://lobste.rs/s/abc",
        },
        {
            "title": "Story 2",
            "url": "https://example.com/2",
            "created_at": "2026-01-02",
            "submitter_user": "bob",
            "score": 20,
            "comments_count": 3,
            "comments_url": "https://lobste.rs/s/def",
        },
    ]
    session = _DummySession(default=_DummyResponse(json_data=payload))
    items = fetch_lobsters(_ctx(session))
    assert len(items) == 2
    assert items[0].author == "alice"
    assert items[0].rank == 1
    assert items[0].discussion_url == "https://lobste.rs/s/abc"
    assert items[1].author == "bob"


# -- Hacker News --


_HN_BASE = "https://hacker-news.firebaseio.com/v0"


def test_fetch_hn():
    responses = {
        f"{_HN_BASE}/topstories.json": _DummyResponse(json_data=[1, 2]),
        f"{_HN_BASE}/item/1.json": _DummyResponse(
            json_data={
                "type": "story",
                "title": "Story One",
                "url": "https://example.com/1",
                "time": 1704067200,
                "by": "alice",
                "score": 100,
                "descendants": 5,
                "kids": [10],
            }
        ),
        f"{_HN_BASE}/item/2.json": _DummyResponse(
            json_data={
                "type": "story",
                "title": "Story Two",
                "url": "https://example.com/2",
                "time": 1704153600,
                "by": "bob",
                "score": 50,
                "descendants": 2,
                "kids": [],
            }
        ),
        f"{_HN_BASE}/item/10.json": _DummyResponse(
            json_data={
                "type": "comment",
                "text": "<p>Great post!</p>",
                "time": 1704070800,
                "by": "charlie",
                "kids": [],
            }
        ),
    }
    session = _DummySession(responses=responses)
    items = fetch_hn(_ctx(session))
    assert len(items) == 2
    # Sorted by comments_count desc: Story One (5) > Story Two (2)
    assert items[0].title == "Story One"
    assert items[0].rank == 1
    assert len(items[0].comments) == 1
    assert items[0].comments[0].author == "charlie"
    assert items[0].comments[0].text == "Great post!"
    assert items[1].title == "Story Two"
    assert items[1].rank == 2


def test_strip_html():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert _strip_html("plain text") == "plain text"


def test_iso_from_unix():
    assert _iso_from_unix(1704067200) == "2024-01-01T00:00:00+00:00"
    assert _iso_from_unix(None) is None
    assert _iso_from_unix("bad") is None


# -- Product Hunt --


def test_fetch_product_hunt():
    rss = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Product Hunt</title>
    <item>
      <title>Product 1</title>
      <link>https://producthunt.com/posts/product-1</link>
      <pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Product 2</title>
      <link>https://producthunt.com/posts/product-2</link>
      <pubDate>Tue, 02 Jan 2026 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""
    session = _DummySession(default=_DummyResponse(content=rss))
    items = fetch_product_hunt(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "Product 1"
    assert items[0].rank == 1
    assert items[1].title == "Product 2"
    assert items[1].rank == 2


# -- Releasebot --


def test_fetch_releasebot():
    releases = [
        {
            "product": {
                "display_name": "ToolX",
                "slug": "toolx",
                "vendor": {"display_name": "Acme", "slug": "acme"},
            },
            "release_details": {
                "release_name": "v2.0",
                "release_summary": "Major update",
            },
            "source": {"source_url": "https://example.com/release"},
            "release_date": "2026-01-01",
            "slug": "toolx-v2",
        },
    ]
    payload = {"nodes": [{"data": [{"releases": releases}]}]}
    session = _DummySession(default=_DummyResponse(json_data=payload))
    items = fetch_releasebot(_ctx(session))
    assert len(items) == 1
    assert items[0].title == "ToolX \u2014 v2.0"
    assert items[0].url == "https://example.com/release"
    assert items[0].author == "Acme"
    assert items[0].extra.get("summary") == "Major update"


def test_fetch_releasebot_fallback_url():
    """When source_url is missing, releasebot constructs URL from slugs."""
    releases = [
        {
            "product": {
                "display_name": "Widget",
                "slug": "widget",
                "vendor": {"display_name": "Corp", "slug": "corp"},
            },
            "release_details": {"release_number": "1.0"},
            "release_date": "2026-02-01",
        },
    ]
    payload = {"nodes": [{"data": [{"releases": releases}]}]}
    session = _DummySession(default=_DummyResponse(json_data=payload))
    items = fetch_releasebot(_ctx(session))
    assert items[0].url == "https://releasebot.io/updates/corp/widget"
    assert items[0].title == "Widget \u2014 1.0"


def test_decode_devalue_data_with_refs():
    data = [{"name": 1, "items": 2}, "hello", ["a", "b"]]
    result = _decode_devalue_data(data)
    assert result == {"name": "hello", "items": ["a", "b"]}


def test_decode_devalue_data_empty():
    assert _decode_devalue_data([]) is None
