from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "addy-osmani",
        "Elevate (Addy Osmani)",
        "https://addyo.substack.com/feed",
    )
