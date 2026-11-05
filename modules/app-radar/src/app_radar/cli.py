from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from . import apple, backtest, dataxapi, signals, supply
from .http import FetchError, create_session
from .report import build_report, write_report
from .storage import Storage, module_root, read_jsonl

DEFAULT_KEYWORDS = module_root() / "config" / "keywords.json"
DEFAULT_BACKTEST = module_root() / "config" / "backtest.json"
DEFAULT_SUPPLY = module_root() / "config" / "supply.json"


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(prog="app-radar")
    parser.add_argument("--data-dir", type=Path, help="Override data directory")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_day(p: argparse.ArgumentParser) -> None:
        p.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD (local)")

    fetch = sub.add_parser("fetch", help="Snapshot App Store charts and young-app lookups")
    add_day(fetch)
    fetch.add_argument("--countries", type=_csv, default=list(apple.COUNTRIES))
    fetch.add_argument("--genres", type=_csv, default=list(apple.GENRES))

    report = sub.add_parser("report", help="Compute signals and write the day's report")
    add_day(report)

    indices = sub.add_parser("indices", help="Fetch Chinese indices via DataXAPI (paid)")
    indices.add_argument("--config", type=Path, default=DEFAULT_KEYWORDS)
    indices.add_argument("--force", action="store_true", help="Ignore min_interval_days")

    sup = sub.add_parser("supply", help="Count look-alike launches for the day's themes")
    add_day(sup)
    sup.add_argument("--config", type=Path, default=DEFAULT_SUPPLY)

    run = sub.add_parser(
        "run", help="fetch + indices (if DATAXAPI_API_KEY is set) + supply + report"
    )
    add_day(run)
    run.add_argument("--config", type=Path, default=DEFAULT_KEYWORDS)
    run.add_argument("--supply-config", type=Path, default=DEFAULT_SUPPLY)

    bt = sub.add_parser("backtest", help="Back-test trend signals against past app waves")
    bt.add_argument("--config", type=Path, default=DEFAULT_BACKTEST)
    bt.add_argument("--refresh", action="store_true", help="Ignore cached series")

    args = parser.parse_args()
    storage = Storage(args.data_dir)

    if args.command == "fetch":
        return _fetch(storage, args.date, args.countries, args.genres)
    if args.command == "report":
        return _report(storage, args.date)
    if args.command == "indices":
        return _indices(storage, args.config, force=args.force)
    if args.command == "backtest":
        return _backtest(storage, args.config, refresh=args.refresh)
    if args.command == "supply":
        return _supply(storage, args.date, args.config)
    rc = _fetch(storage, args.date, list(apple.COUNTRIES), list(apple.GENRES))
    if rc:
        return rc
    _indices(storage, args.config, force=False)  # optional and paid: never fail the run
    _supply(storage, args.date, args.supply_config)  # optional: never fail the run
    return _report(storage, args.date)


def _fetch(storage: Storage, day: str, countries: list[str], genres: list[str]) -> int:
    try:
        run = apple.fetch_day(create_session(), storage, day, countries=countries, genres=genres)
    except FetchError as exc:
        print(f"!! fetch failed: {exc}", file=sys.stderr)
        return 1
    failures = run.pop("failures")
    print(json.dumps({**run, "failures": len(failures)}, ensure_ascii=False))
    for failure in failures[:5]:
        print(f"!! {failure['kind']}: {failure['error']}", file=sys.stderr)
    return 0


def _indices(storage: Storage, config_path: Path, *, force: bool) -> int:
    key = os.environ.get("DATAXAPI_API_KEY")
    if not key:
        print("indices: DATAXAPI_API_KEY not set, skipped")
        return 0
    config = dataxapi.load_config(config_path)
    summary = dataxapi.fetch_indices(create_session(), storage, key, config, force=force)
    print(json.dumps({"indices": summary}, ensure_ascii=False))
    return 1 if summary["aborted"] else 0


def _report(storage: Storage, day: str) -> int:
    try:
        report = build_report(storage, day)
    except FileNotFoundError as exc:
        print(f"!! {exc}", file=sys.stderr)
        return 1
    md_path, json_path = write_report(storage, report)
    print(md_path)
    print(json_path)
    return 0


def _supply(storage: Storage, day: str, config_path: Path) -> int:
    rows = read_jsonl(storage.charts_path(day))
    if not rows:
        print(f"!! supply: no chart snapshot for {day}", file=sys.stderr)
        return 1
    themes = signals.themes(day, rows, read_jsonl(storage.lookups_path(day)), young_days=365)
    result = supply.run_supply(
        create_session(), storage, day, themes, supply.load_config(config_path)
    )
    failures = result.pop("failures")
    print(
        json.dumps(
            {
                "supply": {k: result[k] for k in ("requests", "seconds")},
                "items": len(result["items"]),
                "failures": len(failures),
            }
        )
    )
    for failure in failures[:5]:
        print(
            f"!! supply {failure['country']} {failure['term']}: {failure['error']}", file=sys.stderr
        )
    return 0


def _backtest(storage: Storage, config_path: Path, *, refresh: bool) -> int:
    config = backtest.load_config(config_path)
    # GitHub search allows 30 requests a minute with a token, 10 without.
    token = os.environ.get("GITHUB_TOKEN")
    result = backtest.run_backtest(
        create_session(), storage, config, refresh=refresh, github_token=token
    )
    md_path, json_path = backtest.write_backtest(storage, result)
    print(md_path)
    print(json_path)
    for failure in result["failures"][:5]:
        print(f"!! {failure['kind']} {failure['key']}: {failure['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
