from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("crunchbase-news", "Crunchbase News", "https://news.crunchbase.com/feed/")
