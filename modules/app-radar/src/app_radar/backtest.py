"""Back-test trend signals against past app waves.

For each wave in config/backtest.json this lines up when attention rose (Wikipedia pageviews,
Hacker News stories, GitHub repositories) against when the App Store supply moved (the first
app that reached a rating threshold, the first quarter with many look-alike releases). A
control basket of health and lifestyle topics, chosen before looking at their data, estimates
how often an attention onset is followed by an app-supply surge at all, and how often a surge
had an onset before it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import requests

from .history import (
    SEARCH_LIMIT,
    app_search,
    github_monthly,
    hn_monthly,
    match_apps,
    month_range,
    wiki_monthly,
)
from .http import FetchError
from .storage import Storage, read_json, write_json

FLOORS = {"wiki": 3000, "wiki_other": 500, "hn": 3, "github": 20}
PIVOT_MONTHS = 24  # big apps released this long before the first onset are not the wave's own
HORIZON_YEARS = 2


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --- series metrics -------------------------------------------------------------------------


def window_mean(series: dict[str, int], months: list[str], end: int, window: int) -> float:
    """Mean over the `window` months ending at index `end`; missing months count as 0."""
    span = months[max(0, end - window + 1) : end + 1]
    return sum(series.get(m, 0) for m in span) / window


def onsets(
    series: dict[str, int],
    months: list[str],
    *,
    floor: float,
    window: int = 3,
    ratio: float = 2.0,
    lookback: int = 12,
    gap: int = 12,
) -> list[str]:
    """Months where the trailing mean reached `floor` and doubled year over year.

    Comparing with the same months a year earlier keeps seasonal spikes (January diets,
    November challenges) from counting. After an onset the next one needs `gap` months.
    """
    found: list[str] = []
    last = -gap
    for i in range(lookback + window - 1, len(months)):
        if i - last < gap:
            continue
        current = window_mean(series, months, i, window)
        before = window_mean(series, months, i - lookback, window)
        if current >= floor and current >= ratio * before:
            found.append(months[i])
            last = i
    return found


def rolling_peak(
    series: dict[str, int], months: list[str], window: int = 3
) -> tuple[str, float] | None:
    best: tuple[str, float] | None = None
    for i in range(window - 1, len(months)):
        value = window_mean(series, months, i, window)
        if value > 0 and (best is None or value > best[1]):
            best = (months[i], value)
    return best


def halved_after_peak(series: dict[str, int], months: list[str], window: int = 3) -> str | None:
    peak = rolling_peak(series, months, window)
    if not peak:
        return None
    for i in range(months.index(peak[0]) + 1, len(months)):
        if window_mean(series, months, i, window) <= peak[1] / 2:
            return months[i]
    return None


def month_index(value: str) -> int:
    """'YYYY-MM', 'YYYY-MM-DD' or 'YYYY-Qn' as a month count (quarters use their first month)."""
    year = int(value[:4])
    if value[5] == "Q":
        return year * 12 + (int(value[6]) - 1) * 3
    return year * 12 + int(value[5:7]) - 1


def months_between(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    return month_index(end) - month_index(start)


def shift_month(month: str, delta: int) -> str:
    index = month_index(month) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


# --- app supply -----------------------------------------------------------------------------


def first_winner(
    apps: list[dict[str, Any]], min_ratings: int, cutoff: str | None
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Earliest app with at least `min_ratings` released on or after `cutoff`.

    Big apps released before the cutoff come back separately: they are usually older apps
    renamed into the trend, or incumbents from an earlier wave.
    """
    big = [a for a in apps if a["ratings"] >= min_ratings]
    if not cutoff:
        return (big[0] if big else None), []
    early = [a for a in big if a["release_date"] < cutoff]
    later = [a for a in big if a["release_date"] >= cutoff]
    return (later[0] if later else None), early


