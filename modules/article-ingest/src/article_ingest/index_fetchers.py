from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import feedparser
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from .index_fetcher_utils import (
    apply_query,
    decode_devalue_data,
    extract_release_root,
)
from .index_models import (
    IndexComment,
    IndexEntry,
    IndexFetchError,
    IndexFetchResult,
    IndexFetchStats,
    IndexRequestor,
)

HN_TOP_LIMIT = 30
HN_COMMENT_MAX_SECONDS = 30
HN_COMMENT_MAX_REQUESTS = 300
LOBSTERS_LIMIT = 25
DEFAULT_INDEX_LIMIT = 15
RELEASEBOT_LIMIT = 10
MAX_COMMENT_COUNT = 50

_apply_query = apply_query
_decode_devalue_data = decode_devalue_data

def _iso_from_unix(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    try:
        return datetime.fromtimestamp(int(seconds), tz=timezone.utc).isoformat()
    except Exception:
        return None

def _normalize_comment_body(html: str | None) -> str:
    if not html:
        return ""
    markdown = md(html, heading_style="ATX")
    return "\n".join(line.rstrip() for line in markdown.splitlines()).strip()


class _HnCommentBudget:
    def __init__(self, max_seconds: int, max_requests: int) -> None:
        self.max_seconds = max_seconds
        self.max_requests = max_requests
        self.started_at = time.monotonic()
        self.requests = 0

    def exhausted(self) -> bool:
        if self.requests >= self.max_requests:
            return True
        return (time.monotonic() - self.started_at) >= self.max_seconds

    def record_request(self) -> None:
        self.requests += 1


def _collect_hn_comments(
    requestor: IndexRequestor,
    root_ids: list[int] | None,
    max_count: int = MAX_COMMENT_COUNT,
    budget: _HnCommentBudget | None = None,
) -> list[IndexComment]:
    if not root_ids:
        return []
    queue: deque[tuple[int, int]] = deque((comment_id, 0) for comment_id in root_ids)
    comments: list[IndexComment] = []
    while queue and len(comments) < max_count:
        if budget and budget.exhausted():
            break
        comment_id, depth = queue.popleft()
        try:
            if budget:
                if budget.exhausted():
                    break
                budget.record_request()
            item = requestor.get_json(
                f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json"
            )
        except IndexFetchError:
            continue
        if not isinstance(item, dict):
            continue
        if item.get("type") != "comment":
            continue
        is_deleted = bool(item.get("deleted") or item.get("dead"))
        author = item.get("by")
        created_at = _iso_from_unix(item.get("time"))
        text_html = item.get("text") if not is_deleted else None
        body = _normalize_comment_body(text_html) if text_html else "[deleted]"
        comments.append(
            IndexComment(
                depth=depth,
                author=author,
                body=body,
                created_at=created_at,
                is_deleted=is_deleted,
            )
        )
        kids = item.get("kids") or []
        for kid_id in kids:
            if len(comments) + len(queue) >= max_count:
                break
            queue.append((kid_id, depth + 1))
    return comments


def _fetch_hn_entries(requestor: IndexRequestor) -> list[IndexEntry]:
    top_ids = requestor.get_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not isinstance(top_ids, list):
        raise IndexFetchError("HN topstories response invalid")
    comment_budget = _HnCommentBudget(
        max_seconds=HN_COMMENT_MAX_SECONDS,
        max_requests=HN_COMMENT_MAX_REQUESTS,
    )
    entries: list[IndexEntry] = []
    for story_id in top_ids[:HN_TOP_LIMIT]:
        try:
            item = requestor.get_json(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            )
        except IndexFetchError:
            continue
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not title:
            continue
        url = item.get("url")
        external_link_missing = not bool(url)
        if not url:
            url = f"https://news.ycombinator.com/item?id={story_id}"
        comments = _collect_hn_comments(requestor, item.get("kids"), budget=comment_budget)
        entries.append(
            IndexEntry(
                title=title,
                url=url,
                author=item.get("by"),
                published_at=_iso_from_unix(item.get("time")),
                score=item.get("score"),
                comments_count=item.get("descendants"),
                comments=comments,
                external_link_missing=external_link_missing,
            )
        )
    entries.sort(key=lambda entry: entry.comments_count or 0, reverse=True)
    return entries


def _collect_lobsters_comments(comment_data: list[dict[str, Any]]) -> list[IndexComment]:
    comments: list[IndexComment] = []
    for comment in comment_data:
        if len(comments) >= MAX_COMMENT_COUNT:
            break
        depth = int(comment.get("depth") or 0)
        is_deleted = bool(comment.get("is_deleted") or comment.get("is_moderated"))
        author_info = comment.get("commenting_user")
        if isinstance(author_info, dict):
            author = (
                author_info.get("username")
                or author_info.get("user")
                or author_info.get("name")
            )
        elif isinstance(author_info, str):
            author = author_info
        else:
            author = None
        body = comment.get("comment_plain") or comment.get("comment") or ""
        body = body.strip()
        if not body:
            body = "[deleted]" if is_deleted else ""
        created_at = comment.get("created_at")
        comments.append(
            IndexComment(
                depth=depth,
                author=author,
                body=body,
                created_at=created_at,
                is_deleted=is_deleted,
            )
        )
    return comments


def _fetch_lobsters_entries(requestor: IndexRequestor) -> list[IndexEntry]:
    feed = feedparser.parse("https://lobste.rs/rss")
    if feed.bozo:
        raise IndexFetchError("Lobsters RSS parse error")
    entries: list[IndexEntry] = []
    for entry in feed.entries[:LOBSTERS_LIMIT]:
        title = entry.get("title")
        if not title:
            continue
        comments_url = entry.get("comments") or entry.get("id")
        if not comments_url:
            continue
        story_json_url = f"{comments_url}.json"
        try:
            story_data = requestor.get_json(story_json_url)
        except IndexFetchError:
            story_data = None
        comment_count = None
        score = None
        author = None
        published_at = entry.get("published")
        comments: list[IndexComment] = []
        if isinstance(story_data, dict):
            comment_count = story_data.get("comment_count")
            score = story_data.get("score")
            published_at = story_data.get("created_at") or published_at
            submitter = story_data.get("submitter_user")
            if isinstance(submitter, dict):
                author = submitter.get("username") or submitter.get("user") or submitter.get("name")
            elif isinstance(submitter, str):
                author = submitter
            comments = _collect_lobsters_comments(story_data.get("comments") or [])
        link = entry.get("link") or comments_url
        external_link_missing = link == comments_url
        entries.append(
            IndexEntry(
                title=title,
                url=link,
                author=author,
                published_at=published_at,
                score=score,
                comments_count=comment_count,
                comments=comments,
                external_link_missing=external_link_missing,
            )
        )
    entries.sort(key=lambda entry: entry.comments_count or 0, reverse=True)
    return entries


def _fetch_releasebot_entries(requestor: IndexRequestor) -> list[IndexEntry]:
    data_url = "https://releasebot.io/updates/__data.json"
    payload = requestor.get_json(data_url)
    if not isinstance(payload, dict):
        raise IndexFetchError("Releasebot payload invalid")
    root = extract_release_root(payload)
    releases = root.get("releases") or []
    entries: list[IndexEntry] = []
    for release in releases[:RELEASEBOT_LIMIT]:
        product = release.get("product") or {}
        vendor = product.get("vendor") or {}
        product_name = product.get("display_name") or vendor.get("display_name")
        release_details = release.get("release_details") or {}
        release_summary = release_details.get("release_summary")
        formatted_content = release.get("formatted_content")
        release_name = (
            release_details.get("release_name")
            or release_details.get("release_number")
            or release.get("slug")
            or "Release"
        )
        title = f"{product_name} — {release_name}" if product_name else str(release_name)
        source_url = None
        source = release.get("source")
        if isinstance(source, dict):
            source_url = source.get("source_url")
        if not source_url:
            vendor_slug = vendor.get("slug") or "vendor"
            product_slug = product.get("slug") or "product"
            source_url = f"https://releasebot.io/updates/{vendor_slug}/{product_slug}"
        published_at = release.get("release_date") or release.get("created_at")
        entries.append(
            IndexEntry(
                title=title,
                url=source_url,
                published_at=published_at,
                summary=release_summary,
                details=formatted_content,
            )
        )
    entries.sort(key=lambda entry: entry.published_at or "", reverse=True)
    return entries


def _fetch_hf_papers_entries(requestor: IndexRequestor) -> list[IndexEntry]:
    data = requestor.get_json("https://huggingface.co/api/daily_papers")
    if not isinstance(data, list):
        raise IndexFetchError("HF papers payload invalid")
    entries: list[IndexEntry] = []
    for item in data[:DEFAULT_INDEX_LIMIT]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        paper = item.get("paper") or {}
        if not title:
            title = paper.get("title")
        if not title:
            continue
        paper_id = paper.get("id")
        url = None
        if paper_id:
            url = f"https://huggingface.co/papers/{paper_id}"
        if not url:
            url = paper.get("projectPage") or paper.get("project_page")
        if not url:
            continue
        authors = paper.get("authors") or []
        author = None
        if authors:
            author = authors[0].get("name") if isinstance(authors[0], dict) else None
        entries.append(
            IndexEntry(
                title=title,
                url=url,
                author=author,
                published_at=item.get("publishedAt") or paper.get("publishedAt"),
                score=paper.get("upvotes"),
                comments_count=item.get("numComments"),
            )
        )
    return entries


def _parse_github_trending_html(html: str) -> list[IndexEntry]:
    soup = BeautifulSoup(html, "lxml")
    entries: list[IndexEntry] = []
    for article in soup.select("article.Box-row"):
        link_el = article.select_one("h2 a")
        if link_el is None:
            continue
        repo_text = " ".join(link_el.get_text(strip=True).split())
        repo_path = link_el.get("href")
        if not repo_path:
            continue
        url = f"https://github.com{repo_path}"
        stars_today_el = article.select_one("span.d-inline-block.float-sm-right")
        stars_today = None
        if stars_today_el:
            text = stars_today_el.get_text(strip=True).lower().replace("stars today", "").strip()
            try:
                stars_today = int(text.replace(",", ""))
            except ValueError:
                stars_today = None
        entries.append(IndexEntry(title=repo_text, url=url, score=stars_today))
    return entries


def _fetch_github_trending_html(requestor: IndexRequestor) -> list[IndexEntry]:
    html = requestor.get_text("https://github.com/trending")
    entries = _parse_github_trending_html(html)
    if not entries:
        raise IndexFetchError("github_trending html parse empty")
    return entries

def _fetch_github_trending_rss(requestor: IndexRequestor) -> list[IndexEntry]:
    feed = feedparser.parse(
        requestor.get_bytes("https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml")
    )
    if feed.bozo:
        raise IndexFetchError("github_trending rss parse error")
    entries: list[IndexEntry] = []
    for entry in feed.entries[:DEFAULT_INDEX_LIMIT]:
        title = entry.get("title")
        link = entry.get("link")
        if not title or not link:
            continue
        entries.append(IndexEntry(title=title, url=link))
    if not entries:
        raise IndexFetchError("github_trending rss empty")
    return entries


def _fetch_github_trending_community(requestor: IndexRequestor) -> list[IndexEntry]:
    data = requestor.get_json("https://github-trending-api.now.sh/repositories")
    if isinstance(data, dict):
        data = data.get("items") or data.get("repositories") or []
    entries: list[IndexEntry] = []
    if isinstance(data, list):
        for repo in data[:DEFAULT_INDEX_LIMIT]:
            if not isinstance(repo, dict):
                continue
            title = repo.get("name") or repo.get("repo")
            url = repo.get("url")
            score = repo.get("currentPeriodStars") or repo.get("starsToday")
            if title and url:
                entries.append(IndexEntry(title=title, url=url, score=score))
    if not entries:
        raise IndexFetchError("github_trending community api empty")
    return entries


def _fetch_github_trending_search(requestor: IndexRequestor) -> list[IndexEntry]:
    since = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    query = apply_query(
        "https://api.github.com/search/repositories",
        {
            "q": f"created:>{since}",
            "sort": "stars",
            "order": "desc",
            "per_page": DEFAULT_INDEX_LIMIT,
        },
    )
    payload = requestor.get_json(query)
    entries: list[IndexEntry] = []
    if isinstance(payload, dict):
        for item in payload.get("items", [])[:DEFAULT_INDEX_LIMIT]:
            if not isinstance(item, dict):
                continue
            title = item.get("full_name")
            url = item.get("html_url")
            score = item.get("stargazers_count")
            if title and url:
                entries.append(IndexEntry(title=title, url=url, score=score))
    if not entries:
        raise IndexFetchError("github_trending search empty")
    return entries


def _fetch_github_trending_entries(requestor: IndexRequestor) -> list[IndexEntry]:
    errors: list[str] = []
    for fetcher in (
        _fetch_github_trending_html,
        _fetch_github_trending_rss,
        _fetch_github_trending_community,
        _fetch_github_trending_search,
    ):
        try:
            return fetcher(requestor)
        except IndexFetchError as exc:
            errors.append(str(exc))
    requestor.errors.extend(errors)
    return []


def _fetch_product_hunt_entries(requestor: IndexRequestor) -> list[IndexEntry]:
    feed = feedparser.parse(requestor.get_bytes("https://www.producthunt.com/feed"))
    if feed.bozo:
        raise IndexFetchError("Product Hunt RSS parse error")
    entries: list[IndexEntry] = []
    for entry in feed.entries[:DEFAULT_INDEX_LIMIT]:
        title = entry.get("title")
        link = entry.get("link")
        if not title or not link:
            continue
        summary = entry.get("summary") or entry.get("description")
        tags = []
        for tag in entry.get("tags") or []:
            if isinstance(tag, dict) and tag.get("term"):
                tags.append(tag["term"])
        entries.append(
            IndexEntry(
                title=title,
                url=link,
                published_at=entry.get("published"),
                summary=summary,
                tags=tags,
            )
        )
    return entries


FETCHERS: dict[str, Callable[[IndexRequestor], list[IndexEntry]]] = {
    "hn": _fetch_hn_entries,
    "lobsters": _fetch_lobsters_entries,
    "releasebot": _fetch_releasebot_entries,
    "hf-papers": _fetch_hf_papers_entries,
    "github-trending": _fetch_github_trending_entries,
    "product-hunt-rss": _fetch_product_hunt_entries,
}


def fetch_index_entries(slug: str) -> IndexFetchResult:
    if slug not in FETCHERS:
        raise IndexFetchError(f"Unknown index source: {slug}")
    requestor = IndexRequestor()
    errors: list[str] = []
    start = time.monotonic()
    entries: list[IndexEntry] = []
    try:
        entries = FETCHERS[slug](requestor)
    except IndexFetchError as exc:
        errors.append(str(exc))
    duration_ms = int((time.monotonic() - start) * 1000)
    errors.extend(requestor.errors)
    stats = IndexFetchStats(
        requests=requestor.requests,
        errors=len(errors),
        duration_ms=duration_ms,
    )
    return IndexFetchResult(entries=entries, stats=stats, errors=errors)
