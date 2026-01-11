from __future__ import annotations

from types import SimpleNamespace

import pytest

from article_ingest.adapters import adapter_for_mode
from article_ingest.adapters.comments import HackerNewsAdapter, LobstersAdapter
from article_ingest.adapters.html import HtmlListAdapter
from article_ingest.adapters.rss import RssAdapter
from article_ingest.models import Source, SourcePolicy


class FakeResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        self.apparent_encoding = "utf-8"


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response

    def get(self, url, timeout=20):
        return self._response


class MappingSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self._responses = responses

    def get(self, url, timeout=20):
        return self._responses[url]


def test_html_adapter_discovers_items():
    html = """
    <div class="post">
      <a class="link" href="/a">First</a>
      <time>2026-01-10</time>
      <span class="byline">Alice</span>
    </div>
    <div class="post">
      <a class="link" href="/b">Second</a>
      <time>2026-01-09</time>
      <span class="byline">Bob</span>
    </div>
    """
    source = Source(
        id=1,
        slug="demo",
        name="Demo",
        homepage_url="https://example.com",
        enabled=True,
        policy=SourcePolicy(mode="html"),
        config={
            "list_url": "https://example.com/blog",
            "item_selector": ".post",
            "url_selector": ".link",
            "title_selector": ".link",
            "date_selector": "time",
            "author_selector": ".byline",
        },
    )
    adapter = HtmlListAdapter()
    session = FakeSession(FakeResponse(200, html))

    candidates = adapter.discover(source, session)
    assert len(candidates) == 2
    assert candidates[0].title == "First"
    assert candidates[0].author == "Alice"
    assert candidates[0].detail_url.endswith("/a")


def test_html_adapter_fetch_detail_error():
    source = Source(
        id=1,
        slug="demo",
        name="Demo",
        homepage_url="https://example.com",
        enabled=True,
        policy=SourcePolicy(mode="html"),
        config={
            "list_url": "https://example.com",
            "item_selector": ".post",
            "url_selector": ".link",
        },
    )
    adapter = HtmlListAdapter()
    html = "<div class=\"post\"><a class=\"link\" href=\"/a\">A</a></div>"
    session = FakeSession(FakeResponse(200, html))
    candidate = adapter.discover(source, session)[0]
    error_session = FakeSession(FakeResponse(404, "no"))

    with pytest.raises(Exception):
        adapter.fetch_detail(candidate, error_session)


def test_rss_adapter_discovers(monkeypatch):
    entries = [
        {
            "link": "https://example.com/post",
            "published": "2026-01-10T00:00:00+00:00",
            "title": "Post",
            "author": "Alice",
            "summary": "Summary",
        }
    ]

    def fake_parse(url):
        return SimpleNamespace(entries=entries)

    monkeypatch.setattr("article_ingest.adapters.rss.feedparser.parse", fake_parse)

    source = Source(
        id=1,
        slug="rss",
        name="RSS",
        homepage_url=None,
        enabled=True,
        policy=SourcePolicy(mode="rss"),
        config={"feed_url": "https://example.com/feed"},
    )
    adapter = RssAdapter()
    candidates = adapter.discover(source, session=None)
    assert len(candidates) == 1
    assert candidates[0].title == "Post"


def test_adapter_for_mode_comment_sites():
    assert isinstance(adapter_for_mode("hn"), HackerNewsAdapter)
    assert isinstance(adapter_for_mode("lobsters"), LobstersAdapter)


def test_hn_adapter_discovers_and_comments():
    list_html = """
    <tr class="athing" id="1">
      <td class="title"><span class="titleline"><a href="https://example.com/story">Story</a></span></td>
    </tr>
    <tr>
      <td class="subtext">
        <a class="hnuser">alice</a>
        <span class="age" title="2026-01-10T00:00:00+00:00">1 day ago</span>
        <a href="item?id=123">5 comments</a>
      </td>
    </tr>
    """
    comments_html = """
    <tr class="athing comtr">
      <td class="default">
        <span class="commtext">Hello <i>world</i></span>
        <a class="hnuser">bob</a>
        <span class="age" title="2026-01-10T12:00:00+00:00">2 hours ago</span>
      </td>
    </tr>
    """
    list_url = "https://news.ycombinator.com/"
    comment_url = "https://news.ycombinator.com/item?id=123"
    session = MappingSession(
        {
            list_url: FakeResponse(200, list_html),
            comment_url: FakeResponse(200, comments_html),
        }
    )
    source = Source(
        id=1,
        slug="hn",
        name="HN",
        homepage_url=list_url,
        enabled=True,
        policy=SourcePolicy(mode="hn"),
        config={"list_url": list_url, "top_comments_limit": 1},
    )
    adapter = HackerNewsAdapter()
    candidates = adapter.discover(source, session)
    assert len(candidates) == 1
    assert candidates[0].comment_url == comment_url
    comments_md, count = adapter.fetch_comments(candidates[0], session, limit=1)
    assert count == 1
    assert "Top comments" in comments_md


def test_lobsters_adapter_discovers_and_comments():
    list_html = """
    <li class="story">
      <a class="u-url" href="https://example.com/post">Post</a>
      <a href="/s/abc123/post">3 comments</a>
    </li>
    """
    comments_html = """
    <li class="comment">
      <div class="comment_text"><p>Nice post</p></div>
      <span class="commenter"><a>carol</a></span>
      <time datetime="2026-01-11T00:00:00+00:00">now</time>
    </li>
    """
    list_url = "https://lobste.rs/"
    comment_url = "https://lobste.rs/s/abc123/post"
    session = MappingSession(
        {
            list_url: FakeResponse(200, list_html),
            comment_url: FakeResponse(200, comments_html),
        }
    )
    source = Source(
        id=2,
        slug="lobsters",
        name="Lobsters",
        homepage_url=list_url,
        enabled=True,
        policy=SourcePolicy(mode="lobsters"),
        config={"list_url": list_url, "top_comments_limit": 1},
    )
    adapter = LobstersAdapter()
    candidates = adapter.discover(source, session)
    assert len(candidates) == 1
    assert candidates[0].comment_url == comment_url
    comments_md, count = adapter.fetch_comments(candidates[0], session, limit=1)
    assert count == 1
    assert "Top comments" in comments_md
