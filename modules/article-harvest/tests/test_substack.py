from __future__ import annotations

from datetime import datetime

from article_harvest.models import FetchContext
from article_harvest.sources.substack import make_substack_source

FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>P</title><link>https://n.example.com</link>
<item>
  <title>Paid post</title>
  <link>https://n.example.com/p/paid-slug</link>
  <description>&lt;p&gt;Teaser&lt;/p&gt;
    &lt;a href="https://n.example.com/p/paid-slug"&gt;Read more&lt;/a&gt;</description>
</item>
<item>
  <title>Free post</title>
  <link>https://n.example.com/p/free-slug</link>
  <description>&lt;p&gt;Whole thing&lt;/p&gt;</description>
</item>
</channel></rss>
""".encode()


class _Response:
    def __init__(self, content=b"", json_data=None):
        self.content = content
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class _Session:
    def __init__(self):
        self.api_calls = []

    def get(self, url, timeout=20, cookies=None):
        if url.endswith("/feed"):
            return _Response(content=FEED)
        self.api_calls.append((url, cookies))
        if url.startswith("https://substack.com/"):
            return _Response(json_data={"post": {"body_html": "<p>Full paid body</p>"}})
        return _Response(json_data={"id": 42, "body_html": "<p>Teaser</p>"})


def _fetch(monkeypatch, sid=None):
    if sid is None:
        monkeypatch.delenv("SUBSTACK_SID", raising=False)
    else:
        monkeypatch.setenv("SUBSTACK_SID", sid)
    session = _Session()
    ctx = FetchContext(session=session, run_id="run", now=datetime.utcnow())
    source = make_substack_source("test", "Test", "https://n.example.com/feed", max_age_days=None)
    return source.fetch(ctx), session


def test_paid_post_unlocked_with_cookie(monkeypatch):
    items, session = _fetch(monkeypatch, sid="abc123")
    assert "Full paid body" in items[0].content_markdown
    assert session.api_calls == [
        ("https://n.example.com/api/v1/posts/paid-slug", None),
        ("https://substack.com/api/v1/posts/by-id/42", {"substack.sid": "abc123"}),
    ]


def test_free_post_untouched(monkeypatch):
    items, _ = _fetch(monkeypatch, sid="abc123")
    assert "Whole thing" in items[1].content_markdown


def test_no_cookie_keeps_preview(monkeypatch):
    items, session = _fetch(monkeypatch)
    assert "Read more" in items[0].content_markdown
    assert session.api_calls == []


def test_storage_replaces_paywall_preview(tmp_path):
    from article_harvest.storage import Storage

    path = tmp_path / "content.md"
    path.write_text("Teaser\n\n[Read more](https://n.example.com/p/paid-slug)", encoding="utf-8")
    assert Storage._needs_content_refresh(path, "Full paid body")
    assert not Storage._needs_content_refresh(path, "Teaser\n\n[Read more](https://x)")
