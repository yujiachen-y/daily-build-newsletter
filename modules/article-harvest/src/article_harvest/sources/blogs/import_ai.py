from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "import-ai",
        "Import AI (Jack Clark)",
        "https://importai.substack.com/feed",
    )
