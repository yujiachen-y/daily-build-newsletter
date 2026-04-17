from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "zhang-xiaojun",
        "张小珺商业访谈录",
        "https://feed.xyzfm.space/dk4yh3pkpjp3",
    )
