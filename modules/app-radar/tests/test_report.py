from __future__ import annotations

import re

import pytest
from helpers import chart_row, lookup_row

from app_radar import signals
from app_radar.report import build_report, render_markdown, write_report
from app_radar.storage import Storage, write_jsonl

G = signals.GROSSING


def _seed(storage: Storage) -> None:
    base = [
        chart_row("cn", "6013", G, 60, "1", "AI拍照算热量", "s1", "2026-09-01"),
        chart_row("cn", "6013", G, 8, "2", "拍照记热量", "s2", "2026-09-01"),
    ]
    today = [
        chart_row("cn", "6013", G, 6, "1", "AI拍照算热量", "s1", "2026-09-01"),
        chart_row("cn", "6013", G, 30, "3", "热量拍照识别", "s3", "2026-10-20"),
        chart_row("cn", "6013", G, 1, "9", "老牌健康", "big", "2014-01-01"),
    ]
    write_jsonl(storage.charts_path("2026-10-29"), base)
    write_jsonl(
        storage.lookups_path("2026-10-29"),
        [lookup_row("cn", "1", "AI拍照算热量", 100, "2026-09-01")],
    )
    write_jsonl(storage.charts_path("2026-11-05"), today)
    write_jsonl(
        storage.lookups_path("2026-11-05"),
        [lookup_row("cn", "1", "AI拍照算热量", 450, "2026-09-01")],
    )


def test_report_end_to_end(tmp_path):
    storage = Storage(tmp_path)
    _seed(storage)
    report = build_report(storage, "2026-11-05")
    assert report["history"] == {
        "snapshots_before_today": 1,
        "span_days": 7,
        "base_day": "2026-10-29",
    }
    assert [a["app_id"] for a in report["young_grossing"]] == ["1", "3"]
    assert report["moves"]["climbers"][0]["climb"] == 54
    assert report["rating_growth"][0]["delta"] == 350

    md = render_markdown(report)
    assert "AI拍照算热量" in md and "升 54" in md
    assert "首次进这张榜" in md  # app 3 entered, and 7 days of history is enough to say so
    # Obsidian turns "word #12" into a tag; the report must never produce that pattern
    assert not re.search(r"[A-Za-z一-龥]\s#[0-9]", md)

    md_path, json_path = write_report(storage, report)
    assert md_path.endswith("2026-11-05.md") and json_path.endswith("2026-11-05.json")


def test_first_day_report_says_history_is_missing(tmp_path):
    storage = Storage(tmp_path)
    write_jsonl(
        storage.charts_path("2026-11-05"),
        [chart_row("us", "6013", G, 3, "1", "New", "n", "2026-10-01")],
    )
    md = render_markdown(build_report(storage, "2026-11-05"))
    assert "没有更早的快照" in md
    assert "本期跳过" in md


def test_report_requires_a_snapshot(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_report(Storage(tmp_path), "2026-11-05")
