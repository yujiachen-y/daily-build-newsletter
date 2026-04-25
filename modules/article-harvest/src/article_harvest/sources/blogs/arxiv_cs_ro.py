from __future__ import annotations

from ..rss import make_rss_source


def source():
    # Mirrors arxiv_cs_ai: the /rss/cs.RO feed skips weekends, so use the Atom
    # API's submittedDate query for a stable rolling window.
    return make_rss_source(
        "arxiv-cs-ro",
        "arXiv cs.RO",
        "https://export.arxiv.org/api/query?search_query=cat:cs.RO"
        "&sortBy=submittedDate&sortOrder=descending&max_results=30",
    )
