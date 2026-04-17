from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "ml-street-talk",
        "Machine Learning Street Talk",
        "https://anchor.fm/s/1e4a0eac/podcast/rss",
    )
