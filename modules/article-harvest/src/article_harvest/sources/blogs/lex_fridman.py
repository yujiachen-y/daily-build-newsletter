from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "lex-fridman",
        "Lex Fridman Podcast",
        "https://lexfridman.com/feed/podcast/",
    )
