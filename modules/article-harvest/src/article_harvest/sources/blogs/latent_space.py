from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source("latent-space", "Latent Space", "https://www.latent.space/feed")
