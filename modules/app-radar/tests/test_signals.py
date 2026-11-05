from __future__ import annotations

from helpers import chart_row, lookup_row

from app_radar import signals

G, F = signals.GROSSING, signals.FREE
DAY = "2026-11-05"


def test_tokenize_name_handles_latin_cjk_and_hangul():
    assert signals.tokenize_name("Quit Sugar: The App for You") == {"quit", "sugar", "you"}
    assert signals.tokenize_name("戒糖打卡") == {"戒糖", "糖打", "打卡"}
    assert signals.tokenize_name("설탕 끊기 앱") == {"설탕", "끊기"}
    assert signals.tokenize_name(None) == set()


def test_first_release_uses_earliest_storefront():
    rows = [chart_row("fr", "6013", G, 1, "1", "A", "a", "2026-10-01")]
    lookups = [lookup_row("us", "1", "A", 10, "2024-01-01")]
    assert signals.first_release_dates(rows, lookups) == {"1": "2024-01-01"}


def test_young_apps_aggregates_placements_and_rating_rate():
    rows = [
        chart_row("us", "6013", G, 12, "1", "Young", "Y", "2026-09-06"),
        chart_row("us", "6013", F, 3, "1", "Young", "Y", "2026-09-06"),
        chart_row("cn", "6013", G, 40, "1", "Young", "Y", "2026-10-06"),
        chart_row("us", "6013", G, 1, "2", "Old", "O", "2012-01-01"),
    ]
    lookups = [
        lookup_row("us", "1", "Young", 600, "2026-09-06"),
        lookup_row("cn", "1", "Young", 30, "2026-10-06"),
    ]
    [app] = signals.young_apps(DAY, rows, lookups, young_days=365)
    assert app["best_grossing"] == 12 and app["best_free"] == 3
    assert app["countries"] == ["cn", "us"]
    assert app["age_days"] == 60  # from the earliest storefront
    assert app["ratings_per_day"] == {"us": 10.0, "cn": 1.0}  # local release dates
    assert app["seller_has_older_app"] is False

    rows.append(chart_row("us", "6012", F, 9, "3", "Old by Y", "Y", "2015-01-01"))
    [app] = signals.young_apps(DAY, rows, lookups, young_days=365)
    assert app["seller_has_older_app"] is True


def test_themes_merge_bigrams_and_skip_category_words():
    young_names = ["AI拍照算热量", "拍照记热量", "热量拍照识别"]
    rows = [
        chart_row("cn", "6013", G, i + 1, str(i), n, f"seller{i}", "2026-08-01")
        for i, n in enumerate(young_names)
    ]
    # three young apps share these words, but four established apps use them too
    rows += [
        chart_row("cn", "6013", F, 10 + i, f"h{i}", "健康管家", f"hs{i}", "2026-08-01")
        for i in range(3)
    ]
    rows += [
        chart_row("cn", "6013", F, 20 + i, f"o{i}", "健康管家", "old", "2016-01-01")
        for i in range(4)
    ]
    found = signals.themes(DAY, rows, [], young_days=365)
    assert len(found) == 1
    assert set(found[0]["tokens"]) >= {"拍照", "热量"}
    assert found[0]["young_apps"] == 3 and found[0]["sellers"] == 3


def test_pick_base_day_takes_earliest_within_window():
    days = ["2026-10-20", "2026-10-30", "2026-11-01", "2026-11-04"]
    assert signals.pick_base_day(DAY, days, 7) == "2026-10-30"
    assert signals.pick_base_day(DAY, ["2026-10-01"], 7) is None


def test_chart_moves_compares_only_charts_present_on_both_days():
    base = [
        chart_row("us", "6013", G, 60, "1", "Climber", "c", "2026-01-01"),
        chart_row("us", "6013", G, 5, "2", "Leaver", "l", "2026-01-01"),
        chart_row("fr", "6013", G, 1, "9", "OnlyBase", "o", "2026-01-01"),
    ]
    today = [
        chart_row("us", "6013", G, 10, "1", "Climber", "c", "2026-01-01"),
        chart_row("us", "6013", G, 30, "3", "Newcomer", "n", "2026-01-01"),
    ]
    moves = signals.chart_moves(DAY, today, base, base, history_span_days=3)
    assert [(m["app_id"], m["climb"]) for m in moves["climbers"]] == [("1", 50)]
    assert [m["app_id"] for m in moves["entered"]] == ["3"]
    assert moves["entered"][0]["first_seen"] is False  # 3 days of history is too short to say
    assert [m["app_id"] for m in moves["dropped"]] == ["2"]  # fr chart missing today: ignored

    long = signals.chart_moves(DAY, today, base, base, history_span_days=10)
    assert long["entered"][0]["first_seen"] is True


def test_rating_growth_rates():
    base = [lookup_row("us", "1", "A", 100, "2026-10-06")]
    now = [lookup_row("us", "1", "A", 400, "2026-10-06")]
    [g] = signals.rating_growth(DAY, "2026-10-29", now, base)
    assert g["delta"] == 300 and g["span_days"] == 7
    assert g["per_day_recent"] == 42.9
    assert g["per_day_lifetime"] == 13.3  # 400 ratings over 30 days
    assert g["acceleration"] == 3.21


def test_index_changes_needs_two_windows_and_skips_nulls():
    points = [{"date": f"2026-10-{d:02d}", "value": 100} for d in range(1, 8)]
    points += [{"date": f"2026-10-{d:02d}", "value": 150} for d in range(8, 15)]
    points += [{"date": "2026-10-15", "value": None}]
    series = [
        {"platform": "wechat", "keyword": "戒糖", "metric": "composite_index", "points": points},
        {"platform": "douyin", "keyword": "短", "metric": "search_index", "points": points[:5]},
    ]
    [change] = signals.index_changes(series)
    assert change["keyword"] == "戒糖"
    assert change["change"] == 0.5
    assert change["last_date"] == "2026-10-14"
