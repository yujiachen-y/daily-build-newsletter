from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "unsupervised-learning",
        "Unsupervised Learning (Redpoint, Jacob Effron)",
        "https://feeds.simplecast.com/dOSE_bdP",
    )
