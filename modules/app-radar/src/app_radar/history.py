"""Monthly history series for back-testing trend signals.

- Wikipedia pageviews per article (Wikimedia pageviews API, data from 2015-07, no key).
- Hacker News stories per month matching a query (Algolia HN search, no key).
- GitHub repositories created per month matching a query (search API; a token raises the
  limit from 10 to 30 requests a minute).
- App Store search results with release dates and rating counts (iTunes search API, at most
  200 results per term and country, ranked by relevance; removed apps are missing).
"""

from __future__ import annotations

import calendar
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import quote

import requests

from .http import request_json

WIKI_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "{project}/all-access/user/{article}/monthly/{start}/{end}"
)
HN_URL = "https://hn.algolia.com/api/v1/search"
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
SEARCH_LIMIT = 200

Sleep = Callable[[float], None]


def month_range(start: str, end: str) -> list[str]:
    """Months from start to end inclusive, both as YYYY-MM."""
    year, month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    months = []
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def month_days(month: str) -> tuple[str, str]:
    year, mon = map(int, month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    return f"{month}-01", f"{month}-{last:02d}"


def month_epochs(month: str) -> tuple[int, int]:
    """[start, next month's start) as Unix seconds, UTC."""
    year, mon = map(int, month.split("-"))
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    next_year, next_mon = (year + 1, 1) if mon == 12 else (year, mon + 1)
    end = datetime(next_year, next_mon, 1, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def wiki_monthly(
    session: requests.Session, spec: str, months: list[str], *, sleep: Sleep = time.sleep
) -> dict[str, int]:
    """Monthly user pageviews for "project:Article"; {} when the article does not exist."""
    project, article = spec.split(":", 1)
    first, _ = month_days(months[0])
    _, last = month_days(months[-1])
    url = WIKI_URL.format(
        project=project,
        article=quote(article.replace(" ", "_"), safe=""),
        start=first.replace("-", "") + "00",
        end=last.replace("-", "") + "00",
    )
    data = request_json(session, "GET", url, sleep=sleep, missing_ok=True)
    if not data:
        return {}
    series = {}
    for item in data.get("items", []):
        stamp = item["timestamp"]
        series[f"{stamp[:4]}-{stamp[4:6]}"] = int(item["views"])
    return series


def hn_monthly(
    session: requests.Session,
    query: str,
    months: Iterable[str],
    *,
    pause: float = 0.2,
    sleep: Sleep = time.sleep,
) -> dict[str, int]:
    series = {}
    for month in months:
        start, end = month_epochs(month)
        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": 0,
            # With typo tolerance on, "ozempic" matches "olympic" and "chatgpt" "chatbot".
            "typoTolerance": "false",
            "numericFilters": f"created_at_i>={start},created_at_i<{end}",
        }
        data = request_json(session, "GET", HN_URL, params=params, sleep=sleep)
        series[month] = int(data.get("nbHits") or 0)
        sleep(pause)
    return series


def github_monthly(
    session: requests.Session,
    query: str,
    months: Iterable[str],
    token: str | None,
    *,
    pause: float = 2.2,
    sleep: Sleep = time.sleep,
) -> dict[str, int]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    series = {}
    for month in months:
        first, last = month_days(month)
        params = {"q": f"{query} created:{first}..{last}", "per_page": 1}
        data = request_json(
            session, "GET", GITHUB_SEARCH_URL, params=params, headers=headers, sleep=sleep
        )
        series[month] = int(data.get("total_count") or 0)
        sleep(pause)
    return series


def app_search(
    session: requests.Session, term: str, country: str, *, sleep: Sleep = time.sleep
) -> list[dict[str, Any]]:
    params = {"term": term, "country": country, "entity": "software", "limit": SEARCH_LIMIT}
    data = request_json(session, "GET", ITUNES_SEARCH_URL, params=params, sleep=sleep)
    rows = []
    for item in data.get("results", []):
        rows.append(
            {
                "app_id": str(item.get("trackId")),
                "name": item.get("trackName") or "",
                "seller": item.get("sellerName") or item.get("artistName"),
                "release_date": (item.get("releaseDate") or "")[:10] or None,
                "ratings": int(item.get("userRatingCount") or 0),
                "genre": item.get("primaryGenreName"),
                "country": country,
                "term": term,
            }
        )
    return rows


def match_apps(rows: Iterable[dict[str, Any]], pattern: str) -> list[dict[str, Any]]:
    """Apps whose name matches `pattern`, one row per app id, oldest release first."""
    regex = re.compile(pattern, re.IGNORECASE)
    apps: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("release_date") and regex.search(row.get("name") or ""):
            apps.setdefault(row["app_id"], row)
    return sorted(apps.values(), key=lambda r: r["release_date"])
