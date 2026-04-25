from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "nvidia-robotics",
        "NVIDIA Blog (Robotics)",
        "https://blogs.nvidia.com/blog/category/robotics/feed/",
    )
