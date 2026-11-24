from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

import requests

from . import catalogs, github, hubs, skillssh
from .catalogs import CATALOGS
from .http import create_session
from .report import build_report, write_report
from .storage import Storage, iso, utc_now, write_json

GITHUB_SOURCES_FROM_TRENDING = 200


def main() -> int:
    parser = argparse.ArgumentParser(prog="plugin-radar")
    parser.add_argument("--data-dir", type=Path, help="Override data directory")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_day(p: argparse.ArgumentParser) -> None:
        p.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD (local)")

    run = sub.add_parser("run", help="Fetch every source, backfill history, write the report")
    add_day(run)
    run.add_argument("--no-backfill", action="store_true", help="Skip Internet Archive backfill")
    rep = sub.add_parser("report", help="Rebuild the report from the day's snapshots")
    add_day(rep)
    bf = sub.add_parser("backfill", help="Seed skills.sh history from the Internet Archive")
    add_day(bf)

    args = parser.parse_args()
    storage = Storage(args.data_dir)
    if args.command == "run":
        return _run(storage, args.date, backfill=not args.no_backfill)
    if args.command == "report":
        return _report(storage, args.date)
    written = skillssh.backfill(create_session(), storage, args.date)
    print(f"backfilled skills.sh days: {', '.join(written) or 'none needed'}")
    return 0


def _run(storage: Storage, day: str, *, backfill: bool) -> int:
    session = create_session()
    token = os.environ.get("GITHUB_TOKEN") or None
    statuses: dict[str, Any] = {}
    started = utc_now()

    jobs: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("skillssh", lambda: skillssh.fetch(session, storage, day)),
        ("skillhub", lambda: hubs.fetch_skillhub(session, storage, day)),
        ("clawhub", lambda: hubs.fetch_clawhub(session, storage, day)),
        ("catalog-kimi", lambda: catalogs.fetch_kimi(session, storage, day)),
        ("claude-installs", lambda: catalogs.fetch_claude_stats(session, storage, day)),
    ]
    for key in CATALOGS:
        jobs.append(
            (
                f"catalog-{key}",
                lambda k=key: catalogs.fetch_catalog(session, storage, day, k, token=token),
            )
        )
    snaps: dict[str, dict[str, Any]] = {}
    for name, job in jobs:
        statuses[name] = _attempt(name, job, storage, day, snaps)

    _codex_descriptions(session, snaps, storage, day)

    if backfill:
        try:
            written = skillssh.backfill(session, storage, day)
            statuses["wayback-backfill"] = {"status": "ok", "days": written}
        except Exception as exc:  # noqa: BLE001 - history is optional
            statuses["wayback-backfill"] = {"status": "failed", "error": _err(exc)}

    repos = _repos_to_check(snaps)
    try:
        stats = github.repo_stats(session, repos, token)
        statuses["github"] = {"status": "ok", "repos": len(stats), "authenticated": bool(token)}
    except Exception as exc:  # noqa: BLE001 - fall back to recent star counts below
        stats = {}
        statuses["github"] = {"status": "failed", "error": _err(exc)}
    statuses["github"]["carried_from_earlier_days"] = _carry_github(storage, day, repos, stats)
    write_json(
        storage.snapshot_path("github", day),
        {
            "source": "github",
            "day": day,
            "origin": "live",
            "observed_at": iso(utc_now()),
            "authenticated": bool(token),
            "repos": stats,
        },
    )

    write_json(
        storage.run_path(day),
        {
            "day": day,
            "started_at": iso(started),
            "finished_at": iso(utc_now()),
            "sources": statuses,
        },
    )
    for name, info in statuses.items():
        print(f"{name:18s} {info['status']:7s} {info.get('error') or ''}")
    return _report(storage, day)


def _attempt(
    name: str,
    job: Callable[[], dict[str, Any]],
    storage: Storage,
    day: str,
    snaps: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        snap = job()
    except Exception as exc:  # noqa: BLE001 - one source must not sink the run
        info = {"status": "failed", "error": _err(exc), "seconds": round(time.monotonic() - t0, 1)}
        earlier = storage.load_snapshot(name, day)
        if earlier and earlier.get("origin") == "live":  # an earlier run today succeeded
            snaps[name] = earlier
            info.update(status="reused", reused_observed_at=earlier.get("observed_at"))
        return info
    write_json(storage.snapshot_path(name, day), snap)
    snaps[name] = snap
    return {"status": "ok", "seconds": round(time.monotonic() - t0, 1)}


def _codex_descriptions(
    session: requests.Session, snaps: dict[str, Any], storage: Storage, day: str
) -> None:
    snap = snaps.get("catalog-codex")
    if not snap or not snap["added"]:
        return
    descs = catalogs.codex_descriptions(session, [a["name"] for a in snap["added"]])
    for a in snap["added"]:
        a["description"] = a.get("description") or descs.get(a["name"], "")
    write_json(storage.snapshot_path("catalog-codex", day), snap)


def _carry_github(
    storage: Storage, day: str, repos: list[str], stats: dict[str, Any], max_age: int = 7
) -> int:
    """Fill repos not looked up today (no token, rate limit, outage) from the newest earlier
    lookup within `max_age` days. Star counts move slowly; an unchecked repo would otherwise
    drop out of every signal as "unverified"."""
    wanted = {r.lower() for r in repos} - set(stats)
    carried = 0
    for snap in reversed(storage.history("github", day)[-max_age:]):
        for key, value in (snap.get("repos") or {}).items():
            if key in wanted and value is not None:
                stats[key] = {**value, "as_of": value.get("as_of") or snap["day"]}
                wanted.discard(key)
                carried += 1
        if not wanted:
            break
    return carried


def _repos_to_check(snaps: dict[str, Any]) -> list[str]:
    """Trending repos first (the farming check matters most there), then the all-time list."""
    repos: list[str] = []
    s = snaps.get("skillssh")
    if s:
        repos += [r["source"] for r in s["trending"][:GITHUB_SOURCES_FROM_TRENDING]]
        ranked = sorted(s["all_time"].values(), key=lambda r: r["rank"])
        repos += [r["source"] for r in ranked]
    for key in CATALOGS:
        c = snaps.get(f"catalog-{key}")
        if c:
            repos += [a["repo"] for a in c["added"] if a.get("external") and a.get("repo")]
    return [r for r in repos if "/" in r]


def _report(storage: Storage, day: str) -> int:
    try:
        report = build_report(storage, day)
    except Exception as exc:  # noqa: BLE001
        print(f"!! report failed: {_err(exc)}", file=sys.stderr)
        return 1
    md_path, json_path = write_report(storage, report)
    ok = [s["label"] for s in report["sources"].values() if s["status"] == "ok"]
    bad = [s["label"] for s in report["sources"].values() if s["status"] != "ok"]
    print(f"report: {md_path}")
    print(f"        {json_path}")
    print(f"sources ok: {len(ok)}; not ok: {', '.join(bad) or 'none'}")
    return 0


def _err(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:300]


if __name__ == "__main__":
    sys.exit(main())
