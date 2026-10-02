from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "ai-native-dev",
        "The AI Native Dev (Tessl)",
        "https://rss.buzzsprout.com/2375985.rss",
    )
