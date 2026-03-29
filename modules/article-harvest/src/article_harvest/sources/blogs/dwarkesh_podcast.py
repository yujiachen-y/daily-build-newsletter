from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "dwarkesh-podcast",
        "Dwarkesh Podcast",
        "https://api.substack.com/feed/podcast/69345.rss",
    )
