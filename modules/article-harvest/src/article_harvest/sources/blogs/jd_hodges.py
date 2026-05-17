from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "jd-hodges",
        "J.D. Hodges",
        "https://www.jdhodges.com/feed/",
    )
