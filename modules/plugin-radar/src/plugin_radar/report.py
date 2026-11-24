"""Build the day's report (JSON for machines and fact-check, Markdown for the editor)."""

from __future__ import annotations

from typing import Any

from . import signals
from .catalogs import CATALOGS
from .storage import Storage, iso, parse_iso, read_json, utc_now, write_json

SOURCES = {
    "skillssh": "skills.sh",
    "skillhub": "SkillHub",
    "clawhub": "ClawHub",
    "catalog-claude": "Claude Code 官方市场",
    "catalog-codex": "Codex 官方插件目录",
    "catalog-zcode": "ZCode 官方市场",
    "catalog-kimi": "Kimi 插件介绍页",
    "claude-installs": "Claude Code 安装数文件",
}
LIMITS = {"trending": 60, "list": 15, "suspects": 30, "hub": 30}

# What each platform exposes, verified on 2026-11-22. Shown in the report, never in the newsletter.
COVERAGE = [
    (
        "Claude Code",
        "官方市场目录（GitHub 历史）+ 安装数文件",
        "安装数文件 plugin-details.json 停在 2026-10-21；claude.com 页面上的安装数自 2026-09-29 起"
        "未变（Internet Archive 存档比对）。目录上新/下架是实时的。",
    ),
    (
        "Codex",
        "官方插件目录（openai/plugins 的 GitHub 历史）",
        "客户端的 /ps/plugins/list 需要登录，二进制里没有安装数字段：没有公开热度数字。",
    ),
    (
        "WorkBuddy",
        "SkillHub（技能市场里的 SkillHub 页签）",
        "客户端「推荐」「套件」页签的使用量/安装量需要桌面客户端登录，未接入。",
    ),
    (
        "ZCode",
        "官方市场目录（zai-org/zcode-plugins 的 GitHub 历史）",
        "开源客户端里没有安装计数字段：没有公开热度数字。",
    ),
    (
        "Kimi Work",
        "kimi.com 插件介绍页（逐日比对）",
        "完整目录在开放平台 /v1/plugins，要 API key；没有热度数字。",
    ),
    ("豆包", "未覆盖", "技能商店只在 PC 客户端内，未找到公开目录或热度数字。"),
    (
        "跨 Agent",
        "skills.sh（npx skills 遥测）、ClawHub（OpenClaw）",
        "安装数是各自 CLI 的遥测，不含各家原生市场里的安装。",
    ),
]


def build_report(storage: Storage, day: str) -> dict[str, Any]:
    run = read_json(storage.run_path(day)) or {}
    statuses = run.get("sources") or {}
    snaps = {name: storage.load_snapshot(name, day) for name in SOURCES}
    gh = (storage.load_snapshot("github", day) or {}).get("repos") or {}

    def usable(name: str) -> dict[str, Any] | None:
        snap = snaps.get(name)
        if not snap or snap.get("origin") != "live":
            return None
        status = (statuses.get(name) or {}).get("status")
        return snap if status in (None, "ok", "reused") else None

    report: dict[str, Any] = {
        "day": day,
        "generated_at": iso(utc_now()),
        "sources": _source_table(snaps, statuses),
        "github_checked": len(gh),
        "skillssh": None,
        "skillhub": None,
        "clawhub": None,
        "catalogs": {},
        "claude_installs": None,
        "coverage": [{"platform": p, "covered_by": c, "note": n} for p, c, n in COVERAGE],
    }
    if usable("skillssh"):
        report["skillssh"] = _trim_skillssh(
            signals.skillssh(snaps["skillssh"], storage.history("skillssh", day), gh)
        )
    for name in ("skillhub", "clawhub"):
        if usable(name):
            report[name] = _trim_hub(signals.hub(snaps[name], storage.history(name, day)))
    for key in list(CATALOGS) + ["kimi"]:
        name = f"catalog-{key}"
        if usable(name):
            report["catalogs"][key] = signals.catalog(snaps[name], storage.history(name, day), gh)
    if usable("claude-installs"):
        report["claude_installs"] = signals.claude_installs(
            snaps["claude-installs"], storage.history("claude-installs", day)
        )
    return report


