from __future__ import annotations

from datetime import date
from typing import Any

from . import signals
from .apple import CHARTS, COUNTRIES, GENRES
from .dataxapi import load_series
from .storage import Storage, read_json, read_jsonl, write_json
from .supply import CLONE_MIN, STAGES

LIMITS = {
    "themes": 10,
    "young_grossing": 20,
    "young_free": 15,
    "climbers": 15,
    "entered": 15,
    "dropped": 10,
    "rating_growth": 10,
    "indices": 20,
}
YOUNG_FREE_MAX_RANK = 20
ENTERED_MAX_RANK = 50
INDEX_SPIKE = 0.3

PLATFORM_LABELS = {"wechat": "微信指数", "douyin": "抖音指数", "xiaohongshu": "小红书搜索指数"}


def build_report(storage: Storage, day: str, *, young_days: int = 365, window: int = 7) -> dict:
    rows = read_jsonl(storage.charts_path(day))
    if not rows:
        raise FileNotFoundError(f"no chart snapshot for {day}; run `app-radar fetch` first")
    lookups = read_jsonl(storage.lookups_path(day))
    history = [d for d in storage.chart_days() if d < day]
    base_day = signals.pick_base_day(day, history, window)
    span = (date.fromisoformat(day) - date.fromisoformat(history[0])).days if history else 0

    young = signals.young_apps(day, rows, lookups, young_days=young_days)
    report: dict[str, Any] = {
        "day": day,
        "young_days": young_days,
        "history": {
            "snapshots_before_today": len(history),
            "span_days": span,
            "base_day": base_day,
        },
        "coverage": sorted({(r["country"], r["genre"], r["chart"]) for r in rows}),
        "run": read_json(storage.run_path(day)) or {},
        "themes": signals.themes(day, rows, lookups, young_days=young_days),
        "young_grossing": [a for a in young if a["best_grossing"]],
        "young_free": [
            a
            for a in young
            if not a["best_grossing"] and a["best_free"] and a["best_free"] <= YOUNG_FREE_MAX_RANK
        ],
        "moves": None,
        "rating_growth": [],
        "indices": signals.index_changes(load_series(storage)),
        "supply": read_json(storage.supply_path(day)),
    }
    if base_day:
        base_rows = read_jsonl(storage.charts_path(base_day))
        all_history = [r for d in history for r in read_jsonl(storage.charts_path(d))]
        report["moves"] = signals.chart_moves(
            day, rows, base_rows, all_history, history_span_days=span
        )
        young_ids = {a["app_id"] for a in young}
        report["rating_growth"] = [
            g
            for g in signals.rating_growth(
                day, base_day, lookups, read_jsonl(storage.lookups_path(base_day))
            )
            if g["app_id"] in young_ids
        ]
    return report


def write_report(storage: Storage, report: dict) -> tuple[str, str]:
    md_path, json_path = (
        storage.report_md_path(report["day"]),
        storage.report_json_path(report["day"]),
    )
    write_json(json_path, report)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return str(md_path), str(json_path)


def _place(p: dict[str, Any]) -> str:
    where = COUNTRIES.get(p["country"], p["country"]) + GENRES.get(p["genre"], p["genre"])
    return f"{where}第 {p['rank']} 名"


def _grossing_text(theme: dict[str, Any]) -> str:
    if not theme["in_grossing"]:
        return "都没进畅销榜"
    return f"{theme['in_grossing']} 款进畅销榜（最好第 {theme['best_grossing']} 名）"


def _n(value: float | int) -> str:
    return f"{value:,}"


def _ratings_text(app: dict[str, Any]) -> str:
    if not app["ratings"]:
        return "评分数未取到"
    parts = [
        f"{COUNTRIES.get(c, c)} {_n(app['ratings'][c])}（{app['ratings_per_day'][c]}/天）"
        for c in sorted(app["ratings"], key=lambda c: -app["ratings"][c])
    ]
    return "评分 " + "，".join(parts)


def _app_line(app: dict[str, Any], placements: list[dict[str, Any]]) -> str:
    shown = "、".join(_place(p) for p in placements[:4])
    more = f" 等 {len(placements)} 处" if len(placements) > 4 else ""
    line = (
        f"- **{app['name']}**（{app['seller']}"
        f"{'，该开发商另有上架超一年的在榜 App' if app['seller_has_older_app'] else ''}，"
        f"{app['first_release']} 上架，"
        f"{app['age_days']} 天）：{shown}{more}；{_ratings_text(app)}。"
    )
    if app.get("description_head"):
        line += f" 描述开头：{app['description_head']}"
    if app.get("url"):
        line += f" [App Store]({app['url']})"
    return line


