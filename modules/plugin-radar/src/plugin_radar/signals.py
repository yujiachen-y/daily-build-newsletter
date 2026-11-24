"""Turn snapshots into signals. Pure functions over parsed snapshots; no network.

Every rate is "per day" over the actual time between two observations, so an 18-hour or a
30-hour gap never reads as a day. Every signal that rests on an install counter is checked
against GitHub (stars, repo age) and flagged when the two disagree.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from .storage import parse_iso

# A repo is "suspect" when its install rate dwarfs the attention it gets on GitHub.
SUSPECT_MIN_RATE = 1_000  # installs per day before the star check matters
SUSPECT_MAX_STARS = 100
SUSPECT_RATIO = 20  # installs per day per star
CLUSTER_MIN_SOURCES = 3
CLUSTER_MAX_STARS = 500

RISING_MIN_RATE = 300
RISING_MIN_RATIO = 1.5
WEEKLY_MIN = 3_000
WEEKLY_MIN_RATIO = 1.5
COOLING_TOP = 50
COOLING_MAX_RATIO = 0.5
BREAKOUT_SHARE = 0.25  # last-24h installs as a share of the all-time total

HUB_NEW_DAYS = 14
HUB_FEW_STARS = 10
HUB_MANY_DOWNLOADS = 100_000


def pick_base(
    history: list[dict[str, Any]], now: datetime, days: float, lo: float, hi: float
) -> dict[str, Any] | None:
    """The earlier snapshot closest to `days` before `now`, within [lo, hi] days."""
    best, best_gap = None, None
    for snap in history:
        age = (now - parse_iso(snap["observed_at"])).total_seconds() / 86400
        if lo <= age <= hi:
            gap = abs(age - days)
            if best_gap is None or gap < best_gap:
                best, best_gap = snap, gap
    return best


def elapsed_days(base: dict[str, Any], cur: dict[str, Any]) -> float:
    delta = parse_iso(cur["observed_at"]) - parse_iso(base["observed_at"])
    return delta.total_seconds() / 86400


def base_info(base: dict[str, Any] | None, cur: dict[str, Any]) -> dict[str, Any] | None:
    if not base:
        return None
    return {
        "day": base["day"],
        "observed_at": base["observed_at"],
        "origin": base.get("origin", "live"),
        "days": round(elapsed_days(base, cur), 2),
    }


def suspicion(
    source: str, rate: float, gh: dict[str, dict[str, Any] | None]
) -> tuple[str, list[str]]:
    """("ok" | "suspect" | "unverified", reasons) for a skill's install rate per day."""
    if "/" not in source:
        return "unverified", ["非 GitHub 来源，无法用星数核对"]
    if source.lower() not in gh:
        return "unverified", ["未查 GitHub"]
    repo = gh[source.lower()]
    if repo is None:
        return "unverified", ["GitHub 上找不到该仓库"]
    stars = repo.get("stars") or 0
    if rate >= SUSPECT_MIN_RATE and stars < SUSPECT_MAX_STARS:
        return "suspect", [f"日均安装 {round(rate):,} 次，仓库仅 {stars} 星"]
    if rate >= 5 * SUSPECT_MIN_RATE and rate > SUSPECT_RATIO * max(stars, 1):
        return "suspect", [
            f"日均安装 {round(rate):,} 次，是星数（{stars:,}）的 {rate / stars:.0f} 倍"
        ]
    return "ok", []


def clusters(trending: list[dict[str, Any]], gh: dict[str, Any], top: int = 200) -> dict[str, dict]:
    """Same skill name pushed by several low-star repos at once: a farming pattern."""
    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trending[:top]:
        repo = gh.get(row["source"].lower()) if "/" in row["source"] else None
        stars = (repo or {}).get("stars")
        if "/" in row["source"] and (stars is None or stars < CLUSTER_MAX_STARS):
            by_skill[row["skill"]].append(row)
    out = {}
    for skill, rows in by_skill.items():
        sources = sorted({r["source"] for r in rows})
        if len(sources) >= CLUSTER_MIN_SOURCES:
            out[skill] = {
                "skill": skill,
                "sources": sources,
                "installs_24h": sum(r["installs_24h"] for r in rows),
            }
    return out


