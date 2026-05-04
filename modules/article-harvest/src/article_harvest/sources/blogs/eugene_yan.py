from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "eugene-yan",
        "Eugene Yan",
        "https://eugeneyan.com/rss/",
    )
