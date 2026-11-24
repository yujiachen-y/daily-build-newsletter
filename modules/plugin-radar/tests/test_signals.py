from __future__ import annotations

from helpers import hub_snapshot, skillssh_snapshot

from plugin_radar import signals
from plugin_radar.storage import parse_iso

GH = {
    "mattpocock/skills": {"stars": 330_173, "created": "2026-02-03"},
    "beltsh/superpowers": {"stars": 3, "created": "2026-11-13"},
    "whytryharder/superpowers": {"stars": 0, "created": "2026-11-13"},
    "qu-skills/superpowers": {"stars": 4, "created": "2026-09-02"},
    "flowkit-labs/skills": {"stars": 46, "created": "2026-08-12"},
    "mid/repo": {"stars": 400, "created": "2026-01-01"},
    "gone/repo": None,
}


def test_suspicion_rules() -> None:
    assert signals.suspicion("mattpocock/skills", 4_700, GH)[0] == "ok"
    status, reasons = signals.suspicion("beltsh/superpowers", 29_456, GH)
    assert status == "suspect" and "仅 3 星" in reasons[0]
    # 400 stars but 15,000 installs a day: 37 installs per star per day
    assert signals.suspicion("mid/repo", 15_000, GH)[0] == "suspect"
    assert signals.suspicion("mid/repo", 3_000, GH)[0] == "ok"
    assert signals.suspicion("flowkit-labs/skills", 900, GH)[0] == "ok"  # too small to judge
    assert signals.suspicion("open.feishu.cn", 9_999, GH)[0] == "unverified"
    assert signals.suspicion("gone/repo", 9_999, GH)[0] == "unverified"
    assert signals.suspicion("never/looked-up", 9_999, GH)[0] == "unverified"


def test_clusters_need_three_low_star_sources_with_the_same_skill() -> None:
    trending = [
        {"source": "beltsh/superpowers", "skill": "ai-video-generation", "installs_24h": 29_456},
        {"source": "qu-skills/superpowers", "skill": "ai-video-generation", "installs_24h": 9_000},
        {
            "source": "whytryharder/superpowers",
            "skill": "ai-video-generation",
            "installs_24h": 3_000,
        },
        {"source": "mattpocock/skills", "skill": "grill-me", "installs_24h": 4_700},
    ]
    groups = signals.clusters(trending, GH)
    assert list(groups) == ["ai-video-generation"]
    assert groups["ai-video-generation"]["installs_24h"] == 41_456


def test_pick_base_respects_window() -> None:
    now = parse_iso("2026-11-22T14:00:00Z")
    hist = [
        {"observed_at": "2026-11-12T14:00:00Z"},
        {"observed_at": "2026-11-15T21:17:00Z"},
        {"observed_at": "2026-11-22T04:00:00Z"},
    ]
    assert signals.pick_base(hist, now, 7, 5, 9.5)["observed_at"] == "2026-11-15T21:17:00Z"
    assert signals.pick_base(hist, now, 1, 0.6, 1.6) is None  # 10 hours is too short


def test_skillssh_rising_uses_real_interval_and_skips_suspects() -> None:
    weekly = [5_000] * 7 + [7_000]  # last complete week: 1,000 a day
    base = skillssh_snapshot(
        "2026-11-16",
        "2026-11-15T21:17:00Z",
        {
            "mattpocock/skills/grill-me": (1_000_000, weekly),
            "beltsh/superpowers/ai-video-generation": (10, [0] * 8),
        },
        origin="wayback",
    )
    cur = skillssh_snapshot(
        "2026-11-22",
        "2026-11-22T21:17:00Z",  # exactly 7 days later
        {
            "mattpocock/skills/grill-me": (1_000_000 + 7 * 2_500, weekly),
            "beltsh/superpowers/ai-video-generation": (200_010, [0] * 7 + [50_000]),
        },
        trending=[
            ("beltsh/superpowers/ai-video-generation", 29_456),
            ("mattpocock/skills/grill-me", 4_700),
        ],
    )
    s = signals.skillssh(cur, [base], GH)
    assert s["base_7d"]["days"] == 7.0 and s["base_7d"]["origin"] == "wayback"
    assert [r["name"] for r in s["rising"]] == ["grill-me"]
    grill = s["rising"][0]
    assert grill["rate_recent"] == 2_500 and grill["rate_last_week"] == 1_000
    assert grill["ratio_recent"] == 2.5  # vs max(1,000 last week, 714 four-week average)
    assert [r["name"] for r in s["suspects"]] == ["ai-video-generation"]
    assert s["totals_24h"]["suspect"] == 29_456
    assert s["week"] == "2026-11-09 至 2026-11-15"