def _stars(gh: dict[str, Any], source: str) -> dict[str, Any]:
    repo = gh.get(source.lower()) if "/" in source else None
    return {"stars": (repo or {}).get("stars"), "repo_created": (repo or {}).get("created")}


def week_label(week_end: str | None) -> str | None:
    if not week_end:
        return None
    end = date.fromisoformat(week_end)
    return f"{(end - timedelta(days=6)).isoformat()} 至 {week_end}"


def skillssh(
    cur: dict[str, Any], history: list[dict[str, Any]], gh: dict[str, Any]
) -> dict[str, Any]:
    now = parse_iso(cur["observed_at"])
    base7 = pick_base(history, now, 7, 5, 9.5)
    all_time = cur["all_time"]
    trending = cur.get("trending") or []
    groups = clusters(trending, gh)

    def judge(source: str, skill: str, rate: float) -> tuple[str, list[str]]:
        status, reasons = suspicion(source, rate, gh)
        if skill in groups and source in groups[skill]["sources"]:
            members = len(groups[skill]["sources"])
            reasons = reasons + [f"同名技能 {skill} 由 {members} 个低星仓库同时冲榜"]
            status = "suspect"
        return status, reasons

    trend_rows = []
    for row in trending:
        total = all_time.get(row["id"], {}).get("installs")
        status, reasons = judge(row["source"], row["skill"], row["installs_24h"])
        trend_rows.append(
            {
                **row,
                **_stars(gh, row["source"]),
                "total": total,
                "share_24h": round(row["installs_24h"] / total, 3) if total else None,
                "status": status,
                "reasons": reasons,
            }
        )

    rows = []
    for sid, item in all_time.items():
        weekly = item.get("weekly") or []
        last = weekly[-1] if weekly else None
        prev = weekly[-2] if len(weekly) >= 2 else None
        avg4 = mean(weekly[-5:-1]) if len(weekly) >= 5 else None
        rate = None
        if base7 and sid in base7["all_time"]:
            delta = item["installs"] - base7["all_time"][sid]["installs"]
            if delta >= 0:
                rate = delta / elapsed_days(base7, cur)
        lastweek_rate = last / 7 if last else None
        avg4_rate = avg4 / 7 if avg4 else None
        # Compare with the higher of last week and the four weeks before, so a rebound after
        # one quiet week does not read as a surge.
        base_rate = max(lastweek_rate or 0, avg4_rate or 0) or None
        judged_rate = max(rate or 0, lastweek_rate or 0)
        status, reasons = judge(item["source"], item["skill"], judged_rate)
        rows.append(
            {
                "id": sid,
                "name": item["name"],
                "source": item["source"],
                "skill": item["skill"],
                "rank": item["rank"],
                "total": item["installs"],
                "weekly": weekly,
                "last_week": last,
                "prev_week": prev,
                "avg4": round(avg4) if avg4 is not None else None,
                "rate_recent": round(rate) if rate is not None else None,
                "rate_last_week": round(lastweek_rate) if lastweek_rate else None,
                "rate_avg4": round(avg4_rate) if avg4_rate else None,
                "ratio_recent": round(rate / base_rate, 2) if rate and base_rate else None,
                "ratio_week": round(last / avg4, 2) if last and avg4 else None,
                "streak": _streak(weekly),
                **_stars(gh, item["source"]),
                "status": status,
                "reasons": reasons,
                "url": f"https://skills.sh/{item['source']}/{item['skill']}",
            }
        )

    def clean(r: dict[str, Any]) -> bool:
        return r["status"] == "ok"

    rising = sorted(
        (
            r
            for r in rows
            if clean(r)
            and r["rate_recent"] is not None
            and r["rate_recent"] >= RISING_MIN_RATE
            and (r["ratio_recent"] or 0) >= RISING_MIN_RATIO
        ),
        key=lambda r: r["rate_recent"] - max(r["rate_last_week"] or 0, r["rate_avg4"] or 0),
        reverse=True,
    )
    weekly_up = sorted(
        (
            r
            for r in rows
            if clean(r)
            and (r["last_week"] or 0) >= WEEKLY_MIN
            and (r["ratio_week"] or 0) >= WEEKLY_MIN_RATIO
            and r["last_week"] > (r["prev_week"] or 0)
        ),
        key=lambda r: r["last_week"] - (r["avg4"] or 0),
        reverse=True,
    )
    by_last_week = sorted(rows, key=lambda r: r["last_week"] or 0, reverse=True)[:COOLING_TOP]
    cooling = sorted(
        (r for r in by_last_week if r["ratio_week"] and r["ratio_week"] <= COOLING_MAX_RATIO),
        key=lambda r: (r["avg4"] or 0) - (r["last_week"] or 0),
        reverse=True,
    )
    breakouts = [
        r
        for r in trend_rows
        if r["status"] == "ok"
        and r["rank"] <= 100
        and (r["total"] is None or (r["share_24h"] or 0) >= BREAKOUT_SHARE)
    ]
    suspects = [r for r in trend_rows if r["status"] == "suspect"]
    total_24h = sum(r["installs_24h"] for r in trend_rows)
    suspect_24h = sum(r["installs_24h"] for r in suspects)
    unverified_24h = sum(r["installs_24h"] for r in trend_rows if r["status"] == "unverified")
    return {
        "observed_at": cur["observed_at"],
        "base_7d": base_info(base7, cur),
        "week": week_label(cur.get("week_end")),
        "trending": trend_rows,
        "trending_clean": [r for r in trend_rows if r["status"] == "ok"],
        "breakouts": one_per_source(breakouts),
        "rising": one_per_source(rising),
        "weekly_up": one_per_source(weekly_up),
        "cooling": one_per_source(cooling),
        "suspects": suspects,
        "clusters": sorted(groups.values(), key=lambda g: g["installs_24h"], reverse=True),
        "totals_24h": {
            "rows": len(trend_rows),
            "installs": total_24h,
            "suspect": suspect_24h,
            "unverified": unverified_24h,
            "suspect_share": round(suspect_24h / total_24h, 3) if total_24h else None,
        },
    }


