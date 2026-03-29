from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "no-priors",
        "No Priors (Sarah Guo & Elad Gil)",
        "https://feeds.megaphone.fm/nopriors",
    )
