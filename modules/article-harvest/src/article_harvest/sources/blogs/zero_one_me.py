from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("01-me", "01.me", "https://01.me/atom.xml")
