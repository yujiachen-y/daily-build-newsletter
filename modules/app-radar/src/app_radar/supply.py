"""Supply stage of a niche: how many look-alike apps launched lately, against a baseline.

The back-test (docs/research/2026-11-05-trend-signal-backtest.md) found that the time from a
niche's first winner to its clone wave (10+ look-alike launches in a quarter) shrank from 20
months (short dramas, 2022) to 11 (GLP-1 trackers, 2024) and 5 (quit-porn apps, 2025). The
stage tells whether copying a template into a niche, or into another country, is still early.

Counts come from the iTunes search API: at most 200 apps per term and country, matched on app
names. Removed apps are missing and renamed apps keep their original release date, so counts
are compared with a baseline of evergreen niche utilities searched the same way.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

import requests

from .history import SEARCH_LIMIT, app_search, match_apps
from .http import FetchError
from .storage import Storage, read_json, write_json

STAGES = {
    "empty": "几乎没人做",
    "scattered": "零星，无近两年的赢家",
    "winner": "有赢家、未扎堆",
    "crowded": "已扎堆",
    "unknown": "搜索结果触顶，数不准",
}
QUARTER_DAYS = 91
HALF_DAYS = 182
CLONE_MIN = 10  # look-alike launches in the last quarter that count as a clone wave
WINNER_DAYS = 730
WINNER_MIN_RATINGS = {"us": 1000}
DEFAULT_WINNER_MIN_RATINGS = 300
ACCELERATING = 2.0  # half-year growth against the baseline's that flags a niche as speeding up
MAX_AGE_DAYS = 7  # reuse a theme or watch search for this long
BASELINE_MAX_AGE_DAYS = 28  # baseline terms move slowly; 70 searches take about 7 minutes
LATIN_MARKETS = ("us", "gb", "de", "fr")  # English app names travel across these storefronts
THEME_LIMIT = 10
CJK_BIGRAM = re.compile(r"^[぀-ヿ一-鿿]{2}$")
TRAILING_PARTICLES = "でのをにはがともへや"  # ビデオ通話で → ビデオ通話


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --- queries ---------------------------------------------------------------------------------


def chain_bigrams(tokens: Iterable[str]) -> list[str]:
    """Rebuild phrases from CJK bigrams that overlap by one character.

    The name tokenizer cuts ビデオ通話 into ビデ/デオ/オ通/通話; this joins them back.
    """
    bigrams = sorted(set(tokens))
    following = {a: [b for b in bigrams if b != a and b[0] == a[1]] for a in bigrams}
    has_previous = {b for nexts in following.values() for b in nexts}
    starts = [t for t in bigrams if t not in has_previous] or bigrams[:1]
    chains = []
    for start in starts:
        chain, current, seen = start, start, {start}
        while following[current] and following[current][0] not in seen:
            current = following[current][0]
            seen.add(current)
            chain += current[1]
        if len(chain) > 3:
            chain = chain.rstrip(TRAILING_PARTICLES)
        chains.append(chain)
    return sorted(chains, key=lambda c: (-len(c), c))


def theme_query(theme: dict[str, Any]) -> dict[str, Any] | None:
    """Search term, name pattern and storefronts for one chart theme."""
    tokens = theme["tokens"]
    cjk = [t for t in tokens if CJK_BIGRAM.match(t)]
    words = [t for t in tokens if t not in cjk]
    if cjk:
        term = chain_bigrams(cjk)[0]
        pattern = re.escape(term)
    elif words:
        picked = words[:2]
        term = " ".join(picked)
        pattern = "".join(rf"(?=.*\b{re.escape(w)}\b)" for w in picked)
    else:
        return None
    countries = list(theme["countries"])
    if term.isascii():
        countries += [c for c in LATIN_MARKETS if c not in countries]
    return {
        "kind": "theme",
        "key": " / ".join(tokens[:4]),
        "label": term,
        "countries": {c: {"terms": [term], "pattern": pattern} for c in countries},
    }


def watch_queries(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "kind": "watch",
            "key": item["id"],
            "label": item["label"],
            "countries": item["countries"],
        }
        for item in config.get("watch", [])
    ]


# --- measuring -------------------------------------------------------------------------------


def _age(day: str, released: str) -> int:
    return (date.fromisoformat(day) - date.fromisoformat(released[:10])).days


def window_counts(apps: Iterable[dict[str, Any]], day: str) -> dict[str, int]:
    """Launches in the last quarter, the last half year and the half year before."""
    counts = {"quarter": 0, "half": 0, "prior_half": 0}
    for app in apps:
        age = _age(day, app["release_date"])
        if 0 <= age < QUARTER_DAYS:
            counts["quarter"] += 1
        if 0 <= age < HALF_DAYS:
            counts["half"] += 1
        elif HALF_DAYS <= age < 2 * HALF_DAYS:
            counts["prior_half"] += 1
    return counts


def growth_ratio(counts: dict[str, int], baseline: dict[str, int] | None) -> float | None:
    """Half-year growth of a niche divided by the baseline's growth over the same windows."""
    if not baseline or not baseline.get("half") or not baseline.get("prior_half"):
        return None
    niche = counts["half"] / max(counts["prior_half"], 1)
    base = baseline["half"] / baseline["prior_half"]
    return round(niche / base, 2)


