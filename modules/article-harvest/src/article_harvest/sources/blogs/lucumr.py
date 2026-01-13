from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("lucumr", "Lars (lucumr)", "https://lucumr.pocoo.org/feed.atom")
