from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("gwern-changelog", "Gwern Changelog", "https://gwern.net/rss")
