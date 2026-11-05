from __future__ import annotations

from helpers import DummyResponse, DummySession

from app_radar import backtest
from app_radar.history import month_range
from app_radar.storage import Storage

MONTHS = month_range("2020-01", "2023-12")


def _app(app_id, name, release, ratings=0):
    return {"app_id": app_id, "name": name, "release_date": release, "ratings": ratings}


def test_onsets_need_year_over_year_doubling_above_floor():
    series = {m: 1000 for m in MONTHS}
    # A January spike every year is seasonal and must not count.
    for year in (2020, 2021, 2022, 2023):
        series[f"{year}-01"] = 5000
    for m in month_range("2022-06", "2023-12"):
        series[m] = 4000
    # The January windows (mean 2,333) clear this floor but did not double year over year.
    found = backtest.onsets(series, MONTHS, floor=2000)
    assert found[0] == "2022-06"
    assert not [m for m in found if m[5:] in ("01", "02", "03")]


def test_onsets_treat_missing_months_as_zero_and_respect_gap():
    series = {m: 5000 for m in month_range("2021-06", "2023-12")}
    found = backtest.onsets(series, MONTHS, floor=3000)
    # Article appears in 2021-06; the 3-month mean reaches the floor in 2021-07.
    assert found[0] == "2021-07"
    assert all(backtest.months_between(a, b) >= 12 for a, b in zip(found, found[1:]))


def test_peak_and_halving():
    series = {m: 100 for m in MONTHS}
    series.update({"2021-05": 900, "2021-06": 900, "2021-07": 900})
    assert backtest.rolling_peak(series, MONTHS) == ("2021-07", 900)
    assert backtest.halved_after_peak(series, MONTHS) == "2021-09"


def test_month_helpers():
    assert backtest.months_between("2021-07", "2024-05-29") == 34
    assert backtest.months_between("2021-07", "2023-Q2") == 21
    assert backtest.shift_month("2021-01", -24) == "2019-01"
    assert backtest.months_between(None, "2024-01") is None


def test_first_winner_excludes_apps_older_than_cutoff():
    apps = backtest.match_apps(
        [
            _app("1", "Old Calorie GLP-1", "2016-01-01", 90000),
            _app("2", "Shot GLP-1 Tracker", "2024-05-29", 34000),
            _app("3", "GLP-1 Diary", "2025-01-01", 40000),
            _app("4", "Weather", "2024-01-01", 99999),
            _app("2", "Shot GLP-1 Tracker", "2024-05-29", 34000),  # same app from 2nd term
        ],
        "glp",
    )
    assert [a["app_id"] for a in apps] == ["1", "2", "3"]
    winner, early = backtest.first_winner(apps, 5000, "2019-07-01")
    assert winner["app_id"] == "2"
    assert [a["app_id"] for a in early] == ["1"]


def test_release_counts_and_clone_wave():
    apps = [_app(str(i), "x", "2024-02-01") for i in range(3)]
    apps += [_app(str(i + 10), "x", "2025-05-01") for i in range(10)]
    quarters = backtest.release_counts(apps, "quarter")
    assert quarters == {"2024-Q1": 3, "2025-Q2": 10}
    assert backtest.clone_wave(quarters, 10) == "2025-Q2"
    assert backtest.release_counts(apps, "year") == {"2024": 3, "2025": 10}


def test_surge_years_are_scaled_by_baseline():
    baseline = {"2022": 10, "2023": 10, "2024": 10, "2025": 40}
    counts = {"2022": 2, "2023": 2, "2024": 8, "2025": 16}
    # 2024 quadruples against a flat baseline; 2025 doubles but the baseline quadruples.
    assert backtest.surge_years(counts, baseline, range(2023, 2026)) == [2024]


def test_hit_stats_score_only_full_windows():
    stats = backtest.hit_stats(["2018-03", "2021-07", "2025-01"], [2019, 2023], last_year=2026)
    assert stats == {"onsets": 3, "scored": 2, "hits": 2, "surges": 2, "preceded": 2}