def _header(report: dict) -> list[str]:
    run = report["run"]
    hist = report["history"]
    countries = run.get("countries") or sorted({c for c, _, _ in report["coverage"]})
    genres = run.get("genres") or sorted({g for _, g, _ in report["coverage"]})
    failures = [f for f in run.get("failures", []) if f.get("kind") == "chart"]
    if hist["base_day"]:
        history_text = (
            f"历史快照 {hist['snapshots_before_today']} 天（最早 {hist['span_days']} 天前），"
            f"变化对比基准日 {hist['base_day']}"
        )
    else:
        history_text = "没有更早的快照，本期不含排名变化与评分增速"
    return [
        f"# App 榜单信号 {report['day']}",
        "",
        f"覆盖：{'、'.join(COUNTRIES.get(c, c) for c in countries)} × "
        f"{'、'.join(GENRES.get(g, g) for g in genres)} × "
        f"{'/'.join(CHARTS.values())}前 100。{history_text}。"
        f"抓取失败的榜单 {len(failures)} 个（共 {len(report['coverage'])} 个成功）。",
        "",
        "**写作口径（必读）**",
        "- 排名来自 Apple 公开榜单，不是收入。不要写月入、营收、赚了多少。",
        "- 评分/天 = 本区评分总数 ÷ 本区上架天数，是下载量的粗代理；"
        "不同 App 的评分/下载比能差数倍。",
        "- 不在这份榜单里 ≠ 没在该国上架，也 ≠ 该国市场是空的。",
        f"- 新秀 = 在各区里最早的上架日期距今 ≤ {report['young_days']} 天。",
        "- 「首次进榜」只在下文明确标注时才能写；没标注的「新进」只表示比基准日多出来。",
        "- 第 6 节的供给阶段只数名字里带这个词的 App，来自 App Store 搜索：下架的查不到，"
        "改名的老 App 保留原上架日期。阶段反映供给，不反映需求大小。",
        f"- 「已扎堆」= 近 91 天至少 {CLONE_MIN} 款新上架。写「来晚了」「还有空档」这类判断，"
        "只能引用第 6 节的阶段和数字，并和全站基线一起看。",
        "",
    ]


def render_markdown(report: dict) -> str:
    lines = _header(report)

    lines.append("## 1. 新秀扎堆的名称主题")
    lines.append(
        "（每个词都满足：至少 3 家开发商的新秀 App 名里有它，且名里有它的 App 一半以上是新秀；"
        "指向同一批 App 的词合并成一条）"
    )
    if not report["themes"]:
        lines.append("- 无")
    for t in report["themes"][: LIMITS["themes"]]:
        lines.append(
            f"- **{' / '.join(t['tokens'][:4])}**：新秀 {t['young_apps']} 款 / "
            f"老 App {t['established_apps']} 款，"
            f"{t['sellers']} 家开发商，"
            f"{_grossing_text(t)}，"
            f"{'、'.join(COUNTRIES.get(c, c) for c in t['countries'])}，"
            f"{'、'.join(GENRES.get(g, g) for g in t['genres'])}。例：{'；'.join(t['examples'])}"
        )
    lines.append("")

    young_grossing = report["young_grossing"]
    incumbents = sum(1 for a in young_grossing if a["seller_has_older_app"])
    lines.append(
        f"## 2. 新秀进畅销榜（共 {len(young_grossing)} 款，其中 {incumbents} 款的开发商另有"
        "上架超一年的在榜 App；按最好名次排序）"
    )
    if not young_grossing:
        lines.append("- 无")
    for app in young_grossing[: LIMITS["young_grossing"]]:
        lines.append(_app_line(app, app["grossing"]))
    lines.append("")

    young_free = report["young_free"]
    lines.append(
        f"## 3. 新秀在免费榜前 {YOUNG_FREE_MAX_RANK}、但没进任何畅销榜（共 {len(young_free)} 款）"
    )
    if not young_free:
        lines.append("- 无")
    for app in young_free[: LIMITS["young_free"]]:
        lines.append(_app_line(app, app["free"]))
    lines.append("")

    lines.extend(_moves_section(report))
    lines.extend(_indices_section(report))
    lines.extend(_supply_section(report))
    return "\n".join(lines).rstrip() + "\n"


