from __future__ import annotations

from datetime import datetime, timezone

import pytest
from helpers import all_time_row, flight_page, skillssh_snapshot

from plugin_radar import skillssh
from plugin_radar.storage import Storage, write_json


def test_parse_page_reads_rows_split_across_flight_chunks() -> None:
    rows = [
        all_time_row("vercel-labs/skills", "find-skills", 4_482_796, [1, 2, 3]),
        {"source": "open.feishu.cn", "skillId": "lark-doc", "name": "lark-doc", "installs": 9},
    ]
    parsed = skillssh.parse_page(flight_page(rows))
    assert [r["skillId"] for r in parsed] == ["find-skills", "lark-doc"]
    items = skillssh.all_time_items(parsed)
    assert items["vercel-labs/skills/find-skills"]["weekly"] == [1, 2, 3]
    assert items["vercel-labs/skills/find-skills"]["rank"] == 1
    assert items["open.feishu.cn/lark-doc"]["weekly"] == []


def test_parse_page_rejects_pages_without_data() -> None:
    with pytest.raises(ValueError):
        skillssh.parse_page("<html>maintenance</html>")


def test_trending_items_keep_24h_counts_and_rank() -> None:
    rows = [{"source": "a/b", "skillId": "x", "name": "x", "installs": 500}]
    assert skillssh.trending_items(rows) == [
        {
            "rank": 1,
            "id": "a/b/x",
            "name": "x",
            "source": "a/b",
            "skill": "x",
            "installs_24h": 500,
            "official": False,
        }
    ]


@pytest.mark.parametrize(
    ("observed", "expected"),
    [
        ("2026-11-22T14:00:00+00:00", "2026-11-15"),  # Sunday: current week still running
        ("2026-11-16T12:22:00+00:00", "2026-11-15"),  # Monday after the rollover
        ("2026-11-15T21:17:00+00:00", "2026-11-08"),  # Sunday night UTC, before the rollover
    ],
)
def test_last_week_end_matches_observed_rollover(observed: str, expected: str) -> None:
    assert skillssh.last_week_end(datetime.fromisoformat(observed)).isoformat() == expected


def test_week_end_sticks_when_array_has_not_rolled_over(tmp_path) -> None:
    storage = Storage(tmp_path)
    weekly = [5, 6, 7, 8, 9, 10, 11, 12]
    old = skillssh_snapshot("2026-11-22", "2026-11-22T14:00:00Z", {"a/b/x": (100, weekly)})
    write_json(storage.snapshot_path("skillssh", "2026-11-22"), old)
    new = skillssh_snapshot("2026-11-23", "2026-11-23T01:00:00Z", {"a/b/x": (120, weekly)})
    new["week_end"] = "2026-11-22"  # what the calendar rule says on Monday 01:00 UTC
    skillssh._align_week_end(storage, new)
    assert new["week_end"] == "2026-11-15"


def test_closest_capture_prefers_smallest_day_gap() -> None:
    caps = ["20261114211127", "20261115211738", "20261118112118"]
    target = datetime(2026, 11, 15, tzinfo=timezone.utc).date()
    assert skillssh._closest(caps, target) == "20261115211738"
    far = datetime(2026, 11, 1, tzinfo=timezone.utc).date()
    assert skillssh._closest(caps, far) is None
