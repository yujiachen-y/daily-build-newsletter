from __future__ import annotations

import pytest
from helpers import DummyResponse, DummySession, rss_entry

from app_radar import apple
from app_radar.http import FetchError
from app_radar.storage import Storage, read_json, read_jsonl


def test_parse_rss_ranks_and_single_entry_feed():
    feed = {
        "feed": {
            "entry": [
                rss_entry("1", "Alpha", "A Inc", "2026-01-02"),
                rss_entry("2", "Beta", "B Inc", "2020-05-06"),
            ]
        }
    }
    rows = apple.parse_rss(feed, "us", "6013", "topgrossingapplications")
    assert [(r["rank"], r["app_id"], r["release_date"]) for r in rows] == [
        (1, "1", "2026-01-02"),
        (2, "2", "2020-05-06"),
    ]
    single = {"feed": {"entry": rss_entry("9", "Solo", "S", "2026-02-03")}}
    assert apple.parse_rss(single, "fr", "6012", "topfreeapplications")[0]["app_id"] == "9"
    assert apple.parse_rss({"feed": {}}, "fr", "6012", "topfreeapplications") == []


def test_parse_lookup_keeps_software_only_and_trims_description():
    data = {
        "results": [
            {
                "wrapperType": "software",
                "trackId": 5,
                "trackName": "Alpha",
                "sellerName": "A",
                "userRatingCount": 120,
                "releaseDate": "2026-01-02T08:00:00Z",
                "description": "line one\n\nline two " + "x" * 300,
            },
            {"wrapperType": "artist", "artistId": 7},
        ]
    }
    rows = apple.parse_lookup(data, "us")
    assert len(rows) == 1
    assert rows[0]["app_id"] == "5" and rows[0]["ratings"] == 120
    assert rows[0]["release_date"] == "2026-01-02"
    assert rows[0]["description_head"].startswith("line one line two")
    assert len(rows[0]["description_head"]) == apple.DESCRIPTION_HEAD


def test_lookup_targets_only_young_apps():
    rows = [
        {"country": "us", "app_id": "1", "release_date": "2026-10-01"},
        {"country": "us", "app_id": "2", "release_date": "2020-01-01"},
        {"country": "cn", "app_id": "3", "release_date": None},
    ]
    assert apple.lookup_targets(rows, "2026-11-05", 365) == {"us": ["1"]}


def _handler(method, url, kwargs):
    if "/rss/" in url:
        if "/fr/" in url:
            return DummyResponse(503, text="busy")
        return DummyResponse(
            json_data={
                "feed": {
                    "entry": [
                        rss_entry("1", "Young", "Y", "2026-09-01"),
                        rss_entry("2", "Old", "O", "2015-01-01"),
                    ]
                }
            }
        )
    if "lookup" in url:
        return DummyResponse(
            json_data={
                "results": [
                    {
                        "wrapperType": "software",
                        "trackId": 1,
                        "trackName": "Young",
                        "userRatingCount": 40,
                        "releaseDate": "2026-09-01T07:00:00Z",
                    },
                ]
            }
        )
    raise AssertionError(url)


def test_fetch_day_writes_snapshots_and_records_failures(tmp_path):
    storage = Storage(tmp_path)
    session = DummySession(_handler)
    run = apple.fetch_day(
        session,
        storage,
        "2026-11-05",
        countries=["us", "fr"],
        genres=["6013"],
        sleep=lambda _: None,
    )
    rows = read_jsonl(storage.charts_path("2026-11-05"))
    assert len(rows) == 4  # two us charts x two entries; fr failed
    assert {f["kind"] for f in run["failures"]} == {"chart"}
    assert len(run["failures"]) == 2
    lookup_calls = [url for _, url, _ in session.calls if "lookup" in url]
    assert lookup_calls == ["https://itunes.apple.com/lookup?id=1&country=us"]
    assert read_jsonl(storage.lookups_path("2026-11-05"))[0]["ratings"] == 40
    assert read_json(storage.run_path("2026-11-05"))["chart_rows"] == 4


def test_fetch_day_refuses_to_write_an_empty_snapshot(tmp_path):
    storage = Storage(tmp_path)
    session = DummySession(lambda *_: DummyResponse(404, text="gone"))
    with pytest.raises(FetchError):
        apple.fetch_day(
            session, storage, "2026-11-05", countries=["us"], genres=["6013"], sleep=lambda _: None
        )
    assert not storage.charts_path("2026-11-05").exists()
