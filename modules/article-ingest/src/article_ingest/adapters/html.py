from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from ..models import ItemCandidate, Source
from ..text_processing import detect_blocked_html
from ..url_slug import normalize_url
from .base import AdapterError


class HtmlListAdapter:
    def discover(self, source: Source, session: requests.Session) -> list[ItemCandidate]:
        list_url = source.config.get("list_url")
        if not list_url:
            raise AdapterError("Missing list_url in source config")
        response = session.get(list_url, timeout=20)
        if response.status_code >= 400:
            raise AdapterError(f"HTTP {response.status_code}")
        response.encoding = response.apparent_encoding
        blocked = detect_blocked_html(response.text)
        if blocked:
            raise AdapterError(f"Blocked content detected: {blocked}")
        soup = BeautifulSoup(response.text, "lxml")
        item_selector = source.config.get("item_selector")
        if not item_selector:
            raise AdapterError("Missing item_selector in source config")
        items = soup.select(item_selector)
        url_selector = source.config.get("url_selector")
        url_attr = source.config.get("url_attr", "href")
        title_selector = source.config.get("title_selector")
        date_selector = source.config.get("date_selector")
        author_selector = source.config.get("author_selector")
        summary_selector = source.config.get("summary_selector")
        limit = source.config.get("limit")

        candidates: list[ItemCandidate] = []
        for element in items:
            link_el = element.select_one(url_selector) if url_selector else element.find("a")
            href = link_el.get(url_attr) if link_el else None
            if not href:
                continue
            detail_url = urljoin(list_url, href)
            canonical = normalize_url(detail_url)
            title = None
            if title_selector:
                title_el = element.select_one(title_selector)
                title = title_el.get_text(strip=True) if title_el else None
            elif link_el:
                title = link_el.get_text(strip=True)
            author = None
            if author_selector:
                author_el = element.select_one(author_selector)
                author = author_el.get_text(strip=True) if author_el else None
            published = None
            if date_selector:
                date_el = element.select_one(date_selector)
                if date_el:
                    text = date_el.get_text(strip=True)
                    try:
                        published = dateparser.parse(text).isoformat()
                    except Exception:
                        published = None
            summary = None
            if summary_selector:
                summary_el = element.select_one(summary_selector)
                summary = summary_el.get_text(strip=True) if summary_el else None

            item_key = canonical or detail_url
            candidates.append(
                ItemCandidate(
                    item_key=item_key,
                    canonical_url=canonical or detail_url,
                    title=title,
                    author=author,
                    published_at=published,
                    summary=summary,
                    detail_url=detail_url,
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
