from __future__ import annotations

from datetime import datetime, timedelta, timezone

from helpers import DummyResponse, DummySession

from app_radar import dataxapi
from app_radar.storage import Storage, read_json

NOW = datetime(2026, 11, 5, 1, 0, tzinfo=timezone.utc)
CONFIG = {
    "keywords": ["戒糖", "HRV"],
    "platforms": ["wechat", "douyin", "xiaohongshu"],
    "min_interval_days": 7,
}


def _points(metric, values):
    return [{"date": f"2026-10-{d:02d}T00:00:00Z", metric: v} for d, v in values]


def _handler(method, url, kwargs):
    if "/wechat/" in url:
        keyword = kwargs["params"]["keyword"]
        return DummyResponse(
            json_data={
                "data": {
                    "items": [
                        {
                            "keyword": keyword,
                            "points": _points("composite_index", [(1, 10), (2, 12)]),
                        }
                    ]
                }
            }
        )
    if "/douyin/" in url:
        assert method == "POST"
        items = [
            {"keyword": k.lower(), "points": _points("search_index", [(1, 5)])}
            for k in kwargs["json"]["keywords"]
            if k != "戒糖"
        ]  # 戒糖 not indexed
        return DummyResponse(json_data={"data": {"items": items}})
    if "/xiaohongshu/" in url:
        return DummyResponse(
            json_data={
                "data": {
                    "item": {
                        "keyword": kwargs["params"]["keyword"],
                        "points": _points("search_index", [(1, 7), (2, None)]),
                    }
                }
            }
        )
    raise AssertionError(url)


def test_fetch_indices_batches_douyin_and_stores_series(tmp_path):
    storage = Storage(tmp_path)
    session = DummySession(_handler)
    summary = dataxapi.fetch_indices(session, storage, "k", CONFIG, sleep=lambda _: None, now=NOW)
    assert summary["calls"] == {"wechat": 2, "douyin": 1, "xiaohongshu": 2}
    assert summary["max_cost_usd"] == round(2 * 0.1 + 0.006 + 2 * 0.04, 3)
    assert session.calls[0][2]["headers"]["Authorization"] == "Bearer k"

    hrv = read_json(storage.index_path("douyin", "HRV"))
    assert hrv["points"] == [{"date": "2026-10-01", "value": 5}]
    # not indexed on Douyin: stored empty so it is not re-charged before the interval
    assert read_json(storage.index_path("douyin", "戒糖"))["points"] == []
    xhs = read_json(storage.index_path("xiaohongshu", "戒糖"))
    assert xhs["points"][-1] == {"date": "2026-10-02", "value": None}

    again = dataxapi.fetch_indices(
        DummySession(_handler),
        storage,
        "k",
        CONFIG,
        sleep=lambda _: None,
        now=NOW + timedelta(days=2),
    )
    assert sum(again["calls"].values()) == 0 and again["skipped_not_due"] == 6


def test_merge_series_fills_late_values_but_keeps_known_ones():
    existing = {
        "points": [{"date": "2026-10-01", "value": 3}, {"date": "2026-10-02", "value": None}]
    }
    merged = dataxapi.merge_series(
        existing, [{"date": "2026-10-02", "value": 4}, {"date": "2026-10-01", "value": None}]
    )
    assert merged == [{"date": "2026-10-01", "value": 3}, {"date": "2026-10-02", "value": 4}]


def test_fetch_indices_stops_on_bad_key(tmp_path):
    session = DummySession(lambda *_: DummyResponse(401, text="unauthorized"))
    summary = dataxapi.fetch_indices(
        session, Storage(tmp_path), "bad", CONFIG, sleep=lambda _: None, now=NOW
    )
    assert summary["aborted"] is True
    assert len(session.calls) == 1