def _slim(app: dict[str, Any] | None) -> dict[str, Any] | None:
    if not app:
        return None
    return {k: app.get(k) for k in ("app_id", "name", "seller", "release_date", "ratings")}


def measure(
    rows: list[dict[str, Any]],
    pattern: str,
    day: str,
    country: str,
    baseline: dict[str, int] | None,
    *,
    capped: bool = False,
) -> dict[str, Any]:
    """Stage of one niche in one storefront.

    `capped` means no search term returned a complete list (every term hit the 200 limit).
    """
    apps = match_apps(rows, pattern)
    counts = window_counts(apps, day)
    recent = [a for a in apps if 0 <= _age(day, a["release_date"]) <= WINNER_DAYS]
    winner = max(recent, key=lambda a: a["ratings"], default=None)
    top = max(apps, key=lambda a: a["ratings"], default=None)
    min_ratings = WINNER_MIN_RATINGS.get(country, DEFAULT_WINNER_MIN_RATINGS)
    if len(apps) < 3 and not capped:
        stage = "empty"
    elif counts["quarter"] >= CLONE_MIN:
        stage = "crowded"  # a lower bound, so it holds even when the results are capped
    elif capped:
        # Relevance ranking fills capped results with older apps, so recent launches are
        # undercounted and "not crowded" cannot be told apart from "not counted".
        stage = "unknown"
    elif winner and winner["ratings"] >= min_ratings:
        stage = "winner"
    else:
        stage = "scattered"
    # Capped counts are undercounts, so their growth says nothing either.
    growth = None if stage == "unknown" else growth_ratio(counts, baseline)
    return {
        "matched": len(apps),
        "capped": capped,
        **counts,
        "growth_vs_baseline": growth,
        "accelerating": bool(growth and growth >= ACCELERATING and counts["half"] >= 5),
        "winner": _slim(winner),
        "winner_min_ratings": min_ratings,
        "top": _slim(top),
        "stage": stage,
    }


# --- fetching --------------------------------------------------------------------------------


class Searcher:
    """iTunes search with a per-term cache under data/supply/search/."""

    def __init__(
        self,
        session: requests.Session,
        storage: Storage,
        day: str,
        *,
        pause: float = 3.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session
        self.storage = storage
        self.day = day
        self.pause = pause
        self.sleep = sleep
        self.requests = 0
        self.failures: list[dict[str, str]] = []

    def rows(
        self, terms: list[str], country: str, max_age: int = MAX_AGE_DAYS
    ) -> tuple[list[dict[str, Any]], bool] | None:
        """Results of all terms, and whether every term hit the result limit."""
        found: list[dict[str, Any]] = []
        capped = True
        for term in terms:
            result = self._search(term, country, max_age)
            if result is None:
                return None
            found.extend(result)
            capped = capped and len(result) >= SEARCH_LIMIT - 10
        return found, capped

    def _search(self, term: str, country: str, max_age: int) -> list[dict[str, Any]] | None:
        path = self.storage.supply_search_path(country, term)
        cached = read_json(path)
        if cached and 0 <= _age(self.day, cached["fetched"]) < max_age:
            return cached["rows"]
        try:
            rows = app_search(self.session, term, country, sleep=self.sleep)
        except FetchError as exc:
            self.failures.append({"country": country, "term": term, "error": str(exc)[:300]})
            return None
        finally:
            self.requests += 1
            self.sleep(self.pause)
        write_json(path, {"fetched": self.day, "term": term, "country": country, "rows": rows})
        return rows


def baseline_counts(
    config: dict[str, Any], searcher: Searcher, countries: Iterable[str]
) -> dict[str, dict[str, int]]:
    out = {}
    for country in countries:
        totals = {"quarter": 0, "half": 0, "prior_half": 0}
        for item in config.get("baseline", {}).get(country, []):
            rows, _ = searcher.rows([item["term"]], country, BASELINE_MAX_AGE_DAYS) or ([], False)
            for key, value in window_counts(
                match_apps(rows, item["pattern"]), searcher.day
            ).items():
                totals[key] += value
        if any(totals.values()):
            out[country] = totals
    return out


def run_supply(
    session: requests.Session,
    storage: Storage,
    day: str,
    themes: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    pause: float = 3.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    started = time.time()
    searcher = Searcher(session, storage, day, pause=pause, sleep=sleep)
    queries = [q for q in (theme_query(t) for t in themes[:THEME_LIMIT]) if q]
    queries += watch_queries(config)
    countries = sorted({c for q in queries for c in q["countries"]})
    baseline = baseline_counts(config, searcher, countries)
    items = []
    for query in queries:
        per_country = {}
        for country, spec in query["countries"].items():
            found = searcher.rows(spec["terms"], country)
            if found is None:
                per_country[country] = {"error": True, "terms": spec["terms"]}
                continue
            rows, capped = found
            per_country[country] = {
                "terms": spec["terms"],
                **measure(
                    rows, spec["pattern"], day, country, baseline.get(country), capped=capped
                ),
            }
        items.append({k: query[k] for k in ("kind", "key", "label")} | {"countries": per_country})
    result = {
        "day": day,
        "baseline": baseline,
        "items": items,
        "requests": searcher.requests,
        "failures": searcher.failures,
        "seconds": round(time.time() - started, 1),
    }
    write_json(storage.supply_path(day), result)
    return result
