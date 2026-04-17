from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "techcrunch-venture",
        "TechCrunch Venture",
        "https://techcrunch.com/category/venture/feed/",
        max_age_days=3,
    )
