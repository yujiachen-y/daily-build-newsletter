from __future__ import annotations

from ..rss import make_rss_source

# The Information's direct RSS feed is behind Cloudflare protection.
# We use Google News RSS as a proxy with a site: filter instead.
_FEED_URL = (
    "https://news.google.com/rss/search"
    "?q=site:theinformation.com"
    "&hl=en-US&gl=US&ceid=US:en"
)


def source():
    return make_rss_source(
        "the-information", "The Information", _FEED_URL, max_age_days=3
    )
