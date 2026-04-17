from __future__ import annotations

from ..rss import make_rss_source


def source():
    # DeepLearning.AI has no official RSS; this is a third-party mirror auto-rebuilt
    # hourly from the-batch listing pages. Fallback if it goes stale: parse
    # https://www.deeplearning.ai/sitemap-0.xml for /the-batch/issue-* URLs.
    return make_rss_source(
        "the-batch",
        "The Batch (DeepLearning.AI)",
        "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_the_batch.xml",
    )
