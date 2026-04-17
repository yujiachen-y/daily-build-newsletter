from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "cognitive-revolution",
        "The Cognitive Revolution (Nathan Labenz)",
        "https://feeds.megaphone.fm/RINTP3108857801",
    )
