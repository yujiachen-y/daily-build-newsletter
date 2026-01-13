from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("trends-vc", "Trends.vc", "https://trends.vc/feed/")
