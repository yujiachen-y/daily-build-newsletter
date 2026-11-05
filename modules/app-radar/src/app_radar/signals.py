"""Turn chart and lookup snapshots into signals.

Every number here is computed mechanically so the newsletter writer never has to count or
sort by hand. Signals that need history say how much history they had.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any, Iterable

from .apple import age_days

GROSSING = "topgrossingapplications"
FREE = "topfreeapplications"

ChartKey = tuple[str, str, str]

STOPWORDS = {
    # English and the European languages in the default country list
    "a",
    "an",
    "and",
    "app",
    "apps",
    "best",
    "by",
    "de",
    "der",
    "des",
    "die",
    "das",
    "du",
    "en",
    "et",
    "for",
    "free",
    "für",
    "in",
    "la",
    "le",
    "les",
    "lite",
    "mit",
    "my",
    "new",
    "of",
    "on",
    "one",
    "plus",
    "pro",
    "the",
    "to",
    "und",
    "with",
    "your",
    "von",
    "pour",
    "avec",
    "votre",
    "mon",
    "ma",
}
LATIN_WORD = re.compile(r"[a-z0-9]+(?:['’][a-z]+)?")
HANGUL_WORD = re.compile(r"[가-힣]{2,}")
CJK_RUN = re.compile(r"[぀-ヿ一-鿿]{2,}")


def chart_key(row: dict[str, Any]) -> ChartKey:
    return (row["country"], row["genre"], row["chart"])


def tokenize_name(name: str | None) -> set[str]:
    if not name:
        return set()
    lower = name.lower()
    tokens = {w for w in LATIN_WORD.findall(lower) if len(w) >= 2 and w not in STOPWORDS}
    tokens.update(HANGUL_WORD.findall(name))
    for run in CJK_RUN.findall(name):
        tokens.update(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _index_lookups(lookups: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["country"], row["app_id"]): row for row in lookups}


def first_release_dates(
    rows: Iterable[dict[str, Any]], lookups: Iterable[dict[str, Any]]
) -> dict[str, str]:
    """Earliest release date of each app across all storefronts seen today.

    Storefronts report their own release dates; an app that launched in the US two years ago
    and in France last month is a new market entry, not a new product.
    """
    earliest: dict[str, str] = {}
    for row in list(rows) + list(lookups):
        released = row.get("release_date")
        if not released:
            continue
        current = earliest.get(row["app_id"])
        if current is None or released < current:
            earliest[row["app_id"]] = released
    return earliest


def young_apps(
    day: str,
    rows: list[dict[str, Any]],
    lookups: list[dict[str, Any]],
    *,
    young_days: int,
) -> list[dict[str, Any]]:
    """Young apps in today's charts, with placements and rating counts per storefront."""
    released = first_release_dates(rows, lookups)
    by_lookup = _index_lookups(lookups)
    # A young app from a seller that already has older apps charting (Tencent, TikTok, ...) is
    # an incumbent's launch, not a newcomer copying a template.
    incumbents = {
        row["artist"]
        for row in rows
        if (age_days(day, released.get(row["app_id"])) or 0) > young_days
    }
    apps: dict[str, dict[str, Any]] = {}
    for row in rows:
        age = age_days(day, released.get(row["app_id"]))
        if age is None or age > young_days:
            continue
        app = apps.setdefault(
            row["app_id"],
            {
                "app_id": row["app_id"],
                "name": row["name"],
                "seller": row["artist"],
                "seller_has_older_app": row["artist"] in incumbents,
                "first_release": released[row["app_id"]],
                "age_days": age,
                "grossing": [],
                "free": [],
            },
        )
        placement = {"country": row["country"], "genre": row["genre"], "rank": row["rank"]}
        app["grossing" if row["chart"] == GROSSING else "free"].append(placement)
    for app in apps.values():
        app["grossing"].sort(key=lambda p: p["rank"])
        app["free"].sort(key=lambda p: p["rank"])
        app["best_grossing"] = app["grossing"][0]["rank"] if app["grossing"] else None
        app["best_free"] = app["free"][0]["rank"] if app["free"] else None
        countries = sorted({p["country"] for p in app["grossing"] + app["free"]})
        app["countries"] = countries
        app["ratings"] = {}
        app["ratings_per_day"] = {}
        for country in countries:
            looked = by_lookup.get((country, app["app_id"]))
            if not looked or looked.get("ratings") is None:
                continue
            app["ratings"][country] = looked["ratings"]
            local_age = age_days(day, looked.get("release_date")) or app["age_days"]
            app["ratings_per_day"][country] = round(looked["ratings"] / max(local_age, 1), 1)
            app.setdefault("description_head", looked.get("description_head"))
            app.setdefault("url", looked.get("url"))
            app.setdefault("languages", len(looked.get("languages") or []))
    return sorted(
        apps.values(),
        key=lambda a: (
            a["best_grossing"] or 999,
            a["best_free"] or 999,
            -len(a["countries"]),
        ),
    )


