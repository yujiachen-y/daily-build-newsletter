from __future__ import annotations

from datetime import datetime
from pathlib import Path

from article_harvest.models import FetchContext
from article_harvest.sources.rss import fetch_rss, make_rss_source


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


def test_fetch_rss_max_age_days_filters_old_articles():
    fixture = Path(__file__).parent / "fixtures" / "rss_sample.xml"
    payload = fixture.read_bytes()
    session = DummySession(payload)
    # The fixture article is from 2026-01-13. Set "now" to 2026-01-14 → within 3 days.
    ctx_recent = FetchContext(
        session=session, run_id="run", now=datetime(2026, 1, 14)
    )
    items = fetch_rss(ctx_recent, "https://example.com/feed", max_age_days=3)
    assert len(items) == 1

    # Set "now" to 2026-02-01 → article is 19 days old, beyond 3-day cutoff.
    # Filter-layer empty returns []; the upstream ingester decides how to handle it.
    ctx_old = FetchContext(
        session=session, run_id="run", now=datetime(2026, 2, 1)
    )
    items = fetch_rss(ctx_old, "https://example.com/feed", max_age_days=3)
    assert items == []


def test_fetch_rss_no_max_age_keeps_all():
    fixture = Path(__file__).parent / "fixtures" / "rss_sample.xml"
    payload = fixture.read_bytes()
    session = DummySession(payload)
    # Even with a very late "now", no filtering without max_age_days.
    ctx = FetchContext(session=session, run_id="run", now=datetime(2030, 1, 1))
    items = fetch_rss(ctx, "https://example.com/feed")
    assert len(items) == 1


def test_make_rss_source_default_cutoff_is_90_days():
    fixture = Path(__file__).parent / "fixtures" / "rss_sample.xml"
    payload = fixture.read_bytes()
    session = DummySession(payload)
    src = make_rss_source("sample", "Sample", "https://example.com/feed")

    # Fixture article is from 2026-01-13; within 90 days of 2026-03-01.
    within = FetchContext(session=session, run_id="run", now=datetime(2026, 3, 1))
    assert len(src.fetch(within)) == 1

    # 120 days later is outside the default cutoff.
    beyond = FetchContext(session=session, run_id="run", now=datetime(2026, 5, 15))
    assert src.fetch(beyond) == []
