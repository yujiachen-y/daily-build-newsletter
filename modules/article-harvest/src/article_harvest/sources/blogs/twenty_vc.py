from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "20vc",
        "20VC (Harry Stebbings)",
        "https://rss.libsyn.com/shows/61840/destinations/240976.xml",
    )
