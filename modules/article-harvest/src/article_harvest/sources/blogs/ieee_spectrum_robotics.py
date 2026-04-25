from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "ieee-spectrum-robotics",
        "IEEE Spectrum Robotics",
        "https://spectrum.ieee.org/feeds/topic/robotics.rss",
    )
