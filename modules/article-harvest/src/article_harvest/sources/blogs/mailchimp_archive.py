from __future__ import annotations

from ..rss import make_rss_source

MAILCHIMP_FEED = "https://us7.campaign-archive.com/feed?u=6507bf4e4c2df3fdbae6ef738&id=547725049b"


def source():
    return make_rss_source("mailchimp-archive", "Mailchimp Archive", MAILCHIMP_FEED)
