from __future__ import annotations

from datetime import datetime
from pathlib import Path

from article_harvest.models import FetchContext
from article_harvest.sources.blogs.hf_blog import fetch_hf_blog


class DummySession:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads

    def get(self, url: str, timeout: int = 20):
        return DummyResponse(self.payloads[url])


class DummyResponse:
    def __init__(self, payload: bytes) -> None:
        self.content = payload

    def raise_for_status(self):
        return None


def test_hf_blog_fetch_fills_body_when_rss_has_no_description():
    fixtures = Path(__file__).parent / "fixtures"
    feed = (fixtures / "hf_rss_no_description.xml").read_bytes()
    article = (fixtures / "hf_sample_article.html").read_bytes()

    session = DummySession(
        {
            "https://huggingface.co/blog/feed.xml": feed,
            "https://example.com/hf-post": article,
        }
    )
    ctx = FetchContext(session=session, run_id="run", now=datetime.utcnow())
    items = fetch_hf_blog(ctx)
    assert len(items) == 1

    content = items[0].content_markdown or ""
    assert "This is a long first paragraph" in content
    assert "Upvote" not in content
