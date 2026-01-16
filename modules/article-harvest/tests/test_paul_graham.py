from __future__ import annotations

from datetime import datetime
from pathlib import Path

from article_harvest.models import FetchContext
from article_harvest.sources.blogs.paul_graham import fetch_paul_graham


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


def test_paul_graham_fetch_fills_body_when_rss_has_no_description():
    fixtures = Path(__file__).parent / "fixtures"
    feed = (fixtures / "pg_rss_no_description.xml").read_bytes()
    article = (fixtures / "pg_sample_article.html").read_bytes()

    session = DummySession(
        {
            "http://www.aaronsw.com/2002/feeds/pgessays.rss": feed,
            "https://example.com/pg-sample": article,
        }
    )
    ctx = FetchContext(session=session, run_id="run", now=datetime.utcnow())
    items = fetch_paul_graham(ctx)
    assert len(items) == 1
    assert "Hello world" in (items[0].content_markdown or "")
