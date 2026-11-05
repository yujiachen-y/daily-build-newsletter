"""Chinese attention indices through DataXAPI (paid, per call).

WeChat Index, Douyin's 巨量算数 index and Xiaohongshu's 蒲公英 search index have no official
API. DataXAPI resells them per call. Endpoints and response shapes follow the docs at
https://dataxapi.com/apis/ (read 2026-11-05); the response structure is marked "preview" there,
so parsing is defensive. WeChat only returns the last 30 days, so history only exists if we
keep fetching and store it here.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from .http import FetchError, request_json
from .storage import Storage, read_json, write_json

API = "https://api.dataxapi.com/v1"
PRICES = {"wechat": 0.1, "douyin": 0.006, "xiaohongshu": 0.04}  # USD per call, 2026-11-05
METRICS = {"wechat": "composite_index", "douyin": "search_index", "xiaohongshu": "search_index"}
DOUYIN_BATCH = 5


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    config.setdefault("platforms", list(PRICES))
    config.setdefault("min_interval_days", 7)
    return config


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    if isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data.get("item"), dict):  # the Xiaohongshu endpoint returns one object
        return [data["item"]]
    return []


def parse_points(item: dict[str, Any], metric: str) -> list[dict[str, Any]]:
    points = []
    for point in item.get("points") or []:
        day = (point.get("date") or "")[:10]
        if day:
            points.append({"date": day, "value": point.get(metric)})
    return points


def merge_series(existing: dict[str, Any] | None, points: list[dict[str, Any]]) -> list[dict]:
    """Newer fetches win for the same date: the platforms publish a day or two late and fill
    earlier nulls in later."""
    merged = {p["date"]: p for p in (existing or {}).get("points", [])}
    for point in points:
        if point["value"] is not None or point["date"] not in merged:
            merged[point["date"]] = point
    return [merged[d] for d in sorted(merged)]


def _due(storage: Storage, platform: str, keyword: str, now: datetime, interval: int) -> bool:
    existing = read_json(storage.index_path(platform, keyword))
    if not existing or not existing.get("fetched_at"):
        return True
    last = datetime.fromisoformat(existing["fetched_at"])
    return now - last >= timedelta(days=interval) - timedelta(hours=6)


def _store(storage: Storage, platform: str, keyword: str, points: list[dict], now: str) -> None:
    path = storage.index_path(platform, keyword)
    write_json(
        path,
        {
            "platform": platform,
            "keyword": keyword,
            "metric": METRICS[platform],
            "fetched_at": now,
            "points": merge_series(read_json(path), points),
        },
    )


def fetch_indices(
    session: requests.Session,
    storage: Storage,
    api_key: str,
    config: dict[str, Any],
    *,
    force: bool = False,
    pause: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    headers = {"Authorization": f"Bearer {api_key}"}
    interval = int(config["min_interval_days"])
    calls = {p: 0 for p in PRICES}
    failures: list[dict[str, str]] = []
    skipped = 0

    for platform in config["platforms"]:
        due = [k for k in config["keywords"] if force or _due(storage, platform, k, now, interval)]
        skipped += len(config["keywords"]) - len(due)
        if platform == "douyin":
            batches = [due[i : i + DOUYIN_BATCH] for i in range(0, len(due), DOUYIN_BATCH)]
        else:
            batches = [[k] for k in due]
        for batch in batches:
            try:
                payload = _call(session, platform, batch, headers, now.date(), sleep)
            except FetchError as exc:
                failures.append(
                    {"platform": platform, "keywords": ",".join(batch), "error": str(exc)}
                )
                if any(f"HTTP {code}" in str(exc) for code in (401, 402, 403)):
                    # Bad key, no balance or suspended account: every further call fails too.
                    return _summary(calls, skipped, failures, aborted=True)
                continue
            finally:
                calls[platform] += 1
                sleep(pause)
            returned = {(i.get("keyword") or "").lower(): i for i in _items(payload)}
            for keyword in batch:
                item = returned.get(keyword.lower())
                # A keyword the platform does not index comes back empty; store that too so
                # it is not re-fetched (and re-charged) before the interval is up.
                points = parse_points(item, METRICS[platform]) if item else []
                _store(storage, platform, keyword, points, stamp)

    return _summary(calls, skipped, failures, aborted=False)


def _summary(
    calls: dict[str, int], skipped: int, failures: list[dict[str, str]], *, aborted: bool
) -> dict[str, Any]:
    # Failed calls are not charged, so this is an upper bound.
    cost = sum(PRICES[p] * n for p, n in calls.items())
    return {
        "calls": calls,
        "max_cost_usd": round(cost, 3),
        "skipped_not_due": skipped,
        "failures": failures,
        "aborted": aborted,
    }


def _call(
    session: requests.Session,
    platform: str,
    keywords: list[str],
    headers: dict[str, str],
    today: date,
    sleep: Callable[[float], None],
) -> dict[str, Any]:
    if platform == "wechat":
        return request_json(
            session,
            "GET",
            f"{API}/wechat/index/keywords/history",
            params={"keyword": keywords[0]},
            headers=headers,
            sleep=sleep,
        )
    if platform == "xiaohongshu":
        return request_json(
            session,
            "GET",
            f"{API}/xiaohongshu/pgy/keywords/history",
            params={"keyword": keywords[0]},
            headers=headers,
            sleep=sleep,
        )
    if platform == "douyin":
        body = {
            "keywords": keywords,
            "since": f"{today - timedelta(days=30)}T00:00:00Z",
            "until": f"{today}T00:00:00Z",
        }
        return request_json(
            session,
            "POST",
            f"{API}/douyin/index/keywords/history",
            json=body,
            headers=headers,
            sleep=sleep,
        )
    raise FetchError(f"unknown platform {platform}")


def load_series(storage: Storage) -> list[dict[str, Any]]:
    folder = storage.root / "indices"
    if not folder.exists():
        return []
    return [read_json(p) for p in sorted(folder.glob("*/*.json"))]
