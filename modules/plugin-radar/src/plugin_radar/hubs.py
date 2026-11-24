"""Skill hubs with public JSON APIs and per-skill counters.

SkillHub (skillhub.cn, Tencent): the community behind the "SkillHub" tab of WorkBuddy's skill
market. `downloads` is cumulative; `stars` are SkillHub favourites. The showcase "trending"
list (100 rows) is SkillHub's own recent-surge ranking with an opaque `score`.

ClawHub (clawhub.ai): OpenClaw's skill registry. `downloads` and `installs` are cumulative;
`stars` are ClawHub stars. Only `sort=downloads` and `sort=newest` change the order.

WorkBuddy's own in-client counters (使用量 / 安装量 on the 推荐 and 套件 tabs) need the desktop
client and a login, so they are not here; see the README.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests

from .http import get_json
from .storage import Storage, iso, utc_now

SKILLHUB_TRENDING = "https://api.skillhub.cn/api/v1/showcase/trending"
SKILLHUB_LIST = "https://api.skillhub.cn/api/skills"
CLAWHUB_LIST = "https://clawhub.ai/api/v1/skills"


def _ms_date(ms: Any) -> str | None:
    if not isinstance(ms, (int, float)) or ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def _short(text: Any, limit: int = 90) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def skillhub_item(row: dict[str, Any]) -> dict[str, Any]:
    ns = row.get("namespace") or {}
    handle = ns.get("handle") or row.get("ownerName") or "?"
    slug = ns.get("publicSlug") or row.get("slug") or "?"
    publisher = row.get("publisher") or {}
    return {
        "id": f"{handle}/{slug}",
        "name": row.get("name") or slug,
        "downloads": int(row.get("downloads") or 0),
        "stars": int(row.get("stars") or 0),
        "created": _ms_date(row.get("created_at")),
        "updated": _ms_date(row.get("updated_at")),
        "kind": row.get("source"),
        "publisher": publisher.get("certifiedName") or publisher.get("name"),
        "category": row.get("category"),
        "summary": _short(row.get("description_zh") or row.get("description")),
        "upstream": row.get("upstream_url"),
        "url": f"https://skillhub.cn/skills/{handle}/{slug}",
    }


def fetch_skillhub(session: requests.Session, storage: Storage, day: str) -> dict[str, Any]:
    observed = utc_now()
    trending_raw = get_json(session, SKILLHUB_TRENDING)
    trending = []
    for rank, row in enumerate(trending_raw.get("skills") or [], 1):
        item = skillhub_item(row)
        item["rank"] = rank
        item["score"] = round(float(row.get("score") or 0), 1)
        trending.append(item)
    if not trending:
        raise ValueError("SkillHub trending list is empty")
    top: dict[str, dict[str, Any]] = {}
    total = None
    for page in (1, 2):
        params = {"page": page, "pageSize": 100, "sortBy": "downloads", "order": "desc"}
        data = (get_json(session, SKILLHUB_LIST, params=params) or {}).get("data") or {}
        total = data.get("total", total)
        for row in data.get("skills") or []:
            item = skillhub_item(row)
            top[item["id"]] = item
    if not top:
        raise ValueError("SkillHub download ranking is empty")
    counters = {i["id"]: i for i in trending}
    counters.update(top)
    return {
        "source": "skillhub",
        "day": day,
        "origin": "live",
        "observed_at": iso(observed),
        "total_skills": total,
        "trending": trending,
        "items": counters,
        "raw": [storage.save_raw(day, "skillhub-trending.json", _dump(trending_raw))],
    }


def clawhub_item(row: dict[str, Any]) -> dict[str, Any]:
    stats = row.get("stats") or {}
    owner = row.get("ownerHandle") or "?"
    slug = row.get("slug") or "?"
    return {
        "id": f"{owner}/{slug}",
        "name": row.get("displayName") or slug,
        "downloads": int(stats.get("downloads") or 0),
        "installs": int(stats.get("installs") or 0),
        "stars": int(stats.get("stars") or 0),
        "created": _ms_date(row.get("createdAt")),
        "updated": _ms_date(row.get("updatedAt")),
        "summary": _short(row.get("summary")),
        "url": f"https://clawhub.ai/{owner}/skills/{slug}",
    }


def fetch_clawhub(
    session: requests.Session, storage: Storage, day: str, *, pages: int = 2
) -> dict[str, Any]:
    observed = utc_now()
    items: dict[str, dict[str, Any]] = {}
    cursor = None
    raw_pages = []
    for _ in range(pages):
        params: dict[str, Any] = {"limit": 200, "sort": "downloads"}
        if cursor:
            params["cursor"] = cursor
        data = get_json(session, CLAWHUB_LIST, params=params) or {}
        raw_pages.append(data)
        for row in data.get("items") or []:
            item = clawhub_item(row)
            item["rank"] = len(items) + 1
            items[item["id"]] = item
        cursor = data.get("nextCursor")
        if not cursor:
            break
    if not items:
        raise ValueError("ClawHub download ranking is empty")
    return {
        "source": "clawhub",
        "day": day,
        "origin": "live",
        "observed_at": iso(observed),
        "items": items,
        "raw": [storage.save_raw(day, "clawhub-downloads.json", _dump(raw_pages))],
    }


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)
