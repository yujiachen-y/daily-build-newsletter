from __future__ import annotations

import feedparser
import requests
from dateutil import parser as dateparser

from ..models import ItemCandidate, Source
from ..url_slug import normalize_url
from .base import AdapterError


class RssAdapter:
    def discover(self, source: Source, session: requests.Session) -> list[ItemCandidate]:
        feed_url = source.config.get("feed_url")
        if not feed_url:
            raise AdapterError("Missing feed_url in source config")
        parsed = feedparser.parse(feed_url)
        limit = source.config.get("limit")
        candidates: list[ItemCandidate] = []
        for entry in parsed.entries:
            link = entry.get("link")
            canonical = normalize_url(link) if link else None
            published = None
            if entry.get("published"):
                try:
                    published = dateparser.parse(entry["published"]).isoformat()
                except Exception:
                    published = None
            title = entry.get("title")
            author = entry.get("author")
            item_key = canonical or (title or link or "")
            candidates.append(
                ItemCandidate(
                    item_key=item_key,
                    canonical_url=canonical or link or "",
                    title=title,
                    author=author,
                    published_at=published,
                    summary=entry.get("summary"),
                    detail_url=link,
                )
            )
            if limit and len(candidates) >= int(limit):
                break
        return candidates

    def fetch_detail(self, candidate: ItemCandidate, session: requests.Session) -> str:
        if not candidate.detail_url:
            raise AdapterError("No detail_url for candidate")
        response = session.get(candidate.detail_url, timeout=20)
        if response.status_code >= 400:
            raise AdapterError(f"HTTP {response.status_code}")
        response.encoding = response.apparent_encoding
        return response.text
