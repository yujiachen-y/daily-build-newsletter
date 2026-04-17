from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "training-data",
        "Training Data (Sequoia)",
        "https://feeds.megaphone.fm/trainingdata",
    )
