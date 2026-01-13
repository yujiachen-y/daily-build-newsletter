from __future__ import annotations

from datetime import datetime
from pathlib import Path

from article_harvest.models import FetchContext
from article_harvest.sources.rss import fetch_rss


class DummySession:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def get(self, url: str, timeout: int = 20):
        return DummyResponse(self.payload)


class DummyResponse:
    def __init__(self, payload: bytes) -> None:
        self.content = payload

    def raise_for_status(self):
        return None


def test_fetch_rss_parses_items():
    fixture = Path(__file__).parent / "fixtures" / "rss_sample.xml"
    payload = fixture.read_bytes()
    session = DummySession(payload)
    ctx = FetchContext(session=session, run_id="run", now=datetime.utcnow())
    items = fetch_rss(ctx, "https://example.com/feed")
    assert len(items) == 1
    assert items[0].title == "Sample Post"
