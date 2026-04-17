from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "last-week-in-ai",
        "Last Week in AI",
        "https://lastweekin.ai/feed",
    )