def one_per_source(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the strongest row per repo. `npx skills add owner/repo` installs every skill in the
    repo at once, so sibling skills move together and would otherwise crowd the list."""
    seen: dict[str, dict[str, Any]] = {}
    out = []
    for row in rows:
        if row["source"] in seen:
            seen[row["source"]]["siblings"].append(row["name"])
            continue
        row = {**row, "siblings": []}
        seen[row["source"]] = row
        out.append(row)
    return out


def _streak(weekly: list[int]) -> int:
    """Consecutive week-over-week increases ending at the newest complete week."""
    n = 0
    for a, b in zip(reversed(weekly[:-1]), reversed(weekly)):
        if b > a:
            n += 1
        else:
            break
    return n


def _age_days(created: str | None, now: datetime) -> int | None:
    if not created:
        return None
    return max((now.date() - date.fromisoformat(created)).days, 0)


def hub(
    cur: dict[str, Any], history: list[dict[str, Any]], *, new_days: int = HUB_NEW_DAYS
) -> dict[str, Any]:
    """SkillHub / ClawHub: download movers against an earlier snapshot, plus new fast risers."""
    now = parse_iso(cur["observed_at"])
    base1 = pick_base(history, now, 1, 0.6, 1.6)
    base7 = pick_base(history, now, 7, 5, 9.5)
    base = base7 or base1
    items = cur["items"]
    annotated = {}
    for key, item in items.items():
        age = _age_days(item.get("created"), now)
        flags = []
        if item["downloads"] >= HUB_MANY_DOWNLOADS and item.get("stars", 0) <= HUB_FEW_STARS:
            flags.append(f"下载 {item['downloads']:,} 次但只有 {item.get('stars', 0)} 个收藏/星")
        annotated[key] = {
            **item,
            "age_days": age,
            "per_day_since_created": round(item["downloads"] / max(age, 1))
            if age is not None
            else None,
            "flags": flags,
        }
    movers = []
    if base:
        span = elapsed_days(base, cur)
        for key, item in annotated.items():
            old = (base.get("items") or {}).get(key)
            if not old:
                continue
            delta = item["downloads"] - old["downloads"]
            if delta > 0:
                movers.append({**item, "delta": delta, "per_day": round(delta / span)})
        movers.sort(key=lambda r: r["per_day"], reverse=True)
    new_fast = sorted(
        (
            r
            for r in annotated.values()
            if r["age_days"] is not None and r["age_days"] <= new_days and r["downloads"] > 0
        ),
        key=lambda r: r["per_day_since_created"] or 0,
        reverse=True,
    )
    trending = [
        annotated.get(r["id"], r) | {"rank": r["rank"], "score": r.get("score")}
        for r in cur.get("trending") or []
    ]
    return {
        "observed_at": cur["observed_at"],
        "base": base_info(base, cur),
        "tracked": len(items),
        "total_skills": cur.get("total_skills"),
        "trending": trending,
        "movers": movers,
        "new_fast": new_fast,
        "top": sorted(annotated.values(), key=lambda r: r["downloads"], reverse=True)[:10],
    }


def catalog(cur: dict[str, Any], history: list[dict[str, Any]], gh: dict[str, Any]) -> dict:
    """Listing changes. GitHub catalogs carry their own 7-day window; Kimi diffs snapshots."""
    out = {
        "label": cur.get("label"),
        "observed_at": cur["observed_at"],
        "count": len(cur.get("plugins") or {}),
    }
    if "added" in cur:  # GitHub-backed catalog
        out.update(
            window_days=cur["window_days"],
            window_start=cur["window_start"],
            repo=cur.get("repo"),
            commits_in_window=cur.get("commits_in_window"),
            added=[
                {**a, **(_stars(gh, a["repo"]) if a.get("external") and a.get("repo") else {})}
                for a in cur["added"]
            ],
            removed=cur["removed"],
        )
        return out
    prev = history[-1] if history else None
    if not prev:
        out.update(base=None, added=[], removed=[])
        return out
    now_names, old_names = set(cur["plugins"]), set(prev["plugins"])
    out.update(
        base=base_info(prev, cur),
        added=[{"name": n, **cur["plugins"][n]} for n in sorted(now_names - old_names)],
        removed=[{"name": n} for n in sorted(old_names - now_names)],
    )
    return out


def claude_installs(cur: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    """Movers only when Anthropic regenerated the file since an earlier snapshot."""
    prev = next(
        (h for h in reversed(history) if h.get("generated_at") != cur.get("generated_at")), None
    )
    movers = []
    if prev and prev.get("generated_at") and cur.get("generated_at"):
        span = (parse_iso(cur["generated_at"]) - parse_iso(prev["generated_at"])).total_seconds()
        span_days = span / 86400
        for name, value in cur["installs"].items():
            old = prev["installs"].get(name)
            if old is not None and value > old and span_days > 0:
                movers.append(
                    {
                        "name": name,
                        "installs": value,
                        "delta": value - old,
                        "per_day": round((value - old) / span_days),
                    }
                )
        movers.sort(key=lambda r: r["per_day"], reverse=True)
    top = sorted(cur["installs"].items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        "generated_at": cur.get("generated_at"),
        "age_days": cur.get("age_days"),
        "previous_generated_at": prev.get("generated_at") if prev else None,
        "movers": movers,
        "top": [{"name": n, "installs": v} for n, v in top],
    }
