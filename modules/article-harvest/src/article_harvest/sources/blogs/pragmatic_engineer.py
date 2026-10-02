from __future__ import annotations

from ..substack import make_substack_source


def source():
    return make_substack_source(
        "pragmatic-engineer",
        "Pragmatic Engineer",
        "https://newsletter.pragmaticengineer.com/feed",
    )