def test_rising_ignores_a_rebound_after_one_quiet_week() -> None:
    weekly = [4_100] * 7 + [2_149]  # one dip, like notion-api in the week to 2026-11-15
    base = skillssh_snapshot(
        "2026-11-16", "2026-11-15T21:17:00Z", {"mattpocock/skills/rebound": (100_000, weekly)}
    )
    cur = skillssh_snapshot(
        "2026-11-22",
        "2026-11-22T21:17:00Z",
        {"mattpocock/skills/rebound": (100_000 + 7 * 719, weekly)},
    )
    s = signals.skillssh(cur, [base], GH)
    assert s["rising"] == []


def test_weekly_up_and_cooling_and_streak() -> None:
    cur = skillssh_snapshot(
        "2026-11-22",
        "2026-11-22T14:00:00Z",
        {
            "mattpocock/skills/up": (
                500_000,
                [1_000, 1_000, 2_000, 2_000, 2_000, 2_000, 3_000, 9_000],
            ),
            "mattpocock/skills/down": (
                900_000,
                [9_000, 9_000, 40_000, 40_000, 40_000, 40_000, 40_000, 8_000],
            ),
        },
    )
    s = signals.skillssh(cur, [], GH)
    assert [r["name"] for r in s["weekly_up"]] == ["up"]
    up = s["weekly_up"][0]
    assert up["avg4"] == 2_250 and up["ratio_week"] == 4.0 and up["streak"] == 2
    assert [r["name"] for r in s["cooling"]] == ["down"]
    assert s["base_7d"] is None and s["rising"] == []


def test_breakout_needs_most_installs_in_the_last_day() -> None:
    cur = skillssh_snapshot(
        "2026-11-22",
        "2026-11-22T14:00:00Z",
        {"mattpocock/skills/new": (10_000, [0] * 8), "mattpocock/skills/old": (900_000, [1] * 8)},
        trending=[
            ("mattpocock/skills/new", 6_000),
            ("mattpocock/skills/old", 5_000),
            ("mid/repo/unlisted", 2_000),
        ],
    )
    s = signals.skillssh(cur, [], GH)
    assert [r["skill"] for r in s["breakouts"]] == ["new", "unlisted"]


def test_hub_movers_rates_and_flags() -> None:
    base = hub_snapshot(
        "2026-11-21",
        "2026-11-21T00:00:00Z",
        {"a/x": {"downloads": 1_000}, "a/y": {"downloads": 50}},
    )
    cur = hub_snapshot(
        "2026-11-22",
        "2026-11-22T12:00:00Z",
        {
            "a/x": {"downloads": 4_000, "stars": 30, "created": "2026-11-20"},
            "a/y": {"downloads": 500_050, "stars": 2, "created": "2026-01-01"},
        },
    )
    h = signals.hub(cur, [base])
    assert h["base"]["days"] == 1.5
    by_id = {m["id"]: m for m in h["movers"]}
    assert by_id["a/x"]["per_day"] == 2_000
    assert by_id["a/y"]["flags"]  # many downloads, two stars
    assert [r["id"] for r in h["new_fast"]] == ["a/x"]
    assert h["new_fast"][0]["age_days"] == 2


def test_hub_without_history_has_no_movers() -> None:
    cur = hub_snapshot("2026-11-22", "2026-11-22T12:00:00Z", {"a/x": {"downloads": 4}})
    h = signals.hub(cur, [])
    assert h["base"] is None and h["movers"] == []


def test_catalog_diff_for_snapshot_only_source() -> None:
    prev = {
        "day": "2026-11-21",
        "observed_at": "2026-11-21T00:00:00Z",
        "plugins": {"飞书": {}, "钉钉": {}},
    }
    cur = {
        "label": "Kimi 插件介绍页",
        "observed_at": "2026-11-22T00:00:00Z",
        "plugins": {"飞书": {}, "Figma": {"description": "设计"}},
    }
    c = signals.catalog(cur, [prev], {})
    assert [a["name"] for a in c["added"]] == ["Figma"]
    assert [x["name"] for x in c["removed"]] == ["钉钉"]
    assert signals.catalog(cur, [], {})["base"] is None


def test_claude_installs_only_moves_when_file_regenerated() -> None:
    old = {"generated_at": "2026-10-21T07:42:41Z", "installs": {"a": 100, "b": 50}}
    same = {"generated_at": "2026-10-21T07:42:41Z", "installs": {"a": 100, "b": 50}, "age_days": 32}
    assert signals.claude_installs(same, [old])["movers"] == []
    new = {"generated_at": "2026-10-23T07:42:41Z", "installs": {"a": 300, "b": 50}, "age_days": 0}
    out = signals.claude_installs(new, [old, same])
    assert out["movers"] == [{"name": "a", "installs": 300, "delta": 200, "per_day": 100}]
