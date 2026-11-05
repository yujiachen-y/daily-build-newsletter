from __future__ import annotations

from datetime import date, timedelta

from helpers import DummyResponse, DummySession

from app_radar import supply
from app_radar.report import render_markdown
from app_radar.storage import Storage, read_json

DAY = "2026-11-06"


def _days_ago(n: int) -> str:
    return (date.fromisoformat(DAY) - timedelta(days=n)).isoformat()


def _app(app_id, name, age, ratings=0):
    return {"app_id": app_id, "name": name, "release_date": _days_ago(age), "ratings": ratings}


def test_chain_bigrams_rebuilds_phrases():
    assert supply.chain_bigrams(["オ通", "デオ", "ビデ", "通話"]) == ["ビデオ通話"]
    assert supply.chain_bigrams(["食记", "饮食"]) == ["饮食记"]
    assert supply.chain_bigrams(["漫剧"]) == ["漫剧"]
    assert supply.chain_bigrams(["ビデ", "デオ", "オ通", "通話", "話で"]) == ["ビデオ通話"]


def test_theme_query_for_latin_and_cjk_themes():
    latin = supply.theme_query({"tokens": ["stories"], "countries": ["us", "jp"]})
    assert latin["label"] == "stories"
    # English names travel, so the other Latin-script storefronts are checked too.
    assert list(latin["countries"]) == ["us", "jp", "gb", "de", "fr"]
    assert latin["countries"]["us"]["pattern"] == r"(?=.*\bstories\b)"

    cjk = supply.theme_query({"tokens": ["オ通", "デオ", "ビデ", "通話"], "countries": ["jp"]})
    assert cjk["label"] == "ビデオ通話"
    assert list(cjk["countries"]) == ["jp"]


def test_measure_stages():
    base = {"quarter": 10, "half": 20, "prior_half": 10}
    crowded = [_app(str(i), "Peptide Log", 30) for i in range(10)]
    m = supply.measure(crowded, "peptide", DAY, "us", base)
    assert m["stage"] == "crowded" and m["quarter"] == 10
    # 10 launches against 0 the half year before, while the baseline only doubled.
    assert m["growth_vs_baseline"] == 5.0 and m["accelerating"]

    winner = [
        _app("1", "Shot Tracker", 300, 34000),
        _app("2", "Shot Diary", 100, 50),
        _app("3", "Shot Log", 900, 90000),  # big but older than two years
    ]
    m = supply.measure(winner, "shot", DAY, "us", base)
    assert m["stage"] == "winner"
    assert m["winner"]["app_id"] == "1" and m["top"]["app_id"] == "3"

    scattered = [_app(str(i), "Shot", 200, 10) for i in range(4)]
    assert supply.measure(scattered, "shot", DAY, "us", base)["stage"] == "scattered"
    assert supply.measure(scattered[:2], "shot", DAY, "us", base)["stage"] == "empty"
    assert supply.measure(scattered, "shot", DAY, "us", None)["growth_vs_baseline"] is None


def test_capped_results_only_support_crowded():
    filler = [_app(f"f{i}", "Old Story", 2000) for i in range(195)]
    few_recent = filler + [_app("n1", "Story AI", 10)]
    assert supply.measure(few_recent, "story", DAY, "us", None, capped=True)["stage"] == "unknown"
    many_recent = filler + [_app(f"n{i}", "Story AI", 10) for i in range(10)]
    assert supply.measure(many_recent, "story", DAY, "us", None, capped=True)["stage"] == "crowded"


def _result(i, name, age, ratings=0):
    released = (date.fromisoformat(DAY) - timedelta(days=age)).isoformat()
    return {
        "trackId": i,
        "trackName": name,
        "releaseDate": f"{released}T00:00:00Z",
        "userRatingCount": ratings,
    }


def _handler(method, url, kwargs):
    term = kwargs["params"]["term"]
    if term == "metronome":
        results = [_result(i, "Metronome", 100) for i in range(4)]
        results += [_result(10 + i, "Metronome", 250) for i in range(2)]
    elif term == "stories":
        results = [_result(100 + i, f"AI Stories {i}", 20) for i in range(12)]
    else:
        results = [_result(200, "Other", 400)]
    return DummyResponse(json_data={"results": results})


def test_run_supply_caches_and_renders(tmp_path):
    storage = Storage(tmp_path)
    session = DummySession(_handler)
    config = {
        "baseline": {"us": [{"term": "metronome", "pattern": "metronom"}]},
        "watch": [
            {
                "id": "x",
                "label": "关注项",
                "countries": {"us": {"terms": ["other"], "pattern": "other"}},
            }
        ],
    }
    themes = [{"tokens": ["stories"], "countries": ["us"]}]
    result = supply.run_supply(session, storage, DAY, themes, config, pause=0, sleep=lambda s: None)
    assert result["baseline"]["us"] == {"quarter": 0, "half": 4, "prior_half": 2}
    stories = result["items"][0]["countries"]["us"]
    assert stories["stage"] == "crowded" and stories["quarter"] == 12
    assert result["items"][1]["countries"]["us"]["stage"] == "empty"
    assert read_json(storage.supply_path(DAY))["items"][0]["key"] == "stories"

    calls = len(session.calls)
    supply.run_supply(session, storage, DAY, themes, config, pause=0, sleep=lambda s: None)
    assert len(session.calls) == calls  # searches younger than 7 days come from the cache

    report = {
        "day": DAY,
        "young_days": 365,
        "history": {"snapshots_before_today": 0, "span_days": 0, "base_day": None},
        "coverage": [("us", "6013", "topfreeapplications")],
        "run": {},
        "themes": [],
        "young_grossing": [],
        "young_free": [],
        "moves": None,
        "rating_growth": [],
        "indices": [],
        "supply": result,
    }
    text = render_markdown(report)
    assert "## 6. 供给阶段" in text
    assert "| stories（搜「stories」） | 美国 | 已扎堆，加速 | 12 |" in text
    assert "美国 4/2" in text
