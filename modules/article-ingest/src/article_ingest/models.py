from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourcePolicy:
    mode: str = "html"  # html | rss | hn | lobsters | api | js
    max_rpm: int | None = 30
    min_interval_sec: float | None = None
    jitter_sec: float = 0.0
    concurrency: int = 1
    headless_allowed: bool = False
    cache_ttl_sec: int | None = None
    retry_limit: int = 2
    always_refetch: bool = True


@dataclass
class Source:
    id: int
    slug: str
    name: str
    homepage_url: str | None
    enabled: bool
    policy: SourcePolicy
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ItemCandidate:
    item_key: str
    canonical_url: str
    title: str | None
    author: str | None
    published_at: str | None
    summary: str | None = None
    detail_url: str | None = None
    comment_url: str | None = None