def _moves_section(report: dict) -> list[str]:
    base_day = report["history"]["base_day"]
    lines = [f"## 4. 较 {base_day} 的变化" if base_day else "## 4. 排名与评分变化"]
    moves = report["moves"]
    if not moves:
        return lines + ["- 需要至少一天更早的快照，本期跳过。", ""]
    chart_name = CHARTS
    lines.append("**畅销榜爬升 ≥20 名**")
    climbers = [m for m in moves["climbers"] if m["chart"] == signals.GROSSING]
    for m in climbers[: LIMITS["climbers"]] or [None]:
        lines.append(
            f"- {m['name']}：{_place(m)}（{base_day} 为第 {m['base_rank']} 名，升 {m['climb']}）"
            if m
            else "- 无"
        )
    lines.append(f"**新进畅销榜前 {ENTERED_MAX_RANK}（{base_day} 不在前 100）**")
    entered = [
        m
        for m in moves["entered"]
        if m["chart"] == signals.GROSSING and m["rank"] <= ENTERED_MAX_RANK
    ]
    for m in entered[: LIMITS["entered"]] or [None]:
        if not m:
            lines.append("- 无")
            continue
        tag = (
            f"，在 {report['history']['span_days']} 天的快照里首次进这张榜"
            if m["first_seen"]
            else ""
        )
        lines.append(f"- {m['name']}：{_place(m)}{tag}")
    young_ids = {a["app_id"] for a in report["young_grossing"]} | {
        a["app_id"] for a in report["young_free"]
    }
    lines.append("**跌出畅销榜前 100 的新秀**")
    dropped = [
        m for m in moves["dropped"] if m["chart"] == signals.GROSSING and m["app_id"] in young_ids
    ]
    for m in dropped[: LIMITS["dropped"]] or [None]:
        lines.append(
            f"- {m['name']}：{COUNTRIES.get(m['country'], m['country'])}"
            f"{GENRES.get(m['genre'], m['genre'])}{chart_name[m['chart']]}，{base_day} 为第 "
            f"{m['base_rank']} 名"
            if m
            else "- 无"
        )
    lines.append("**评分增长最快的新秀**")
    for g in report["rating_growth"][: LIMITS["rating_growth"]] or [None]:
        lines.append(
            f"- {g['name']}（{COUNTRIES.get(g['country'], g['country'])}）：{g['span_days']} 天 +"
            f"{_n(g['delta'])} 条评分，{g['per_day_recent']}/天，是上架以来日均的 "
            f"{g['acceleration']} 倍"
            if g
            else "- 无"
        )
    return lines + [""]


def _indices_section(report: dict) -> list[str]:
    lines = ["## 5. 国内指数（DataXAPI，近 7 天日均对比前 7 天）"]
    indices = report["indices"]
    if not indices:
        return lines + ["- 未配置 DATAXAPI_API_KEY 或数据不足 14 天，本期跳过。", ""]
    for c in indices[: LIMITS["indices"]]:
        flag = " ⚑" if c["change"] is not None and abs(c["change"]) >= INDEX_SPIKE else ""
        change = f"{c['change']:+.0%}" if c["change"] is not None else "无法计算"
        lines.append(
            f"- {PLATFORM_LABELS.get(c['platform'], c['platform'])}「{c['keyword']}」："
            f"{change}（{_n(c['previous_avg'])} → {_n(c['recent_avg'])}，"
            f"截至 {c['last_date']}）{flag}"
        )
    lines.append("指数是各平台自己的热度分，不是搜索次数；三个平台的数值不能互相比较。")
    return lines + [""]


def _supply_cell(m: dict[str, Any]) -> list[str]:
    stage = STAGES[m["stage"]] + ("，加速" if m["accelerating"] else "")
    growth = "—" if m["growth_vs_baseline"] is None else f"{m['growth_vs_baseline']} 倍"
    winner = m["winner"]
    winner_text = (
        f"{winner['name'][:30]}（{winner['release_date']}，{_n(winner['ratings'])} 条评分）"
        if winner
        else "无"
    )
    capped = "（搜索结果触顶）" if m["capped"] else ""
    return [stage, f"{m['quarter']}{capped}", growth, winner_text]


def _supply_section(report: dict) -> list[str]:
    supply = report.get("supply")
    lines = [
        f"## 6. 供给阶段（App Store 搜索，统计截至 {supply['day']}）"
        if supply
        else "## 6. 供给阶段"
    ]
    if not supply:
        return lines + ["- 本期没有跑 `app-radar supply`。", ""]
    base = supply["baseline"]
    base_text = "、".join(
        f"{COUNTRIES.get(c, c)} {b['half']}/{b['prior_half']}"
        for c, b in sorted(base.items())
        if b.get("prior_half")
    )
    lines += [
        f"全站基线（冷门工具词近半年/前半年新上架数）：{base_text or '未取到'}。"
        "「增速」= 该词近半年新上架数的环比 ÷ 基线环比，大于 1 表示比全站涨得快。",
        "",
        "| 主题或关注项 | 国家 | 阶段 | 近 91 天新上架 | 增速 | 两年内评分最多 |",
        "|---|---|---|---|---|---|",
    ]
    for item in supply["items"]:
        name = item["key"] if item["kind"] == "theme" else f"关注：{item['label']}"
        for country, m in item["countries"].items():
            where = COUNTRIES.get(country, country)
            if m.get("error"):
                lines.append(f"| {name} | {where} | 搜索失败 | | | |")
                continue
            lines.append(
                f"| {name}（搜「{'、'.join(m['terms'])}」） | {where} | "
                + " | ".join(_supply_cell(m))
                + " |"
            )
    return lines + [""]
