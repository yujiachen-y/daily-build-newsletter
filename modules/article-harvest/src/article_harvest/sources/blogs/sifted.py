from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("sifted", "Sifted", "https://sifted.eu/feed/", max_age_days=3)
