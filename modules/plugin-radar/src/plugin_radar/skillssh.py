"""skills.sh: the cross-agent skills leaderboard fed by `npx skills` install telemetry.

Two public pages, both server-rendered with the data embedded in the Next.js flight payload:

- `/` (all time): top 600 by deduplicated total installs. Each row also carries
  `weeklyInstalls`, the last 8 *completed* weeks (UTC Monday to Sunday). The array rolls over
  once a week, early on Monday UTC; the cumulative `installs` moves every day.
- `/trending`: top 600 by installs in the last 24 hours (`installs` is the 24h count).

The JSON API (/api/v1/skills) needs a Vercel OIDC token, so the pages are the public route.
Sources without a slash (e.g. `open.feishu.cn`) are "well-known" domains, not GitHub repos.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from .http import FetchError, get_json, get_text
from .storage import Storage, iso, local_day, parse_iso, utc_now, write_json

ALL_TIME_URL = "https://www.skills.sh/"
TRENDING_URL = "https://www.skills.sh/trending"
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
WAYBACK_RAW = "https://web.archive.org/web/{ts}id_/https://skills.sh/"

_FLIGHT_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
_KEY = '"initialSkills":'


def parse_page(html: str) -> list[dict[str, Any]]:
    """Return the leaderboard rows embedded in a skills.sh page."""
    text = "".join(json.loads(f'"{chunk}"') for chunk in _FLIGHT_RE.findall(html))
    start = text.find(_KEY)
    if start < 0:
        raise ValueError("initialSkills not found in skills.sh page")
    rows, _ = json.JSONDecoder().raw_decode(text, start + len(_KEY))
    if not isinstance(rows, list) or not rows:
        raise ValueError("initialSkills is empty")
    return rows


def skill_id(row: dict[str, Any]) -> str:
    return f"{row['source']}/{row['skillId']}"


def is_github(source: str) -> bool:
    return "/" in source


def skill_url(source: str, skill: str) -> str:
    return f"https://skills.sh/{source}/{skill}"


def last_week_end(observed: datetime) -> date:
    """Sunday that closes the newest complete week in weeklyInstalls at this moment."""
    utc_day = observed.astimezone(timezone.utc).date()
    monday = utc_day - timedelta(days=utc_day.weekday())
    return monday - timedelta(days=1)


def all_time_items(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    items = {}
    for rank, row in enumerate(rows, 1):
        items[skill_id(row)] = {
            "rank": rank,
            "name": row.get("name") or row["skillId"],
            "source": row["source"],
            "skill": row["skillId"],
            "installs": int(row["installs"]),
            "weekly": [int(x) for x in row.get("weeklyInstalls") or []],
            "official": bool(row.get("isOfficial")),
        }
    return items


def trending_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "id": skill_id(row),
            "name": row.get("name") or row["skillId"],
            "source": row["source"],
            "skill": row["skillId"],
            "installs_24h": int(row["installs"]),
            "official": bool(row.get("isOfficial")),
        }
        for rank, row in enumerate(rows, 1)
    ]


def fetch(session: requests.Session, storage: Storage, day: str) -> dict[str, Any]:
    observed = utc_now()
    all_html = get_text(session, ALL_TIME_URL)
    trend_html = get_text(session, TRENDING_URL)
    snapshot = {
        "source": "skillssh",
        "day": day,
        "origin": "live",
        "observed_at": iso(observed),
        "week_end": last_week_end(observed).isoformat(),
        "all_time": all_time_items(parse_page(all_html)),
        "trending": trending_items(parse_page(trend_html)),
        "raw": [
            storage.save_raw(day, "skillssh-all-time.html", all_html),
            storage.save_raw(day, "skillssh-trending.html", trend_html),
        ],
    }
    _align_week_end(storage, snapshot)
    return snapshot


def _align_week_end(storage: Storage, snapshot: dict[str, Any]) -> None:
    """weeklyInstalls rolls over a few hours after Monday 00:00 UTC. If the arrays still match
    an earlier snapshot, they still describe that snapshot's week."""
    probe = _probe_weekly(snapshot)
    for earlier in reversed(storage.history("skillssh", snapshot["day"])):
        if _probe_weekly(earlier) == probe and probe:
            snapshot["week_end"] = earlier.get("week_end") or snapshot["week_end"]
            return
        if earlier.get("week_end") and earlier["week_end"] < snapshot["week_end"]:
            return


def _probe_weekly(snapshot: dict[str, Any]) -> list[list[int]]:
    top = sorted(snapshot.get("all_time", {}).values(), key=lambda r: r["rank"])[:5]
    return [r["weekly"] for r in top]


def wayback_candidates(session: requests.Session, since: date) -> list[str]:
    """Wayback timestamps of skills.sh home captures since `since`, latest capture per UTC day."""
    params = {
        "url": "skills.sh/",
        "output": "json",
        "fl": "timestamp",
        "filter": "statuscode:200",
        "from": since.strftime("%Y%m%d"),
    }
    rows = get_json(session, WAYBACK_CDX, params=params, timeout=90)
    by_day: dict[str, str] = {}
    for row in rows[1:] if rows else []:
        ts = row[0]
        by_day[ts[:8]] = max(ts, by_day.get(ts[:8], ""))
    return [by_day[d] for d in sorted(by_day)]


def backfill(
    session: requests.Session, storage: Storage, day: str, *, offsets: tuple[int, ...] = (1, 7)
) -> list[str]:
    """Seed history from the Internet Archive so the first run already has a base.

    For each offset (days before `day`) without a snapshot within one day of it, fetch the
    archived capture closest to that point. Live snapshots are never overwritten.
    """
    target_day = date.fromisoformat(day)
    have = set(storage.snapshot_days("skillssh"))
    wanted = []
    for offset in offsets:
        target = target_day - timedelta(days=offset)
        near = {(target + timedelta(days=d)).isoformat() for d in (-1, 0, 1)}
        if not near & have:
            wanted.append(target)
    if not wanted:
        return []
    captures = wayback_candidates(session, min(wanted) - timedelta(days=2))
    written = []
    for target in wanted:
        ts = _closest(captures, target)
        if not ts:
            continue
        observed = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        snap_day = local_day(observed)
        if snap_day >= day or snap_day in have:
            continue
        try:
            html = get_text(session, WAYBACK_RAW.format(ts=ts), timeout=90)
            items = all_time_items(parse_page(html))
        except (FetchError, ValueError):
            continue
        storage_snapshot = {
            "source": "skillssh",
            "day": snap_day,
            "origin": "wayback",
            "wayback_url": WAYBACK_RAW.format(ts=ts),
            "observed_at": iso(observed),
            "week_end": last_week_end(observed).isoformat(),
            "all_time": items,
            "trending": [],
            "raw": [storage.save_raw(snap_day, f"skillssh-wayback-{ts}.html", html)],
        }
        write_json(storage.snapshot_path("skillssh", snap_day), storage_snapshot)
        have.add(snap_day)
        written.append(snap_day)
    return written


def _closest(captures: list[str], target: date) -> str | None:
    best, best_gap = None, None
    for ts in captures:
        observed = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        gap = abs((observed.date() - target).days)
        if gap <= 2 and (best_gap is None or gap < best_gap):
            best, best_gap = ts, gap
    return best


def observed(snapshot: dict[str, Any]) -> datetime:
    return parse_iso(snapshot["observed_at"])
