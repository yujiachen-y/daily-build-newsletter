from __future__ import annotations

from ..rss import make_rss_source


def source():
    # arxiv's /rss/cs.AI feed skips weekends (empty on Sat/Sun), so the daily
    # ingest fails 2 days a week. The Atom API's submittedDate query returns a
    # stable rolling window regardless of publication day.
    return make_rss_source(
        "arxiv-cs-ai",
        "arXiv cs.AI",
        "https://export.arxiv.org/api/query?search_query=cat:cs.AI"
        "&sortBy=submittedDate&sortOrder=descending&max_results=30",
    )
