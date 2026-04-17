from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "sv101",
        "硅谷101",
        "https://feeds.fireside.fm/sv101/rss",
    )
