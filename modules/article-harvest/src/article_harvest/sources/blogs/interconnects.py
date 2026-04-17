from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "interconnects",
        "Interconnects (Nathan Lambert)",
        "https://www.interconnects.ai/feed",
    )
