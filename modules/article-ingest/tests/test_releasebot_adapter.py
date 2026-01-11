from __future__ import annotations

import pytest

from article_ingest.adapters.base import AdapterError
from article_ingest.adapters.releasebot import (
    ReleasebotAdapter,
    _apply_query,
    _extract_release_root,
    _parse_release,
    decode_devalue_data,
)
from article_ingest.models import Source, SourcePolicy


def test_decode_devalue_data_resolves_references():
    data = [
        {"foo": 1, "bar": 2},
        {"id": 3, "name": 4},
        [1],
        123,
        "alice",
    ]
    decoded = decode_devalue_data(data)
    assert decoded == {"foo": {"id": 123, "name": "alice"}, "bar": [{"id": 123, "name": "alice"}]}


def test_parse_release_builds_candidate():
    release = {
        "id": 1,
        "slug": "v1-1",
        "release_details": {"release_name": "v1", "release_summary": "summary"},
        "product": {
            "display_name": "Widget",
            "slug": "widget",
            "vendor": {"slug": "acme", "display_name": "Acme"},
        },
        "source": {"source_url": "https://example.com/release"},
        "release_date": "2026-01-11T00:00:00",
        "formatted_content": "### Hello",
    }
    parsed = _parse_release(release)
    assert parsed is not None
    assert parsed.candidate.title == "Widget — v1"
    assert parsed.candidate.canonical_url == "https://example.com/release"
    assert parsed.markdown.startswith("### Hello")


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.urls = []

    def get(self, url, timeout=20):
        self.urls.append(url)
        if not self._responses:
            raise AssertionError("No more fake responses")
        return self._responses.pop(0)


def _payload(releases, next_offset=None):
    root = {"releases": releases}
    if next_offset is not None:
        root["nextOffset"] = next_offset
    return {"nodes": [{"data": [root]}]}


def test_apply_query_merges_params():
    url = "https://releasebot.io/updates/__data.json?offset=1"
    merged = _apply_query(url, {"offset": "2", "q": "bot"})
    assert merged == "https://releasebot.io/updates/__data.json?offset=2&q=bot"


def test_discover_paginates_and_fetch_detail():
    releases_page1 = [
        {
            "id": "rel-1",
            "slug": "rel-1",
            "release_details": {"release_name": "v1", "release_summary": "summary"},
            "product": {"slug": "widget", "display_name": "Widget", "vendor": {"slug": "acme"}},
            "source": {"source_url": "https://example.com/release-1"},
            "release_date": "2026-01-11T00:00:00",
            "formatted_content": "### Notes\n\n- first",
        },
        {
            "id": "rel-2",
            "slug": "rel-2",
            "release_details": {"release_name": "v2"},
            "product": {"slug": "widget", "display_name": "Widget", "vendor": {"slug": "acme"}},
            "source": {"source_url": "https://example.com/release-2"},
            "release_date": "2026-01-10T00:00:00",
            "formatted_content": "### Notes\n\n- second",
        },
    ]
    releases_page2 = [
        {
            "id": "rel-3",
            "slug": "rel-3",
            "release_details": {"release_name": "v3"},
            "product": {"slug": "widget", "display_name": "Widget", "vendor": {"slug": "acme"}},
            "source": {"source_url": "https://example.com/release-3"},
            "release_date": "2026-01-09T00:00:00",
            "formatted_content": "### Notes\n\n- third",
        },
    ]
    payloads = [
        _FakeResponse(_payload(releases_page1, next_offset="page2")),
        _FakeResponse(_payload(releases_page2)),
    ]
    session = _FakeSession(payloads)
    adapter = ReleasebotAdapter()
    source = Source(
        id=1,
        slug="releasebot",
        name="Releasebot",
        homepage_url=None,
        enabled=True,
        policy=SourcePolicy(mode="releasebot"),
        config={"data_url": "https://releasebot.io/updates/__data.json", "limit": 3},
    )

    candidates = adapter.discover(source, session)
    assert len(candidates) == 3
    assert candidates[0].item_key.startswith("releasebot:acme:widget")
    html = adapter.fetch_detail(candidates[0], session)
    assert "<article>" in html
    assert "### Notes" in html
    assert "first" in html
    assert session.urls[0] == "https://releasebot.io/updates/__data.json"
    assert session.urls[1] == "https://releasebot.io/updates/__data.json?offset=page2"


def test_extract_release_root_errors():
    with pytest.raises(AdapterError):
        _extract_release_root({"nodes": [{"data": [{"foo": "bar"}]}]})


def test_discover_raises_on_http_error():
    adapter = ReleasebotAdapter()
    source = Source(
        id=1,
        slug="releasebot",
        name="Releasebot",
        homepage_url=None,
        enabled=True,
        policy=SourcePolicy(mode="releasebot"),
        config={"data_url": "https://releasebot.io/updates/__data.json"},
    )
    session = _FakeSession([_FakeResponse({}, status_code=500)])
    with pytest.raises(AdapterError):
        adapter.discover(source, session)
