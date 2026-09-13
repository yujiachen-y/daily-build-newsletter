from __future__ import annotations

from ..rss import make_rss_source


def source():
    # ponytail: feed has no per-item <link>, so item URLs fall back to the mp3
    # enclosure. Swap for a real episode page if one ever shows up in the feed.
    return make_rss_source(
        "moonshots",
        "Moonshots (Peter Diamandis)",
        "https://feeds.megaphone.fm/DVVTS2890392624",
    )
