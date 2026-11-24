from __future__ import annotations

from helpers import hub_snapshot, skillssh_snapshot

from plugin_radar import report, signals
from plugin_radar.storage import Storage, write_json


def test_zh_and_cnt_formatting() -> None:
    assert report.zh(9_876) == "9,876"
    assert report.zh(10_000) == "1 万"
    assert report.zh(47_049) == "4.7 万"
    assert report.zh(123_456_789) == "1.23 亿"
    assert report.cnt(9_876) == "9,876 次"
    assert report.cnt(47_049) == "4.7 万次"
    assert report.cnt(88_091, "星") == "8.8 万星"


def test_one_per_source_keeps_strongest_and_names_siblings() -> None:
    rows = [
        {"source": "heygen-com/hyperframes", "name": "style-sampling"},
        {"source": "remotion-dev/skills", "name": "remotion-license"},
        {"source": "heygen-com/hyperframes", "name": "reverse-any-video"},
    ]
    out = signals.one_per_source(rows)
    assert [r["name"] for r in out] == ["style-sampling", "remotion-license"]
    assert out[0]["siblings"] == ["reverse-any-video"]
    assert "reverse-any-video" in report._sib(out[0])


def _seed(storage: Storage, day: str, statuses: dict[str, dict]) -> None:
    weekly = [1_000] * 7 + [9_000]
    write_json(
        storage.snapshot_path("skillssh", day),
        skillssh_snapshot(
            day,
            f"{day}T14:00:00Z",
            {"mattpocock/skills/grill-me": (500_000, weekly)},
            trending=[("beltsh/superpowers/ai-video-generation", 29_456)],
        ),
    )
    write_json(
        storage.snapshot_path("skillhub", day),
        hub_snapshot(day, f"{day}T14:00:00Z", {"a/x": {"downloads": 9, "created": day}}),
    )
    write_json(
        storage.snapshot_path("github", day),
        {"repos": {"mattpocock/skills": {"stars": 330_000}, "beltsh/superpowers": {"stars": 3}}},
    )
    write_json(storage.run_path(day), {"sources": statuses})


def test_report_end_to_end_marks_failures_and_never_reuses_stale_snapshots(tmp_path) -> None:
    storage = Storage(tmp_path)
    day = "2026-11-22"
    _seed(
        storage,
        day,
        {"skillssh": {"status": "ok"}, "skillhub": {"status": "failed", "error": "HTTP 502"}},
    )
    r = report.build_report(storage, day)
    assert r["skillssh"]["weekly_up"][0]["name"] == "grill-me"
    assert r["skillhub"] is None  # failed today: no section, even though a snapshot exists
    assert r["sources"]["skillhub"]["status"] == "failed"
    assert r["sources"]["clawhub"]["status"] == "missing"
    md = report.render_markdown(r)
    assert "**grill-me**（`mattpocock/skills`）这一周安装 9,000 次" in md
    assert "是平均的 9.0 倍" in md
    assert "| SkillHub | failed |" in md
    assert "仓库仅 3 星" in md
    # status lines belong to the report, and the report says so
    assert "不写进日报" in md
    # suspect-install stats are a filter, not a daily signal: they stay out of section 1
    writable = md.split("## 2. 明细表")[0]
    assert "GitHub 关注度严重不符" not in writable
    assert "beltsh/superpowers" not in writable


def test_github_lookups_carry_over_from_recent_days(tmp_path) -> None:
    from plugin_radar import cli

    storage = Storage(tmp_path)
    write_json(
        storage.snapshot_path("github", "2026-11-21"),
        {"day": "2026-11-21", "repos": {"a/b": {"stars": 5}, "c/d": None}},
    )
    stats = {"x/y": {"stars": 1}}
    carried = cli._carry_github(storage, "2026-11-22", ["x/y", "a/b", "c/d"], stats)
    assert carried == 1
    assert stats["a/b"] == {"stars": 5, "as_of": "2026-11-21"}
    assert "c/d" not in stats  # a past "not found" is not carried


def test_clip_prefers_sentence_end() -> None:
    text = "提供 208 个 MCP 工具。" + "所有物理数字都出自确定性内核" * 20
    assert report._clip(text) == "提供 208 个 MCP 工具。" or report._clip(text).endswith("…")
    long_sentence = "第一句话写得比较长一些用来占位。" * 3 + "第二句" * 60
    assert report._clip(long_sentence).endswith("。")
    assert report._clip("短。") == "短。"
