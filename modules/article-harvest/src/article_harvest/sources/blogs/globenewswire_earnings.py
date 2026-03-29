from __future__ import annotations

from ..rss import make_rss_source

_FEED_URL = (
    "https://www.globenewswire.com/RssFeed/subjectcode"
    "/13-Earnings%20Releases%20And%20Operating%20Results"
)


def source():
    return make_rss_source(
        "globenewswire-earnings",
        "GlobeNewswire Earnings",
        _FEED_URL,
    )