def _source_table(snaps: dict[str, Any], statuses: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for name, label in SOURCES.items():
        snap = snaps.get(name)
        status = statuses.get(name) or {}
        state = status.get("status") or (
            "ok" if snap and snap.get("origin") == "live" else "missing"
        )
        out[name] = {
            "label": label,
            "status": state,
            "observed_at": snap.get("observed_at") if snap else None,
            "error": status.get("error"),
            "raw": snap.get("raw") if snap else None,
        }
    return out


def _trim_skillssh(s: dict[str, Any]) -> dict[str, Any]:
    s = dict(s)
    s["trending"] = s["trending"][: LIMITS["trending"]]
    s["trending_clean"] = s["trending_clean"][: LIMITS["list"]]
    s["suspects"] = s["suspects"][: LIMITS["suspects"]]
    for key in ("breakouts", "rising", "weekly_up", "cooling"):
        s[key] = s[key][: LIMITS["list"]]
    s["clusters"] = s["clusters"][:10]
    return s


def _trim_hub(h: dict[str, Any]) -> dict[str, Any]:
    h = dict(h)
    h["trending"] = h["trending"][: LIMITS["hub"]]
    h["movers"] = h["movers"][: LIMITS["list"]]
    h["new_fast"] = h["new_fast"][: LIMITS["list"]]
    return h


def write_report(storage: Storage, report: dict[str, Any]) -> tuple[str, str]:
    md_path = storage.report_md_path(report["day"])
    json_path = storage.report_json_path(report["day"])
    write_json(json_path, report)
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return str(md_path), str(json_path)


# ---------------------------------------------------------------- formatting helpers


def zh(n: float | int | None) -> str:
    """Chinese-style count: 9,876 / 4.7 万 / 1.23 亿."""
    if n is None:
        return "?"
    n = int(round(n))
    if abs(n) >= 100_000_000:
        return f"{n / 1e8:.2f}".rstrip("0").rstrip(".") + " 亿"
    if abs(n) >= 10_000:
        return f"{n / 1e4:.1f}".rstrip("0").rstrip(".") + " 万"
    return f"{n:,}"


def cnt(n: float | int | None, unit: str = "次") -> str:
    """zh() plus a unit: 9,876 次 / 4.7 万次."""
    text = zh(n)
    return f"{text}{unit}" if text.endswith(("万", "亿")) else f"{text} {unit}"


def mmdd(text: str | None) -> str:
    if not text:
        return "?"
    if "T" in text:
        return parse_iso(text).astimezone().strftime("%m-%d")
    return text[5:10]


def local_time(text: str | None) -> str:
    return parse_iso(text).astimezone().strftime("%m-%d %H:%M") if text else "—"


def _times(ratio: float | None) -> str:
    return f"{ratio:.1f} 倍" if ratio is not None else "?"


def _stars(row: dict[str, Any]) -> str:
    if row.get("stars") is None:
        return "GitHub 星数未知"
    return f"GitHub {cnt(row['stars'], '星')}"


def _name(row: dict[str, Any]) -> str:
    return f"**{row['name']}**（`{row['source']}`）"


def _sib(row: dict[str, Any]) -> str:
    sib = row.get("siblings") or []
    if not sib:
        return ""
    names = "、".join(sib[:3]) + (f" 等 {len(sib)} 个技能" if len(sib) > 3 else " 技能")
    return f"同仓库的 {names}走势相同（一次安装整个仓库）。"


def _clip(text: str, limit: int = 140) -> str:
    """Cut at a sentence end so a half sentence never invites the writer to finish it."""
    if len(text) <= limit:
        return text
    cut = max(text.rfind(mark, 0, limit) for mark in ("。", "；", ". "))
    return text[: cut + 1] if cut > limit // 3 else text[: limit - 1] + "…"


def _short(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------- Markdown


def render_markdown(r: dict[str, Any]) -> str:
    out = [f"# 插件与技能热度 · {r['day']}", ""]
    out += [
        "给日报编辑用。第 1 节是可以直接写的信号，句子里的数字都已算好，照抄即可；"
        "写之前读第 4 节口径。第 3 节的来源状态只写进收尾报告，不写进日报。",
        "",
        "## 1. 值得写的信号",
        "",
    ]
    out += _skillssh_signals(r.get("skillssh"))
    out += _catalog_signals(r.get("catalogs") or {})
    out += _hub_signals(
        "SkillHub（WorkBuddy 技能市场里的 SkillHub 页签）", r.get("skillhub"), "下载"
    )
    out += _hub_signals("ClawHub（OpenClaw 技能市场）", r.get("clawhub"), "下载")
    out += ["## 2. 明细表", ""]
    out += _quality(r.get("skillssh"))
    out += _detail_tables(r)
    out += ["## 3. 来源状态（写进收尾报告，不写进日报）", ""]
    out += _source_rows(r)
    out += ["## 4. 口径（写日报前必读）", ""]
    out += _rules(r)
    return "\n".join(out).rstrip() + "\n"


def _skillssh_signals(s: dict[str, Any] | None) -> list[str]:
    out = ["### 1.1 skills.sh 热度上升（跨 Agent，已排除疑似刷量）", ""]
    if not s:
        return out + ["skills.sh 今天没抓到，本节为空。", ""]
    base = s.get("base_7d")
    if base and s["rising"]:
        origin = " Internet Archive 存档" if base["origin"] == "wayback" else "本地快照"
        out.append(f"对照：{mmdd(base['observed_at'])} 的{origin}，相隔 {base['days']:.1f} 天。")
        out.append("")
        for row in s["rising"][:5]:
            out.append(
                f"- {_name(row)}最近 {base['days']:.1f} 天日均安装 {cnt(row['rate_recent'])}，"
                f"上周（{s['week']}）日均 {cnt(row['rate_last_week'])}、再往前四周日均 "
                f"{cnt(row['rate_avg4'])}，是两者中较高值的 {_times(row['ratio_recent'])}；"
                f"累计 {cnt(row['total'])}，{_stars(row)}。"
                f"{_sib(row)} [skills.sh]({row['url']})"
            )
    elif not base:
        out.append("没有 5–9 天前的快照（存档也没取到），这一节只看下面的周数据。")
    else:
        out.append("没有技能满足「日均 ≥300 次，且是上周日均和前四周日均中较高值的 1.5 倍以上」。")
    out.append("")
    out += [f"### 1.2 周安装加速（{s['week']} 这一周，对比前四周平均）", ""]
    if s["weekly_up"]:
        for row in s["weekly_up"][:5]:
            streak = f"，已连续 {row['streak']} 周上升" if row["streak"] >= 2 else ""
            out.append(
                f"- {_name(row)}这一周安装 {cnt(row['last_week'])}，前四周平均 "
                f"{cnt(row['avg4'])}，是平均的 {_times(row['ratio_week'])}{streak}；"
                f"{_stars(row)}。{_sib(row)} [skills.sh]({row['url']})"
            )
    else:
        out.append("没有技能满足「周安装 ≥3,000 且是前四周平均 1.5 倍以上」。")
    out.append("")
    out += ["### 1.3 新冒头（24 小时榜前 100 里，大部分安装发生在最近一天）", ""]
    if s["breakouts"]:
        for row in s["breakouts"][:5]:
            if row["total"]:
                tail = (
                    f"累计 {cnt(row['total'])}，其中 {round(row['share_24h'] * 100)}% "
                    "来自这 24 小时"
                )
            else:
                tail = "还没进累计榜前 600"
            created = f"，仓库建于 {row['repo_created']}" if row.get("repo_created") else ""
            out.append(
                f"- {_name(row)}过去 24 小时安装 {cnt(row['installs_24h'])}，24 小时榜第 "
                f"{row['rank']} 名；{tail}。{_stars(row)}{created}。{_sib(row)}"
                f" [skills.sh](https://skills.sh/{row['source']}/{row['skill']})"
            )
    else:
        out.append("没有。")
    out.append("")
    out += ["### 1.4 降温（上周安装前 50 里跌到前四周平均一半以下）", ""]
    if not s["cooling"]:
        out += ["没有。", ""]
    else:
        for row in s["cooling"][:3]:
            pct = round(row["last_week"] / row["avg4"] * 100)
            out.append(
                f"- {_name(row)}{s['week']} 这一周安装 {cnt(row['last_week'])}，"
                f"是前四周平均（{cnt(row['avg4'])}）的 {pct}%。{_sib(row)}"
                f" [skills.sh]({row['url']})"
            )
        out.append("")
    return out


def _catalog_signals(catalogs: dict[str, Any]) -> list[str]:
    out = ["### 1.5 官方市场上新与下架", ""]
    if not catalogs:
        return out + ["目录源今天都没抓到。", ""]
    any_change = False
    for key in ("claude", "codex", "zcode", "kimi"):
        c = catalogs.get(key)
        if not c:
            continue
        added, removed = c.get("added") or [], c.get("removed") or []
        if "window_days" in c:
            scope = f"近 {c['window_days']} 天（{mmdd(c['window_start'])} 起）"
        elif c.get("base"):
            scope = f"与 {mmdd(c['base']['observed_at'])} 相比"
        else:
            out.append(f"- {c['label']}：首次抓取，共 {c['count']} 个，明天起比对。")
            continue
        if not added and not removed:
            continue
        any_change = True
        parts = []
        if added:
            names = "、".join(_added_name(a) for a in added[:8])
            more = f" 等 {len(added)} 个" if len(added) > 8 else f"，共 {len(added)} 个"
            parts.append(f"上架 {names}{more}")
        if removed:
            names = "、".join(_added_name(x) for x in removed[:8])
            parts.append(f"下架 {names}")
        out.append(f"- {c['label']}{scope}：{'；'.join(parts)}。目录现有 {c['count']} 个。")
        for a in added[:8]:
            if a.get("description"):
                extra = (
                    f"，源仓库 GitHub {cnt(a['stars'], '星')}" if a.get("stars") is not None else ""
                )
                out.append(f"  - {a['name']}：{_clip(a['description'])}{extra}")
    if not any_change:
        out.append("- 各官方目录在窗口内没有上架或下架。")
    out.append("")
    return out


def _added_name(a: dict[str, Any]) -> str:
    return f"{a['name']}（{mmdd(a.get('date'))}）" if a.get("date") else a["name"]


def _hub_signals(title: str, h: dict[str, Any] | None, verb: str) -> list[str]:
    num = "1.6" if title.startswith("SkillHub") else "1.7"
    out = [f"### {num} {title}", ""]
    if not h:
        return out + ["今天没抓到，本节为空。", ""]
    base = h.get("base")
    if base and h["movers"]:
        out.append(f"对照：{mmdd(base['observed_at'])} 的快照，相隔 {base['days']:.1f} 天。")
        out.append("")
        for row in [m for m in h["movers"] if not m["flags"]][:5]:
            out.append(
                f"- **{_short(row['name'])}**近 {base['days']:.1f} 天日均{verb} "
                f"{cnt(row['per_day'])}，"
                f"累计 {cnt(row['downloads'])}，{row.get('stars', 0)} 个收藏/星。"
                f" [{title.split('（')[0]}]({row['url']})"
            )
    else:
        out.append("还没有可对照的早期快照（这两个站没有存档可回填），明天起出现日增。")
    out.append("")
    fresh = [r for r in h["new_fast"] if not r["flags"]][:3]
    if fresh:
        out.append(f"{HUB_NEW_LABEL}：")
        for row in fresh:
            out.append(
                f"- **{_short(row['name'])}**（{row['created']} 上架）"
                f"{row['age_days']} 天累计{verb} "
                f"{cnt(row['downloads'])}，{row.get('stars', 0)} 个收藏/星。"
                f"{row.get('summary', '')} [链接]({row['url']})"
            )
        out.append("")
    if h.get("trending"):
        top = "；".join(
            f"{_short(t['name'])}（累计{verb} {zh(t['downloads'])}）" for t in h["trending"][:5]
        )
        out += [f"站内趋势榜前五：{top}。", ""]
    return out


HUB_NEW_LABEL = f"近 {signals.HUB_NEW_DAYS} 天新上架、按上架以来日均排序"


def _quality(s: dict[str, Any] | None) -> list[str]:
    # 11-23 起不在第 1 节：刷量比例天天差不多，写进日报就是每天重复同一句话。它只是第 1 节的过滤器。
    out = ["### 刷量过滤明细（供核对，不写进日报）", ""]
    if not s:
        return out + ["skills.sh 今天没抓到。", ""]
    t = s["totals_24h"]
    if t["installs"]:
        out.append(
            f"- skills.sh 24 小时榜前 {t['rows']} 个技能共 {cnt(t['installs'])}安装，其中 "
            f"{cnt(t['suspect'])}（{round((t['suspect_share'] or 0) * 100)}%）"
            f"来自安装量与 GitHub 关注度严重不符的仓库；另有 {cnt(t['unverified'])}"
            "来自非 GitHub 来源或未核对的仓库。"
        )
    for g in s["clusters"][:3]:
        out.append(
            f"- 同名技能 `{g['skill']}` 由 {len(g['sources'])} 个低星仓库同时上 24 小时榜，合计 "
            f"{cnt(g['installs_24h'])}：{'、'.join(g['sources'][:6])}。"
        )
    if s["suspects"]:
        out += [
            "",
            "| 24h 名次 | 技能 | 来源 | 24h 安装 | GitHub 星 | 建库 | 判定依据 |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in s["suspects"][:12]:
            out.append(
                f"| {row['rank']} | {row['name']} | {row['source']} | {row['installs_24h']:,} | "
                f"{_fmt(row.get('stars'))} | {row.get('repo_created') or '?'} | "
                f"{'；'.join(row['reasons'])} |"
            )
    out.append("")
    return out


def _fmt(v: Any) -> str:
    return f"{v:,}" if isinstance(v, int) else "?"


def _detail_tables(r: dict[str, Any]) -> list[str]:
    out = []
    s = r.get("skillssh")
    if s:
        out += [
            "### skills.sh 24 小时榜前 20（含被排除的条目）",
            "",
            "| 名次 | 技能 | 来源 | 24h 安装 | 累计 | GitHub 星 | 状态 |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in s["trending"][:20]:
            state = {"ok": "", "suspect": "疑似刷量", "unverified": "无法核对"}[row["status"]]
            out.append(
                f"| {row['rank']} | {row['name']} | {row['source']} | {row['installs_24h']:,} | "
                f"{_fmt(row.get('total'))} | {_fmt(row.get('stars'))} | {state} |"
            )
        out.append("")
    for key, title in (("skillhub", "SkillHub 趋势榜前 10"), ("clawhub", "ClawHub 累计下载前 10")):
        h = r.get(key)
        if not h:
            continue
        rows = h["trending"][:10] if key == "skillhub" else h["top"][:10]
        out += [
            f"### {title}",
            "",
            "| 技能 | 累计下载 | 收藏/星 | 上架 | 提示 |",
            "|---|---|---|---|---|",
        ]
        for row in rows:
            out.append(
                f"| [{_short(row['name'])}]({row['url']}) | {row['downloads']:,} | "
                f"{row.get('stars', 0)} | "
                f"{row.get('created') or '?'} | {'；'.join(row.get('flags') or [])} |"
            )
        out.append("")
    c = r.get("claude_installs")
    if c:
        out += [
            f"### Claude Code 官方安装数（文件生成于 {mmdd(c['generated_at'])}，"
            f"{c['age_days']} 天前）",
            "",
        ]
        if c["movers"]:
            out.append(
                f"两次生成（{mmdd(c['previous_generated_at'])} → {mmdd(c['generated_at'])}）之间"
                "增长最快："
                + "；".join(f"{m['name']} 日均 +{zh(m['per_day'])}" for m in c["movers"][:5])
                + "。"
            )
        out.append(
            "存量前十（只作背景，不代表近期热度）："
            + "；".join(f"{t['name']} {zh(t['installs'])}" for t in c["top"])
            + "。"
        )
        out.append("")
    return out


def _source_rows(r: dict[str, Any]) -> list[str]:
    out = ["| 来源 | 状态 | 观测时间（本地） | 备注 |", "|---|---|---|---|"]
    for name, info in r["sources"].items():
        note = info.get("error") or ""
        if name == "claude-installs" and r.get("claude_installs"):
            c = r["claude_installs"]
            note = note or f"文件生成于 {c['generated_at']}，已 {c['age_days']} 天未更新"
        if name == "skillssh" and r.get("skillssh") and r["skillssh"].get("base_7d"):
            b = r["skillssh"]["base_7d"]
            note = note or f"7 天对照：{b['observed_at']}（{b['origin']}）"
        out.append(
            f"| {info['label']} | {info['status']} | {local_time(info['observed_at'])} | "
            f"{note[:160]} |"
        )
    out += ["", f"GitHub 核对仓库数：{r.get('github_checked', 0)}。", "", "平台覆盖：", ""]
    for c in r["coverage"]:
        out.append(f"- {c['platform']}：{c['covered_by']}。{c['note']}")
    out.append("")
    return out


def _rules(r: dict[str, Any]) -> list[str]:
    return [
        "- skills.sh 的安装数是 `npx skills` CLI 的去重安装遥测，跨 Claude Code、Codex、Cursor 等；"
        "不是活跃用户，也不含各家原生插件市场里的安装。写「安装 X 次」，不写「X 人在用」。",
        "- 「日均」都按两次观测的实际间隔折算；对照基准的日期写进句子（「较 11-15」）。周数据是已经"
        "结束的完整周（UTC 周一至周日），写清是哪一周，不要写成「本周」。",
        "- 疑似刷量和无法核对的条目不写成热度，刷量比例和冲榜仓库也不写进日报：第 1 节已经把它们"
        "滤掉了，比例每天都差不多，写了就是每天重复同一句话。",
        "- SkillHub 的下载量是累计口径，可能含客户端自动下载；它不是 WorkBuddy 客户端里的「安装量/"
        "使用量」。带「收藏极少」提示的条目不写成热度。",
        "- 官方目录的上架/下架是事实，但不代表热度；从目录里消失不等于停用，写「从官方目录移除」。",
        "- Claude Code 的安装数文件停在生成日，相同数字不代表「没有变化」。只有报告给出两次生成之间"
        "的增长时才能写增长。",
        "- 豆包、Kimi、Codex、ZCode 没有公开的单个插件热度数字；不要写「X 平台上最热的插件」。",
        f"- 生成时间：{r['generated_at']}。数字照抄本报告，不要自己重算。",
        "",
    ]
