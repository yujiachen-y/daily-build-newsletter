from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "paul-graham",
        "Paul Graham",
        "http://www.aaronsw.com/2002/feeds/pgessays.rss",
    )
