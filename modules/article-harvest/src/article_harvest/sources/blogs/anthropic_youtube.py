from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "anthropic-youtube",
        "Anthropic YouTube",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCrDwWp7EBBv4NwvScIpBDOA",
    )
