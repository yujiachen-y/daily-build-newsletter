from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "arxiv-cs-ai",
        "arXiv cs.AI",
        "http://export.arxiv.org/rss/cs.AI",
    )
