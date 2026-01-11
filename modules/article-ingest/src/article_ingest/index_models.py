from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .ingest_fetch import build_session


@dataclass(frozen=True)
class IndexSource:
    slug: str
    name: str
    homepage_url: str


@dataclass
class IndexComment:
    depth: int
    author: str | None
    body: str
    created_at: str | None
    is_deleted: bool = False


@dataclass
class IndexEntry:
    title: str
    url: str
    author: str | None = None
    published_at: str | None = None
    score: int | None = None
    comments_count: int | None = None
    comments: list[IndexComment] | None = None
    summary: str | None = None
    details: str | None = None
    tags: list[str] | None = None
    external_link_missing: bool = False

    def __post_init__(self) -> None:
        if self.comments is None:
            self.comments = []
        if self.tags is None:
            self.tags = []


@dataclass
class IndexFetchStats:
    requests: int
    errors: int
    duration_ms: int


@dataclass
class IndexFetchResult:
    entries: list[IndexEntry]
    stats: IndexFetchStats
    errors: list[str]


class IndexFetchError(Exception):
    pass


class IndexRequestor:
    def __init__(self) -> None:
        self.session = build_session(None)
        self.requests = 0
        self.errors: list[str] = []

    def _record_error(self, message: str) -> None:
        self.errors.append(message)

    def get(self, url: str, timeout: int = 20) -> requests.Response:
        self.requests += 1
        try:
            response = self.session.get(url, timeout=timeout)
        except Exception as exc:
            message = f"{url} error={exc}"
            self._record_error(message)
            raise IndexFetchError(message) from exc
        if response.status_code >= 400:
            message = f"{url} HTTP {response.status_code}"
            self._record_error(message)
            raise IndexFetchError(message)
        return response

    def get_json(self, url: str, timeout: int = 20) -> Any:
        response = self.get(url, timeout=timeout)
        try:
            return response.json()
        except Exception as exc:
            message = f"{url} invalid_json={exc}"
            self._record_error(message)
            raise IndexFetchError(message) from exc

    def get_text(self, url: str, timeout: int = 20) -> str:
        response = self.get(url, timeout=timeout)
        response.encoding = response.apparent_encoding
        return response.text

    def get_bytes(self, url: str, timeout: int = 20) -> bytes:
        response = self.get(url, timeout=timeout)
        return response.content
