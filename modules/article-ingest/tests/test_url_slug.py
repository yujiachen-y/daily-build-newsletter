from __future__ import annotations

from article_ingest.url_slug import normalize_url


def test_normalize_url_sorts_query_and_strips_trailing_slash():
    url = "HTTPS://Example.com/path/?b=2&a=1"
    assert normalize_url(url) == "https://example.com/path?a=1&b=2"
