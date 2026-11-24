from __future__ import annotations

import json
from typing import Any


def flight_page(rows: list[dict[str, Any]]) -> str:
    """A minimal page in the shape skills.sh serves: data inside self.__next_f.push strings."""
    payload = '5:["$","$L1",null,{"initialSkills":' + json.dumps(rows) + ',"total":600}]\n'
    half = len(payload) // 2
    chunks = [payload[:half], payload[half:]]
    scripts = "".join(
        f"<script>self.__next_f.push([1,{json.dumps(chunk)}])</script>" for chunk in chunks
    )
    return f"<html><body>{scripts}</body></html>"


def all_time_row(source: str, skill: str, installs: int, weekly: list[int]) -> dict[str, Any]:
    return {
        "source": source,
        "skillId": skill,
        "name": skill,
        "installs": installs,
        "weeklyInstalls": weekly,
    }


def skillssh_snapshot(
    day: str,
    observed_at: str,
    all_time: dict[str, tuple[int, list[int]]],
    trending: list[tuple[str, int]] | None = None,
    origin: str = "live",
) -> dict[str, Any]:
    items = {}
    for rank, (sid, (installs, weekly)) in enumerate(all_time.items(), 1):
        source, skill = sid.rsplit("/", 1)
        items[sid] = {
            "rank": rank,
            "name": skill,
            "source": source,
            "skill": skill,
            "installs": installs,
            "weekly": weekly,
            "official": False,
        }
    trend = []
    for rank, (sid, n) in enumerate(trending or [], 1):
        source, skill = sid.rsplit("/", 1)
        trend.append(
            {
                "rank": rank,
                "id": sid,
                "name": skill,
                "source": source,
                "skill": skill,
                "installs_24h": n,
                "official": False,
            }
        )
    return {
        "source": "skillssh",
        "day": day,
        "origin": origin,
        "observed_at": observed_at,
        "week_end": "2026-11-15",
        "all_time": items,
        "trending": trend,
        "raw": [],
    }


def hub_snapshot(day: str, observed_at: str, items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    full = {}
    for key, extra in items.items():
        full[key] = {
            "id": key,
            "name": key.split("/")[-1],
            "downloads": 0,
            "stars": 0,
            "created": None,
            "summary": "",
            "url": f"https://example.com/{key}",
            **extra,
        }
    return {
        "source": "skillhub",
        "day": day,
        "origin": "live",
        "observed_at": observed_at,
        "items": full,
        "trending": [],
        "raw": [],
    }