def themes(
    day: str,
    rows: list[dict[str, Any]],
    lookups: list[dict[str, Any]],
    *,
    young_days: int,
    min_sellers: int = 3,
    min_young_share: float = 0.5,
) -> list[dict[str, Any]]:
    """Name tokens shared by several young apps from different sellers.

    A token also common among established apps ("tracker", "健康") is a category word, not a
    theme, so a token must be mostly young apps to count.
    """
    released = first_release_dates(rows, lookups)
    young: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    old: dict[str, set[str]] = defaultdict(set)
    names: dict[str, str] = {}
    for row in rows:
        age = age_days(day, released.get(row["app_id"]))
        names.setdefault(row["app_id"], row["name"] or "")
        for token in tokenize_name(row["name"]):
            if age is not None and age <= young_days:
                bucket = young[token]
                bucket["apps"].add(row["app_id"])
                bucket["sellers"].add(row["artist"] or row["app_id"])
                bucket["countries"].add(row["country"])
                bucket["genres"].add(row["genre"])
            else:
                old[token].add(row["app_id"])
    best_grossing: dict[str, int] = {}
    for row in rows:
        if row["chart"] == GROSSING:
            best_grossing[row["app_id"]] = min(row["rank"], best_grossing.get(row["app_id"], 999))
    candidates = []
    for token, bucket in young.items():
        n_young, n_old = len(bucket["apps"]), len(old.get(token, ()))
        if len(bucket["sellers"]) < min_sellers or n_young / (n_young + n_old) < min_young_share:
            continue
        candidates.append((token, bucket, old.get(token, set())))
    return [
        {
            "tokens": cluster["tokens"],
            "young_apps": len(cluster["apps"]),
            "established_apps": len(cluster["old"]),
            "sellers": len(cluster["sellers"]),
            "countries": sorted(cluster["countries"]),
            "genres": sorted(cluster["genres"]),
            "examples": sorted(names[a] for a in cluster["apps"])[:6],
            "in_grossing": sum(1 for a in cluster["apps"] if a in best_grossing),
            "best_grossing": min(
                (best_grossing[a] for a in cluster["apps"] if a in best_grossing), default=None
            ),
        }
        for cluster in _cluster_tokens(candidates)
    ]


def _cluster_tokens(
    candidates: list[tuple[str, dict[str, set[str]], set[str]]], *, min_overlap: float = 0.5
) -> list[dict[str, Any]]:
    """Merge tokens that mostly name the same apps.

    Chinese names are split into character bigrams, so one cluster of apps ("AI拍照算热量饮食记录")
    yields 拍照 / 饮食 / 食记 as separate tokens; they are one theme.
    """
    clusters: list[dict[str, Any]] = []
    for token, bucket, old_apps in sorted(candidates, key=lambda c: (-len(c[1]["apps"]), c[0])):
        apps = bucket["apps"]
        for cluster in clusters:
            overlap = len(apps & cluster["apps"]) / len(apps | cluster["apps"])
            if overlap >= min_overlap:
                cluster["tokens"].append(token)
                for field in ("apps", "sellers", "countries", "genres"):
                    cluster[field] |= bucket[field]
                cluster["old"] |= old_apps
                break
        else:
            clusters.append(
                {"tokens": [token], "old": set(old_apps)}
                | {
                    field: set(bucket[field])
                    for field in ("apps", "sellers", "countries", "genres")
                }
            )
    return sorted(clusters, key=lambda c: (-len(c["apps"]), c["tokens"][0]))


def _ranks_by_chart(rows: Iterable[dict[str, Any]]) -> dict[ChartKey, dict[str, int]]:
    ranks: dict[ChartKey, dict[str, int]] = defaultdict(dict)
    for row in rows:
        ranks[chart_key(row)][row["app_id"]] = row["rank"]
    return ranks