def _handler(method, url, kwargs):
    params = kwargs.get("params") or {}
    if "wikimedia.org" in url:
        if "Missing" in url:
            return DummyResponse(404, text="not found")
        items = [
            {"timestamp": f"{m.replace('-', '')}0100", "views": 500 if m < "2021-06" else 6000}
            for m in MONTHS
        ]
        return DummyResponse(json_data={"items": items})
    if "algolia" in url:
        return DummyResponse(json_data={"nbHits": 4})
    if "itunes.apple.com/search" in url:
        if params["term"] == "calculator":
            results = [
                {"trackId": i, "trackName": "Calculator", "releaseDate": f"{y}-03-01T00:00:00Z"}
                for i, y in enumerate([2021, 2022, 2023, 2023])
            ]
        else:
            results = [
                {
                    "trackId": 1,
                    "trackName": "Topic Tracker",
                    "releaseDate": "2022-02-01T00:00:00Z",
                    "userRatingCount": 8000,
                },
            ] + [
                {
                    "trackId": 10 + i,
                    "trackName": f"Topic {i}",
                    "releaseDate": "2023-05-01T00:00:00Z",
                }
                for i in range(6)
            ]
        return DummyResponse(json_data={"results": results})
    raise AssertionError(url)


def test_run_backtest_end_to_end(tmp_path):
    config = {
        "start_month": "2020-01",
        "end_month": "2023-12",
        "github_start_month": "2023-01",
        "baseline": [{"term": "calculator", "pattern": "calculator"}],
        "waves": [
            {
                "id": "w",
                "label": "话题",
                "kind": "health",
                "wiki": ["en.wikipedia:Topic", "de.wikipedia:Missing"],
                "hn": ["topic"],
                "apps": [{"country": "us", "terms": ["topic"], "pattern": "topic", "clone_min": 5}],
            }
        ],
        "controls": [
            {"id": "c", "wiki": "en.wikipedia:Topic", "term": "topic", "pattern": "topic"}
        ],
    }
    session = DummySession(_handler)
    storage = Storage(tmp_path)
    result = backtest.run_backtest(
        session, storage, config, sleep=lambda s: None, log=lambda m: None
    )
    wave = result["waves"][0]
    assert wave["first_onset"] == "2021-07"
    supply = wave["supply"][0]
    assert supply["winner"]["release_date"] == "2022-02-01"
    assert ["2022-02", "us 第一个赢家上架"] in wave["timeline"]
    assert wave["timeline"][0] == ["2021-07", "wiki 最早起势（en.wikipedia:Topic）"]
    hn_call = next(k for m, u, k in session.calls if "algolia" in u)
    assert hn_call["params"]["typoTolerance"] == "false"
    assert supply["clone_wave"] == "2023-Q2"
    missing = [s for s in wave["signals"] if s["key"] == "de.wikipedia:Missing"][0]
    assert missing["first_month"] is None and missing["onsets"] == []
    assert result["controls"][0]["matched"] == 7

    calls = len(session.calls)
    backtest.run_backtest(session, storage, config, sleep=lambda s: None, log=lambda m: None)
    assert len(session.calls) == calls  # second run is served from the cache

    md_path, _ = backtest.write_backtest(storage, result)
    text = md_path.read_text(encoding="utf-8")
    assert "话题" in text and "2021-07" in text


def test_quiet_candidates_need_recent_onset_and_low_supply():
    def control(cid, onsets, years):
        return {"id": cid, "signal": {"onsets": onsets}, "years": years}

    result = {
        "span": ["2015-07", "2026-10"],
        "controls": [
            control("quiet", ["2025-08"], {"2025": 2}),
            control("crowded", ["2025-08"], {"2025": 40}),
            control("old", ["2019-01"], {"2025": 0}),
        ],
    }
    assert [c["id"] for c in backtest.quiet_candidates(result)] == ["quiet"]
