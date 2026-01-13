from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

import requests


SourceKind = Literal["aggregation", "blog"]
SourceMethod = Literal["api", "rss", "html", "agent"]


@dataclass(frozen=True)
class FetchContext:
    session: requests.Session
    run_id: str
    now: datetime


@dataclass(frozen=True)
class BlogItem:
    title: str
    url: str
    published_at: str | None = None
    author: str | None = None
    summary: str | None = None
    content_markdown: str | None = None


@dataclass(frozen=True)
class AggregationComment:
    author: str | None
    published_at: str | None
    text: str


@dataclass(frozen=True)
class AggregationItem:
    title: str
    url: str
    published_at: str | None = None
    author: str | None = None
    score: int | None = None
    comments_count: int | None = None
    rank: int | None = None
    discussion_url: str | None = None
    comments: list[AggregationComment] = field(default_factory=list)
    extra: dict[str, str | int | None] = field(default_factory=dict)


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    kind: SourceKind
    method: SourceMethod
    fetch: Callable[[FetchContext], list[BlogItem] | list[AggregationItem]]
    enabled: bool = True


@dataclass(frozen=True)
class Record:
    source_id: str
    source_name: str
    kind: SourceKind
    title: str
    url: str
    archived_at: str
    published_at: str | None = None
    author: str | None = None
    snapshot_date: str | None = None
    rank: int | None = None
    comments_count: int | None = None
    score: int | None = None
    extra: dict[str, str | int | None] = field(default_factory=dict)
    item_id: str | None = None
    content_path: str | None = None

    def to_dict(self) -> dict[str, str | int | None | dict[str, str | int | None]]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "kind": self.kind,
            "title": self.title,
            "url": self.url,
            "archived_at": self.archived_at,
            "published_at": self.published_at,
            "author": self.author,
            "snapshot_date": self.snapshot_date,
            "rank": self.rank,
            "comments_count": self.comments_count,
            "score": self.score,
            "extra": self.extra or None,
            "item_id": self.item_id,
            "content_path": self.content_path,
        }
