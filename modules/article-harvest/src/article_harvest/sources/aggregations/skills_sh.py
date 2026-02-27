from __future__ import annotations

import json

from ...errors import FetchError
from ...http import get_text
from ...models import AggregationItem, FetchContext, Source

SKILLS_SH_TRENDING_URL = "https://skills.sh/trending"
SKILLS_SH_HOT_URL = "https://skills.sh/hot"
SKILLS_SH_LIMIT = 30


def source_trending() -> Source:
    return Source(
        id="skills-sh-trending",
        name="Skills.sh Trending (24h)",
        kind="aggregation",
        method="html",
        fetch=fetch_trending,
    )


def source_hot() -> Source:
    return Source(
        id="skills-sh-hot",
        name="Skills.sh Hot",
        kind="aggregation",
        method="html",
        fetch=fetch_hot,
    )


def _extract_skills(html: str) -> list[dict[str, object]]:
    """Extract the initialSkills JSON array from Next.js RSC payload."""
    idx = html.find("initialSkills")
    if idx < 0:
        raise FetchError("skills.sh: initialSkills not found in page")

    chunk = html[idx : idx + 200_000]
    # Unescape double-escaped JSON from RSC payload
    chunk = chunk.replace('\\"', '"')

    arr_start = chunk.find("[")
    if arr_start < 0:
        raise FetchError("skills.sh: no JSON array after initialSkills")

    depth = 0
    end_pos = -1
    for i, c in enumerate(chunk[arr_start:], arr_start):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break

    if end_pos < 0:
        raise FetchError("skills.sh: unclosed JSON array")

    raw = chunk[arr_start:end_pos]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FetchError(f"skills.sh: JSON parse error: {exc}") from exc


def _skill_url(skill: dict[str, object]) -> str:
    source = skill.get("source", "")
    skill_id = skill.get("skillId", "")
    return f"https://skills.sh/{source}/{skill_id}"


def fetch_trending(ctx: FetchContext) -> list[AggregationItem]:
    html = get_text(ctx.session, SKILLS_SH_TRENDING_URL)
    skills = _extract_skills(html)
    if not skills:
        raise FetchError("skills.sh trending list empty")

    items: list[AggregationItem] = []
    for rank, skill in enumerate(skills[:SKILLS_SH_LIMIT], start=1):
        name = skill.get("name")
        if not name:
            continue
        items.append(
            AggregationItem(
                title=str(name),
                url=_skill_url(skill),
                author=str(skill.get("source", "")).split("/")[0] or None,
                score=skill.get("installs") if isinstance(skill.get("installs"), int) else None,
                rank=rank,
                extra={
                    "source_repo": str(skill.get("source", "")),
                    "skill_id": str(skill.get("skillId", "")),
                },
            )
        )
    if not items:
        raise FetchError("skills.sh trending entries empty")
    return items


def fetch_hot(ctx: FetchContext) -> list[AggregationItem]:
    html = get_text(ctx.session, SKILLS_SH_HOT_URL)
    skills = _extract_skills(html)
    if not skills:
        raise FetchError("skills.sh hot list empty")

    items: list[AggregationItem] = []
    for rank, skill in enumerate(skills[:SKILLS_SH_LIMIT], start=1):
        name = skill.get("name")
        if not name:
            continue
        change = skill.get("change")
        installs = skill.get("installs")
        installs_yesterday = skill.get("installsYesterday")
        items.append(
            AggregationItem(
                title=str(name),
                url=_skill_url(skill),
                author=str(skill.get("source", "")).split("/")[0] or None,
                score=installs if isinstance(installs, int) else None,
                rank=rank,
                extra={
                    "source_repo": str(skill.get("source", "")),
                    "skill_id": str(skill.get("skillId", "")),
                    "change": change if isinstance(change, int) else None,
                    "installs_yesterday": (
                        installs_yesterday if isinstance(installs_yesterday, int) else None
                    ),
                },
            )
        )
    if not items:
        raise FetchError("skills.sh hot entries empty")
    return items
