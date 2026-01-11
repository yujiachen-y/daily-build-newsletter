from __future__ import annotations

from .base import AdapterError, SourceAdapter
from .comments import HackerNewsAdapter, LobstersAdapter
from .html import HtmlListAdapter
from .releasebot import ReleasebotAdapter
from .rss import RssAdapter


def adapter_for_mode(mode: str) -> SourceAdapter:
    if mode == "rss":
        return RssAdapter()
    if mode == "html":
        return HtmlListAdapter()
    if mode == "hn":
        return HackerNewsAdapter()
    if mode == "lobsters":
        return LobstersAdapter()
    if mode == "releasebot":
        return ReleasebotAdapter()
    raise AdapterError(f"Unsupported adapter mode: {mode}")

__all__ = ["AdapterError", "SourceAdapter", "adapter_for_mode"]
