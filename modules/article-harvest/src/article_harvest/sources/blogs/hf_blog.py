from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("hf-blog", "Hugging Face Blog", "https://huggingface.co/blog/feed.xml")
