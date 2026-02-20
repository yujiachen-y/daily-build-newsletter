from __future__ import annotations

from datetime import datetime

from article_harvest.models import FetchContext
from article_harvest.sources.blogs.alphasignal_last_email import (
    _cleanup_markdown,
    _collapse_blank_lines,
    _is_pipe_separator,
    _is_table_rule,
    _trim_preamble,
)
from article_harvest.sources.blogs.claude_blog import fetch_claude_blog
from article_harvest.sources.blogs.founders_fund_anatomy import fetch_founders_fund
from article_harvest.sources.blogs.openai_dev_blog import fetch_openai_dev_blog

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


# -- Claude Blog --


_CLAUDE_LISTING = """\
<html><body><main>
  <article><a href="/blog/post-one"><h2>Post One</h2></a></article>
  <article><a href="/blog/post-two"><h2>Post Two</h2></a></article>
  <article><a href="/blog/category/news">Category link</a></article>
</main></body></html>"""

_CLAUDE_ARTICLE = """\
<html><head>
<script type="application/ld+json">{"datePublished": "2026-01-15"}</script>
</head><body><main>
  <h1>The Real Title</h1>
  <p>Interesting article content goes here with enough text to verify.</p>
</main></body></html>"""


def test_fetch_claude_blog():
    session = _DummySession(
        responses={"https://claude.com/blog": _DummyResponse(text=_CLAUDE_LISTING)},
        default=_DummyResponse(text=_CLAUDE_ARTICLE),
    )
    items = fetch_claude_blog(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "The Real Title"
    assert items[0].published_at == "2026-01-15"
    assert "Interesting article content" in items[0].content_markdown


# -- OpenAI Developers Blog --


_OPENAI_LISTING = """\
<html><body><main>
  <a href="/blog/new-feature">New Feature</a>
  <a href="/blog/update">Update</a>
  <a href="/blog/topic/ai">Topic link</a>
  <a href="/docs/api">Docs link</a>
</main></body></html>"""

_OPENAI_ARTICLE = """\
<html><body><article>
  <h1>OpenAI Feature</h1>
  <p>Details about the new feature.</p>
</article></body></html>"""


def test_fetch_openai_dev_blog():
    session = _DummySession(
        responses={
            "https://developers.openai.com/blog": _DummyResponse(text=_OPENAI_LISTING),
        },
        default=_DummyResponse(text=_OPENAI_ARTICLE),
    )
    items = fetch_openai_dev_blog(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "OpenAI Feature"
    assert "new feature" in items[0].content_markdown.lower()


# -- AlphaSignal helpers --


def test_is_table_rule_true():
    assert _is_table_rule("| --- | --- | --- | --- | --- |")


def test_is_table_rule_false_blank():
    assert not _is_table_rule("")


def test_is_table_rule_false_few_pipes():
    assert not _is_table_rule("| a |")


def test_is_pipe_separator_true():
    assert _is_pipe_separator("|  |  |")


def test_is_pipe_separator_false_has_text():
    assert not _is_pipe_separator("| hello |")


def test_is_pipe_separator_false_blank():
    assert not _is_pipe_separator("")


def test_trim_preamble_hey():
    lines = ["Welcome", "Hey there!", "Content"]
    assert _trim_preamble(lines) == ["Hey there!", "Content"]


def test_trim_preamble_daily_briefing():
    lines = ["Logo", "Your daily briefing is here", "Data"]
    assert _trim_preamble(lines) == ["Your daily briefing is here", "Data"]


def test_trim_preamble_no_match():
    lines = ["Content only", "More content"]
    assert _trim_preamble(lines) == lines


def test_collapse_blank_lines():
    lines = ["a", "", "", "", "b", "", "c"]
    assert _collapse_blank_lines(lines) == "a\n\nb\n\nc"


def test_cleanup_markdown():
    text = "Hey folks!\n| --- | --- | --- | --- | --- |\n\nContent\n|  |\n\n\nMore"
    result = _cleanup_markdown(text)
    assert "---" not in result
    assert "Hey folks!" in result
    assert "Content" in result
    assert "More" in result


# -- Founders Fund Anatomy --


def test_fetch_founders_fund():
    payload = [
        {
            "title": {"rendered": "<b>Deep Tech</b>"},
            "link": "https://foundersfund.com/anatomy/deep-tech",
            "date": "2026-01-10",
            "excerpt": {"rendered": "<p>Summary here</p>"},
            "content": {"rendered": "<p>Full content here</p>"},
        },
        {
            "title": {"rendered": "Second Post"},
            "link": "https://foundersfund.com/anatomy/second",
            "date": "2026-01-11",
            "excerpt": {"rendered": "<p>Another summary</p>"},
            "content": {"rendered": "<p>Another full post</p>"},
        },
    ]
    session = _DummySession(default=_DummyResponse(json_data=payload))
    items = fetch_founders_fund(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "Deep Tech"
    assert items[0].published_at == "2026-01-10"
    assert items[0].content_markdown is not None
    assert "Full content" in items[0].content_markdown
    assert items[0].summary is not None
