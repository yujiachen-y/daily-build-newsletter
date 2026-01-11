from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from markdownify import markdownify as md

from ..models import ItemCandidate, Source
from ..text_processing import normalize_markdown
from ..url_slug import normalize_url
from .base import AdapterError


def _comment_text_to_markdown(html: str) -> str:
    markdown = md(html, heading_style="ATX")
    return normalize_markdown(markdown).strip()


def _format_comments(comments: list[tuple[str | None, str | None, str]]) -> str:
    if not comments:
        return ""
    lines = ["# Top comments", ""]
    for idx, (author, timestamp, body) in enumerate(comments, start=1):
        header = f"{idx}. **{author or 'unknown'}**"
        if timestamp:
            header = f"{header} · {timestamp}"
        lines.append(header)
        lines.append("")
        lines.append(body)
        lines.append("")
    return "\n".join(lines).strip()


class HackerNewsAdapter:
    def __init__(self) -> None:
        self._top_comments_limit: int | None = None

    def discover(self, source: Source, session: requests.Session) -> list[ItemCandidate]:
        list_url = source.config.get("list_url") or "https://news.ycombinator.com/"
        self._top_comments_limit = source.config.get("top_comments_limit")
        response = session.get(list_url, timeout=20)
        if response.status_code >= 400:
            raise AdapterError(f"HTTP {response.status_code}")
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "lxml")
        rows = soup.select("tr.athing")
        limit = source.config.get("limit")

        candidates: list[ItemCandidate] = []
        for row in rows:
            title_el = row.select_one(".titleline a") or row.select_one("a")
            if title_el is None:
                continue
            href = title_el.get("href")
            if not href:
                continue
            article_url = urljoin(list_url, href)
            title = title_el.get_text(strip=True) or None
            subtext_row = row.find_next_sibling("tr")
            comment_url = None
            author = None
            published = None
            if subtext_row is not None:
                subtext = subtext_row.select_one(".subtext") or subtext_row
                author_el = subtext.select_one(".hnuser")
                if author_el is not None:
                    author = author_el.get_text(strip=True) or None
                age_el = subtext.select_one(".age")
                if age_el is not None:
                    time_text = age_el.get("title") or age_el.get_text(strip=True)
                    if time_text:
                        try:
                            published = dateparser.parse(time_text).isoformat()
                        except Exception:
                            published = None
                comment_el = None
                for link in subtext.find_all("a"):
                    link_href = link.get("href") or ""
                    if "item?id=" in link_href:
                        comment_el = link
                if comment_el is not None:
                    comment_href = comment_el.get("href")
                    if comment_href:
                        comment_url = urljoin(list_url, comment_href)

            canonical = normalize_url(article_url)
            item_key = canonical or article_url
            candidates.append(
                ItemCandidate(
                    item_key=item_key,
                    canonical_url=canonical or article_url,
                    title=title,
                    author=author,
                    published_at=published,
                    summary=None,
                    detail_url=article_url,
                    comment_url=comment_url,
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

    def fetch_comments(
        self,
        candidate: ItemCandidate,
        session: requests.Session,
        limit: int | None = None,
    ) -> tuple[str, int]:
        if not candidate.comment_url:
            return "", 0
        response = session.get(candidate.comment_url, timeout=20)
        if response.status_code >= 400:
            raise AdapterError(f"HTTP {response.status_code}")
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "lxml")
        rows = soup.select("tr.athing.comtr")
        if not rows:
            rows = soup.select("tr.comtr")
        max_count = limit or self._top_comments_limit or 5
        comments: list[tuple[str | None, str | None, str]] = []
        for row in rows:
            text_el = row.select_one(".commtext")
            if text_el is None:
                continue
            body = _comment_text_to_markdown(str(text_el))
            if not body:
                continue
            author_el = row.select_one(".hnuser")
            author = author_el.get_text(strip=True) if author_el is not None else None
            age_el = row.select_one(".age")
            timestamp = None
            if age_el is not None:
                timestamp = age_el.get("title") or age_el.get_text(strip=True) or None
            comments.append((author, timestamp, body))
            if len(comments) >= max_count:
                break
        return _format_comments(comments), len(comments)


class LobstersAdapter:
    def __init__(self) -> None:
        self._top_comments_limit: int | None = None

    def discover(self, source: Source, session: requests.Session) -> list[ItemCandidate]:
        list_url = source.config.get("list_url") or "https://lobste.rs/"
        self._top_comments_limit = source.config.get("top_comments_limit")
        response = session.get(list_url, timeout=20)
        if response.status_code >= 400:
            raise AdapterError(f"HTTP {response.status_code}")
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "lxml")
        items = soup.select("li.story") or soup.select("div.story")
        limit = source.config.get("limit")

        candidates: list[ItemCandidate] = []
        for element in items:
            title_el = element.select_one("a.u-url") or element.select_one("a.story_link")
            if title_el is None:
                title_el = element.select_one("a")
            article_href = title_el.get("href") if title_el is not None else None
            if not article_href:
                continue
            article_url = urljoin(list_url, article_href)

            comment_url = None
            for link in element.find_all("a"):
                href = link.get("href") or ""
                if "/s/" in href:
                    comment_url = urljoin(list_url, href)
                    break

            title = title_el.get_text(strip=True) if title_el is not None else None
            canonical = normalize_url(article_url)
            item_key = canonical or article_url
            candidates.append(
                ItemCandidate(
                    item_key=item_key,
                    canonical_url=canonical or article_url,
                    title=title,
                    author=None,
                    published_at=None,
                    summary=None,
                    detail_url=article_url,
                    comment_url=comment_url,
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

    def fetch_comments(
        self,
        candidate: ItemCandidate,
        session: requests.Session,
        limit: int | None = None,
    ) -> tuple[str, int]:
        if not candidate.comment_url:
            return "", 0
        response = session.get(candidate.comment_url, timeout=20)
        if response.status_code >= 400:
            raise AdapterError(f"HTTP {response.status_code}")
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "lxml")
        blocks = soup.select("li.comment") or soup.select(".comment")
        max_count = limit or self._top_comments_limit or 5
        comments: list[tuple[str | None, str | None, str]] = []
        for block in blocks:
            text_el = block.select_one(".comment_text") or block.select_one(".comment-body")
            if text_el is None:
                continue
            body = _comment_text_to_markdown(str(text_el))
            if not body:
                continue
            author_el = block.select_one(".commenter a") or block.select_one(".u-author")
            author = author_el.get_text(strip=True) if author_el is not None else None
            time_el = block.select_one("time")
            timestamp = None
            if time_el is not None:
                timestamp = time_el.get("datetime") or time_el.get_text(strip=True) or None
            comments.append((author, timestamp, body))
            if len(comments) >= max_count:
                break
        return _format_comments(comments), len(comments)
