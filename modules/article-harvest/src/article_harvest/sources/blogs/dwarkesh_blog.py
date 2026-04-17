from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "dwarkesh-blog",
        "Dwarkesh Blog (Dwarkesh Patel)",
        "https://www.dwarkesh.com/feed",
    )
