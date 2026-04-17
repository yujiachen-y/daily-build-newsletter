from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "techcrunch-fundings",
        "TechCrunch Fundings & Exits",
        "https://techcrunch.com/tag/funding/feed/",
        max_age_days=60,
    )
