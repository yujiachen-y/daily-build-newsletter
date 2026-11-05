"""Apple App Store charts (legacy iTunes RSS) and the iTunes lookup API.

The newer rss.marketingtools.apple.com feed dropped top-grossing (it returns 502), so charts
come from the legacy itunes.apple.com RSS, which still serves per-country, per-genre charts
capped at 100 entries.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any, Callable, Iterable

import requests

from .http import FetchError, request_json
from .storage import Storage, read_jsonl, write_json, write_jsonl

COUNTRIES = {
    "us": "美国",
    "gb": "英国",
    "de": "德国",
    "fr": "法国",
    "jp": "日本",
    "kr": "韩国",
    "cn": "中国",
}

# Non-game genres where subscription apps live. Games are left out on purpose: they dominate
# grossing charts and are not the copy-a-template playbook this module watches.
GENRES = {
    "6013": "健康健美",
    "6012": "生活",
    "6007": "效率",
    "6017": "教育",
    "6008": "摄影与录像",
    "6002": "工具",
    "6016": "娱乐",
}

CHARTS = {
    "topgrossingapplications": "畅销榜",
    "topfreeapplications": "免费榜",
}

RSS_LIMIT = 100  # the legacy feed returns at most 100 entries whatever limit is asked for
LOOKUP_BATCH = 100
DESCRIPTION_HEAD = 160


def rss_url(country: str, chart: str, genre: str) -> str:
    return f"https://itunes.apple.com/{country}/rss/{chart}/limit={RSS_LIMIT}/genre={genre}/json"


def lookup_url(country: str, app_ids: Iterable[str]) -> str:
    return f"https://itunes.apple.com/lookup?id={','.join(app_ids)}&country={country}"


def _label(entry: dict[str, Any], key: str) -> str | None:
    value = entry.get(key)
    if isinstance(value, dict):
        return value.get("label")
    return None


def parse_rss(data: dict[str, Any], country: str, genre: str, chart: str) -> list[dict[str, Any]]:
    entries = data.get("feed", {}).get("entry", [])
    if isinstance(entries, dict):  # a feed with one entry is not wrapped in a list
        entries = [entries]
    rows = []
    for rank, entry in enumerate(entries, start=1):
        id_attrs = entry.get("id", {}).get("attributes", {})
        app_id = id_attrs.get("im:id")
        if not app_id:
            continue
        release = _label(entry, "im:releaseDate") or ""
        rows.append(
            {
                "country": country,
                "genre": genre,
                "chart": chart,
                "rank": rank,
                "app_id": str(app_id),
                "bundle_id": id_attrs.get("im:bundleId"),
                "name": _label(entry, "im:name"),
                "artist": _label(entry, "im:artist"),
                "release_date": release[:10] or None,
                "url": entry.get("id", {}).get("label"),
            }
        )
    return rows


def _description_head(text: str | None) -> str | None:
    if not text:
        return None
    flat = re.sub(r"\s+", " ", text).strip()
    return flat[:DESCRIPTION_HEAD]


def parse_lookup(data: dict[str, Any], country: str) -> list[dict[str, Any]]:
    rows = []
    for item in data.get("results", []):
        if item.get("wrapperType") not in (None, "software"):
            continue
        rows.append(
            {
                "country": country,
                "app_id": str(item.get("trackId")),
                "name": item.get("trackName"),
                "seller": item.get("sellerName") or item.get("artistName"),
                "ratings": item.get("userRatingCount"),
                "rating_avg": item.get("averageUserRating"),
                "release_date": (item.get("releaseDate") or "")[:10] or None,
                "version_date": (item.get("currentVersionReleaseDate") or "")[:10] or None,
                "price": item.get("price"),
                "currency": item.get("currency"),
                "genre": item.get("primaryGenreName"),
                "languages": item.get("languageCodesISO2A") or [],
                "url": item.get("trackViewUrl"),
                "description_head": _description_head(item.get("description")),
            }
        )
    return rows


def age_days(day: str, release_date: str | None) -> int | None:
    if not release_date:
        return None
    try:
        return (date.fromisoformat(day) - date.fromisoformat(release_date)).days
    except ValueError:
        return None


def lookup_targets(
    rows: Iterable[dict[str, Any]], day: str, young_days: int
) -> dict[str, list[str]]:
    """Young apps per country: the only ones whose rating counts we track."""
    targets: dict[str, set[str]] = {}
    for row in rows:
        age = age_days(day, row.get("release_date"))
        if age is not None and age <= young_days:
            targets.setdefault(row["country"], set()).add(row["app_id"])
    return {country: sorted(ids) for country, ids in targets.items()}


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def fetch_day(
    session: requests.Session,
    storage: Storage,
    day: str,
    *,
    countries: Iterable[str] = COUNTRIES,
    genres: Iterable[str] = GENRES,
    charts: Iterable[str] = CHARTS,
    young_days: int = 365,
    history_days: int = 7,
    rss_pause: float = 0.3,
    lookup_pause: float = 1.5,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    started = time.time()
    countries, genres, charts = list(countries), list(genres), list(charts)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for country in countries:
        for genre in genres:
            for chart in charts:
                url = rss_url(country, chart, genre)
                try:
                    data = request_json(session, "GET", url, sleep=sleep)
                    rows.extend(parse_rss(data, country, genre, chart))
                except FetchError as exc:
                    failures.append({"kind": "chart", "url": url, "error": str(exc)})
                sleep(rss_pause)
    if not rows:
        # An empty file would read as "every app left the charts" in tomorrow's diff.
        raise FetchError(f"no chart rows fetched for {day}: {failures[:1]}")
    write_jsonl(storage.charts_path(day), rows)

    # Keep tracking apps that were young and charting during the past week, so a drop out of
    # the chart still leaves a rating-count trail.
    recent = [d for d in storage.chart_days() if d < day][-history_days:]
    history_rows = [r for d in recent for r in read_jsonl(storage.charts_path(d))]
    targets = lookup_targets(rows + history_rows, day, young_days)
    lookups: list[dict[str, Any]] = []
    for country in countries:
        for batch in _chunks(targets.get(country, []), LOOKUP_BATCH):
            url = lookup_url(country, batch)
            try:
                lookups.extend(
                    parse_lookup(request_json(session, "GET", url, sleep=sleep), country)
                )
            except FetchError as exc:
                failures.append({"kind": "lookup", "url": url, "error": str(exc)})
            sleep(lookup_pause)
    write_jsonl(storage.lookups_path(day), lookups)

    run = {
        "day": day,
        "countries": countries,
        "genres": genres,
        "charts": charts,
        "chart_rows": len(rows),
        "chart_requests": len(countries) * len(genres) * len(charts),
        "lookup_rows": len(lookups),
        "lookup_targets": sum(len(v) for v in targets.values()),
        "failures": failures,
        "seconds": round(time.time() - started, 1),
    }
    write_json(storage.run_path(day), run)
    return run