def period(day: str, by: str) -> str:
    if by == "year":
        return day[:4]
    return f"{day[:4]}-Q{(int(day[5:7]) - 1) // 3 + 1}"


def release_counts(apps: Iterable[dict[str, Any]], by: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for app in apps:
        key = period(app["release_date"], by)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def clone_wave(quarter_counts: dict[str, int], min_count: int) -> str | None:
    for quarter, count in sorted(quarter_counts.items()):
        if count >= min_count:
            return quarter
    return None


def surge_years(
    year_counts: dict[str, int],
    baseline: dict[str, int],
    years: Iterable[int],
    *,
    min_count: int = 5,
    ratio: float = 2.0,
) -> list[int]:
    """Years whose releases, scaled by the baseline's releases that year, at least doubled
    against the mean of the two years before. The baseline absorbs App Store-wide growth and
    the search API's lean towards recent apps."""

    def scaled(year: int) -> float:
        base = baseline.get(str(year), 0)
        return year_counts.get(str(year), 0) / base if base else 0.0

    surges = []
    for year in years:
        if year_counts.get(str(year), 0) < min_count:
            continue
        before = (scaled(year - 1) + scaled(year - 2)) / 2
        if scaled(year) >= ratio * before:
            surges.append(year)
    return surges


def hit_stats(
    onset_months: list[str], surges: list[int], *, last_year: int, horizon: int = HORIZON_YEARS
) -> dict[str, Any]:
    """Onsets followed by a surge within `horizon` years, and surges with an onset before.

    Only onsets whose whole horizon is observed (year + horizon <= last_year) are scored.
    """
    years = [int(m[:4]) for m in onset_months]
    scored = [y for y in years if y + horizon <= last_year]
    hits = [y for y in scored if any(y <= s <= y + horizon for s in surges)]
    preceded = [s for s in surges if any(s - horizon <= y <= s for y in years)]
    return {
        "onsets": len(onset_months),
        "scored": len(scored),
        "hits": len(hits),
        "surges": len(surges),
        "preceded": len(preceded),
    }


# --- fetching with a disk cache -------------------------------------------------------------


class Fetcher:
    """Fetches series once and caches them under data/backtest/raw/."""

    def __init__(
        self,
        session: requests.Session,
        storage: Storage,
        months: list[str],
        github_months: list[str],
        *,
        refresh: bool = False,
        github_token: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = print,
    ) -> None:
        self.session = session
        self.storage = storage
        self.months = months
        self.github_months = github_months
        self.refresh = refresh
        self.github_token = github_token
        self.sleep = sleep
        self.log = log
        self.failures: list[dict[str, str]] = []

    def wiki(self, spec: str) -> dict[str, int] | None:
        return self._cached(
            "wiki",
            spec,
            self.months,
            lambda: wiki_monthly(self.session, spec, self.months, sleep=self.sleep),
            pause=0.5,
        )

    def hn(self, query: str) -> dict[str, int] | None:
        return self._cached(
            "hn",
            query,
            self.months,
            lambda: hn_monthly(self.session, query, self.months, sleep=self.sleep),
        )

    def github(self, query: str) -> dict[str, int] | None:
        return self._cached(
            "github",
            query,
            self.github_months,
            lambda: github_monthly(
                self.session, query, self.github_months, self.github_token, sleep=self.sleep
            ),
        )

    def apps(self, term: str, country: str) -> list[dict[str, Any]] | None:
        return self._cached(
            "apps",
            f"{country}_{term}",
            None,
            lambda: app_search(self.session, term, country, sleep=self.sleep),
            pause=3.0,
        )

    def _cached(
        self,
        kind: str,
        key: str,
        months: list[str] | None,
        fetch: Callable[[], Any],
        pause: float = 0.0,
    ) -> Any:
        path = self.storage.backtest_raw_path(kind, key)
        span = [months[0], months[-1]] if months else None
        cached = read_json(path)
        if cached is not None and not self.refresh and cached.get("span") == span:
            return cached["data"]
        self.log(f"fetch {kind}: {key}")
        try:
            data = fetch()
        except FetchError as exc:
            self.failures.append({"kind": kind, "key": key, "error": str(exc)[:300]})
            return None
        write_json(path, {"key": key, "span": span, "data": data})
        self.sleep(pause)
        return data


# --- measuring ------------------------------------------------------------------------------


def measure_signal(
    kind: str, key: str, series: dict[str, int] | None, months: list[str], floor: float
) -> dict[str, Any]:
    if series is None:
        return {"kind": kind, "key": key, "error": True}
    found = onsets(series, months, floor=floor)
    peak = rolling_peak(series, months)
    return {
        "kind": kind,
        "key": key,
        "first_month": min(series) if series else None,
        "onsets": found,
        "onset": found[0] if found else None,
        "peak_month": peak[0] if peak else None,
        "peak_mean": round(peak[1]) if peak else None,
        "halved": halved_after_peak(series, months),
    }


def wiki_floor(spec: str) -> int:
    return FLOORS["wiki"] if spec.startswith("en.") else FLOORS["wiki_other"]


def _slim(app: dict[str, Any] | None) -> dict[str, Any] | None:
    if not app:
        return None
    keys = ("app_id", "name", "seller", "release_date", "ratings")
    return {k: app.get(k) for k in keys}


def measure_supply(
    entry: dict[str, Any],
    fetcher: Fetcher,
    cutoff: str | None,
    baseline: dict[str, int],
    last_year: int,
) -> dict[str, Any]:
    """App supply for one country. The baseline is US-only, so surges outside the US are
    approximate."""
    country = entry["country"]
    results = [fetcher.apps(term, country) for term in entry["terms"]]
    rows = [row for result in results if result for row in result]
    apps = match_apps(rows, entry["pattern"])
    winner, early = first_winner(apps, entry.get("min_ratings", 5000), cutoff)
    quarters = release_counts(apps, "quarter")
    years = release_counts(apps, "year")
    top = sorted(apps, key=lambda a: -a["ratings"])[:5]
    return {
        "country": country,
        "terms": entry["terms"],
        "min_ratings": entry.get("min_ratings", 5000),
        "clone_min": entry.get("clone_min", 10),
        "capped": any(result and len(result) >= SEARCH_LIMIT - 10 for result in results),
        "failed": any(result is None for result in results),
        "matched": len(apps),
        "winner": _slim(winner),
        "pre_cutoff_winners": [_slim(a) for a in early],
        "clone_wave": clone_wave(quarters, entry.get("clone_min", 10)),
        "years": years,
        "surges": surge_years(years, baseline, range(2016, last_year + 1)),
        "top": [_slim(a) for a in top],
    }


def _earliest(signals: list[dict[str, Any]], kind: str | None = None) -> str | None:
    found = [s["onset"] for s in signals if s.get("onset") and (kind is None or s["kind"] == kind)]
    return min(found) if found else None


def measure_wave(
    wave: dict[str, Any],
    fetcher: Fetcher,
    months: list[str],
    baseline: dict[str, int],
    last_year: int,
) -> dict[str, Any]:
    signals = [
        measure_signal("wiki", spec, fetcher.wiki(spec), months, wiki_floor(spec))
        for spec in wave.get("wiki", [])
    ]
    signals += [
        measure_signal("hn", q, fetcher.hn(q), months, FLOORS["hn"]) for q in wave.get("hn", [])
    ]
    signals += [
        measure_signal("github", q, fetcher.github(q), fetcher.github_months, FLOORS["github"])
        for q in wave.get("github", [])
    ]
    first = _earliest(signals)
    cutoff = f"{shift_month(first, -PIVOT_MONTHS)}-01" if first else None
    supply = [
        measure_supply(entry, fetcher, cutoff, baseline, last_year)
        for entry in wave.get("apps", [])
    ]
    wiki_en = [s for s in signals if s["kind"] == "wiki" and s["key"].startswith("en.")]
    en_onsets = sorted({m for s in wiki_en for m in s.get("onsets", [])})
    surges = supply[0]["surges"] if supply else []
    return {
        "id": wave["id"],
        "label": wave["label"],
        "kind": wave["kind"],
        "note": wave.get("note"),
        "signals": signals,
        "first_onset": first,
        "first_onset_by_kind": {k: _earliest(signals, k) for k in ("wiki", "hn", "github")},
        "cutoff": cutoff,
        "supply": supply,
        "surges": surges,
        "hit_stats": hit_stats(en_onsets, surges, last_year=last_year),
        "timeline": timeline(signals, supply),
    }


def timeline(signals: list[dict[str, Any]], supply: list[dict[str, Any]]) -> list[list[str]]:
    """Key dates in order: first onset per source kind, the biggest Wikipedia article's peak
    and halving, then each country's first winner, clone-wave quarter and first surge year."""
    events: list[list[str]] = []
    for kind in ("wiki", "hn", "github"):
        firsts = [(s["onset"], s["key"]) for s in signals if s["kind"] == kind and s.get("onset")]
        if firsts:
            month, key = min(firsts)
            events.append([month, f"{kind} 最早起势（{key}）"])
    wiki = [s for s in signals if s["kind"] == "wiki" and s.get("peak_mean")]
    if wiki:
        top = max(wiki, key=lambda s: s["peak_mean"])
        events.append([top["peak_month"], f"注意力峰值（{top['key']}）"])
        if top["halved"]:
            events.append([top["halved"], "注意力跌破峰值一半"])
    for item in supply:
        country = item["country"]
        if item["winner"]:
            events.append([item["winner"]["release_date"][:7], f"{country} 第一个赢家上架"])
        if item["clone_wave"]:
            events.append([item["clone_wave"], f"{country} 克隆潮（单季 ≥{item['clone_min']} 款）"])
        if item["surges"]:
            events.append([f"{item['surges'][0]}", f"{country} 供给突增年（按基线）"])
    return sorted(events, key=lambda e: _event_index(e[0]))


def _event_index(value: str) -> int:
    return month_index(value) if len(value) > 4 else int(value) * 12


def measure_control(
    control: dict[str, Any],
    fetcher: Fetcher,
    months: list[str],
    baseline: dict[str, int],
    last_year: int,
) -> dict[str, Any]:
    signal = measure_signal(
        "wiki", control["wiki"], fetcher.wiki(control["wiki"]), months, FLOORS["wiki"]
    )
    rows = fetcher.apps(control["term"], control.get("country", "us")) or []
    apps = match_apps(rows, control["pattern"])
    years = release_counts(apps, "year")
    surges = surge_years(years, baseline, range(2016, last_year + 1))
    return {
        "id": control["id"],
        "signal": signal,
        "term": control["term"],
        "matched": len(apps),
        "capped": len(rows) >= SEARCH_LIMIT - 10,
        "years": years,
        "surges": surges,
        "hit_stats": hit_stats(signal.get("onsets", []), surges, last_year=last_year),
    }


def baseline_counts(config: dict[str, Any], fetcher: Fetcher) -> dict[str, int]:
    total: dict[str, int] = {}
    for item in config.get("baseline", []):
        rows = fetcher.apps(item["term"], item.get("country", "us")) or []
        for year, count in release_counts(match_apps(rows, item["pattern"]), "year").items():
            total[year] = total.get(year, 0) + count
    return dict(sorted(total.items()))


def _sum_stats(items: Iterable[dict[str, Any]]) -> dict[str, int]:
    total = {"onsets": 0, "scored": 0, "hits": 0, "surges": 0, "preceded": 0}
    for item in items:
        for key in total:
            total[key] += item["hit_stats"][key]
    return total


def run_backtest(
    session: requests.Session,
    storage: Storage,
    config: dict[str, Any],
    *,
    refresh: bool = False,
    github_token: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    months = month_range(config["start_month"], config["end_month"])
    github_months = month_range(config["github_start_month"], config["end_month"])
    fetcher = Fetcher(
        session,
        storage,
        months,
        github_months,
        refresh=refresh,
        github_token=github_token,
        sleep=sleep,
        log=log,
    )
    last_year = int(config["end_month"][:4])
    baseline = baseline_counts(config, fetcher)
    waves = [measure_wave(w, fetcher, months, baseline, last_year) for w in config.get("waves", [])]
    controls = [
        measure_control(c, fetcher, months, baseline, last_year) for c in config.get("controls", [])
    ]
    return {
        "span": [months[0], months[-1]],
        "floors": FLOORS,
        "pivot_months": PIVOT_MONTHS,
        "horizon_years": HORIZON_YEARS,
        "baseline": baseline,
        "waves": waves,
        "controls": controls,
        "wave_stats": _sum_stats(waves),
        "control_stats": _sum_stats(controls),
        "failures": fetcher.failures,
    }


# --- rendering ------------------------------------------------------------------------------


def _years_text(years: dict[str, int], since: int = 2016) -> str:
    return " ".join(f"{y[2:]}:{n}" for y, n in years.items() if int(y) >= since) or "无"


def _app_text(app: dict[str, Any] | None) -> str:
    if not app:
        return "无"
    return f"{app['name'][:32]}（{app['release_date']}，{app['ratings']:,} 条评分）"


def _render_wave(wave: dict[str, Any]) -> list[str]:
    lines = [f"### {wave['label']}（{wave['kind']}）", ""]
    if wave.get("note"):
        lines += [wave["note"], ""]
    lines += [
        "| 信号 | 数据起点 | 起势月份 | 3 月均值峰值 | 跌破峰值一半 |",
        "|---|---|---|---|---|",
    ]
    for s in wave["signals"]:
        if s.get("error"):
            lines.append(f"| {s['kind']} {s['key']} | 抓取失败 | | | |")
            continue
        peak = f"{s['peak_month']}（{s['peak_mean']:,}）" if s["peak_month"] else "—"
        onset_text = "、".join(s["onsets"]) or "无"
        lines.append(
            f"| {s['kind']} {s['key']} | {s['first_month'] or '无数据'} | {onset_text} "
            f"| {peak} | {s['halved'] or '—'} |"
        )
    lines += [
        "",
        f"最早起势 {wave['first_onset'] or '无'}；早于 {wave['cutoff'] or '—'} 上架的大 App "
        "不算这波的赢家（多半是改名转型或上一波的老玩家）。",
        "",
        "| 国家 | 搜索词 | 匹配 | 第一个赢家 | 克隆潮 | 突增年 | 按年上架 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in wave["supply"]:
        capped = "（触顶）" if item["capped"] else ""
        lines.append(
            f"| {item['country']} | {' / '.join(item['terms'])} | {item['matched']}{capped} "
            f"| {_app_text(item['winner'])} | {item['clone_wave'] or '无'} "
            f"| {'、'.join(map(str, item['surges'])) or '无'} | {_years_text(item['years'])} |"
        )
    excluded = [(i["country"], a) for i in wave["supply"] for a in i["pre_cutoff_winners"]]
    if excluded:
        names = "；".join(f"{c} {a['name'][:24]}（{a['release_date'][:4]}）" for c, a in excluded)
        lines += ["", f"排除的早期大 App：{names}"]
    lines += ["", "时间线：" + " → ".join(f"{m} {label}" for m, label in wave["timeline"]), ""]
    return lines


def quiet_candidates(
    result: dict[str, Any], recent_months: int = 36, max_supply: int = 10
) -> list[dict[str, str]]:
    """Controls whose attention doubled recently while last full year's app releases stay low:
    the shape GLP-1 had before its trackers arrived."""
    end = result["span"][1]
    last_full_year = str(int(end[:4]) - 1)
    found = []
    for c in result["controls"]:
        recent = [
            m for m in c["signal"].get("onsets", []) if 0 <= months_between(m, end) <= recent_months
        ]
        supply = c["years"].get(last_full_year, 0)
        if recent and supply < max_supply:
            onset_text = "、".join(recent)
            why = f"起势 {onset_text}，{last_full_year} 年新上架 {supply} 款"
            found.append({"id": c["id"], "why": why})
    return found


def _ratio(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator}" + (
        f"（{numerator / denominator:.0%}）" if denominator else ""
    )


def render_markdown(result: dict[str, Any]) -> str:
    span = result["span"]
    lines = [
        f"# 趋势信号回测（{span[0]} 至 {span[1]}）",
        "",
        "## 口径",
        "",
        "- 起势：3 个月均值同比翻倍且不低于门槛（Wikipedia 英文 3,000 次/月、其他语言 500、"
        "HN 3 篇/月、GitHub 20 个新仓库/月），两次起势至少隔 12 个月。数据起点之前的起势看不到。",
        "- 供给：iTunes search 每个词每国最多 200 条，按名称正则匹配，按原始上架日期计数。"
        "下架的 App 查不到，改名转型的老 App 保留原上架日期。",
        "- 第一个赢家：达到评分门槛的最早上架者，"
        f"早于最早起势 {result['pivot_months']} 个月的不算。"
        "克隆潮：第一个上架数达到门槛的季度（绝对数，近两年会被全站供给增长推高）。",
        f"- 供给突增年：按基线（计算器、天气等）缩放后，上架数达到前两年均值的 2 倍且不少于 5 款。"
        f"命中：起势后 {result['horizon_years']} 年内出现突增；只计窗口完整的起势。",
        "",
        "## 已知浪潮",
        "",
    ]
    for wave in result["waves"]:
        lines += _render_wave(wave)
    lines += [
        "## 对照组（美区，英文 Wikipedia）",
        "",
        "| 话题 | 起势 | 峰值 | 匹配 | 突增年 | 按年上架 |",
        "|---|---|---|---|---|---|",
    ]
    for c in result["controls"]:
        s = c["signal"]
        onset_text = "无数据" if s.get("error") else ("、".join(s["onsets"]) or "无")
        capped = "（触顶）" if c["capped"] else ""
        lines.append(
            f"| {c['id']} | {onset_text} | {s.get('peak_month') or '—'} "
            f"| {c['matched']}{capped} | {'、'.join(map(str, c['surges'])) or '无'} "
            f"| {_years_text(c['years'])} |"
        )
    for name, key in (("已知浪潮", "wave_stats"), ("对照组", "control_stats")):
        st = result[key]
        lines += [
            "",
            f"**{name}**：起势后 {result['horizon_years']} 年内跟出供给突增 "
            f"{_ratio(st['hits'], st['scored'])}；"
            f"供给突增之前 {result['horizon_years']} 年内有起势 "
            f"{_ratio(st['preceded'], st['surges'])}。",
        ]
    lines += ["", "## 注意力起势、供给还少的对照话题", ""]
    lines += [f"- {c['id']}：{c['why']}" for c in quiet_candidates(result)] or ["- 无"]
    lines += ["", "## 基线（按年上架数之和）", "", _years_text(result["baseline"], 2010), ""]
    if result["failures"]:
        lines += ["## 抓取失败", ""]
        lines += [f"- {f['kind']} {f['key']}: {f['error'][:160]}" for f in result["failures"]]
    return "\n".join(lines).rstrip() + "\n"


def write_backtest(storage: Storage, result: dict[str, Any]) -> tuple[Path, Path]:
    md_path = storage.backtest_report_path("md")
    json_path = storage.backtest_report_path("json")
    write_json(json_path, result)
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return md_path, json_path
