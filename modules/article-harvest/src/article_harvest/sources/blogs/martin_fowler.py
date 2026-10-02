from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "martin-fowler",
        "martinfowler.com",
        "https://martinfowler.com/feed.atom",
    )
