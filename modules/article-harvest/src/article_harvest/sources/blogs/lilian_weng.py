from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("lilian-weng", "Lilian Weng", "https://lilianweng.github.io/index.xml")