def pick_base_day(day: str, history_days: list[str], window: int) -> str | None:
    """Earliest snapshot within the last `window` days, so a change spans as many days as we
    have, up to a week."""
    today = date.fromisoformat(day)
    candidates = [d for d in history_days if 0 < (today - date.fromisoformat(d)).days <= window]
    return min(candidates) if candidates else None


def chart_moves(
    day: str,
    rows: list[dict[str, Any]],
    base_rows: list[dict[str, Any]],
    all_history_rows: list[dict[str, Any]],
    *,
    history_span_days: int,
    min_climb: int = 20,
    first_seen_min_span: int = 7,
) -> dict[str, list[dict[str, Any]]]:
    """Rank changes against the base snapshot, only for charts present on both days."""
    today, base = _ranks_by_chart(rows), _ranks_by_chart(base_rows)
    ever_seen: dict[ChartKey, set[str]] = defaultdict(set)
    for row in all_history_rows:
        ever_seen[chart_key(row)].add(row["app_id"])
    names = {row["app_id"]: row["name"] for row in rows + base_rows}
    climbers, entered, dropped = [], [], []
    for key in sorted(set(today) & set(base)):
        country, genre, chart = key
        for app_id, rank in today[key].items():
            before = base[key].get(app_id)
            item = {
                "app_id": app_id,
                "name": names.get(app_id),
                "country": country,
                "genre": genre,
                "chart": chart,
                "rank": rank,
                "base_rank": before,
            }
            if before is None:
                item["first_seen"] = (
                    history_span_days >= first_seen_min_span and app_id not in ever_seen[key]
                )
                entered.append(item)
            elif before - rank >= min_climb:
                item["climb"] = before - rank
                climbers.append(item)
        for app_id, before in base[key].items():
            if app_id not in today[key]:
                dropped.append(
                    {
                        "app_id": app_id,
                        "name": names.get(app_id),
                        "country": country,
                        "genre": genre,
                        "chart": chart,
                        "base_rank": before,
                    }
                )
    climbers.sort(key=lambda m: (-m["climb"], m["rank"]))
    entered.sort(key=lambda m: m["rank"])
    dropped.sort(key=lambda m: m["base_rank"])
    return {"climbers": climbers, "entered": entered, "dropped": dropped}


def rating_growth(
    day: str,
    base_day: str,
    lookups: list[dict[str, Any]],
    base_lookups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    span = (date.fromisoformat(day) - date.fromisoformat(base_day)).days
    before = _index_lookups(base_lookups)
    growth = []
    for row in lookups:
        old = before.get((row["country"], row["app_id"]))
        if not old or row.get("ratings") is None or old.get("ratings") is None:
            continue
        delta = row["ratings"] - old["ratings"]
        if delta <= 0:
            continue
        age = age_days(day, row.get("release_date")) or 1
        lifetime = row["ratings"] / max(age, 1)
        recent = delta / span
        growth.append(
            {
                "app_id": row["app_id"],
                "name": row["name"],
                "country": row["country"],
                "ratings": row["ratings"],
                "delta": delta,
                "span_days": span,
                "per_day_recent": round(recent, 1),
                "per_day_lifetime": round(lifetime, 1),
                "acceleration": round(recent / lifetime, 2) if lifetime else None,
            }
        )
    return sorted(growth, key=lambda g: -g["per_day_recent"])


def index_changes(series: list[dict[str, Any]], *, window: int = 7) -> list[dict[str, Any]]:
    """Last `window` days against the `window` before, per keyword and platform."""
    changes = []
    for item in series:
        points = [p for p in item["points"] if p.get("value") is not None]
        values = [p["value"] for p in points]
        if len(values) < window * 2:
            continue
        recent = sum(values[-window:]) / window
        previous = sum(values[-2 * window : -window]) / window
        change = (recent - previous) / previous if previous else None
        changes.append(
            {
                "platform": item["platform"],
                "keyword": item["keyword"],
                "metric": item["metric"],
                "last_date": points[-1]["date"],
                "recent_avg": round(recent),
                "previous_avg": round(previous),
                "change": round(change, 3) if change is not None else None,
            }
        )
    return sorted(changes, key=lambda c: -(c["change"] or 0))
