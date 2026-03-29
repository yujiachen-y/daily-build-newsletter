from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("ainews-smol", "AINews (smol.ai)", "https://news.smol.ai/rss.xml")
