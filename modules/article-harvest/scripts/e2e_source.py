from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from article_harvest.sources.registry import get_source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    source = get_source(args.source)
    failures = 0
    for run_idx in range(1, args.runs + 1):
        print(f"[e2e] run {run_idx}/{args.runs} for {source.id}")
        ok = _run_ingest(args.source)
        if not ok:
            failures += 1
            continue
        if not _validate_output(source.id, source.kind):
            failures += 1
    if failures:
        print(f"[e2e] {failures} run(s) failed", file=sys.stderr)
        return 1
    print("[e2e] all runs ok")
    return 0


def _run_ingest(source_id: str) -> bool:
    cmd = [sys.executable, "-m", "article_harvest.cli", "ingest", "--source", source_id]
    env = dict(**_base_env())
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        return False
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout)
        print("[e2e] invalid JSON report", file=sys.stderr)
        return False
    failures = report.get("failures") or []
    if any(entry.get("source_id") == source_id for entry in failures if isinstance(entry, dict)):
        print(f"[e2e] source {source_id} reported failure", file=sys.stderr)
        return False
    successes = report.get("successes") or []
    if not any(entry.get("source_id") == source_id for entry in successes if isinstance(entry, dict)):
        print(f"[e2e] source {source_id} missing success record", file=sys.stderr)
        return False
    return True


def _validate_output(source_id: str, kind: str) -> bool:
    data_root = Path(__file__).resolve().parents[1] / "data"
    source_root = data_root / "sources" / source_id
    if kind == "aggregation":
        snapshot_path = source_root / "snapshots" / f"{date.today().isoformat()}.json"
        if not snapshot_path.exists():
            print(f"[e2e] missing snapshot: {snapshot_path}", file=sys.stderr)
            return False
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        items = payload.get("items") or []
        if not items:
            print("[e2e] snapshot items empty", file=sys.stderr)
            return False
        return True

    manifest_path = source_root / "manifest.jsonl"
    if not manifest_path.exists():
        print(f"[e2e] missing manifest: {manifest_path}", file=sys.stderr)
        return False
    lines = [line for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]
    if not lines:
        print("[e2e] manifest empty", file=sys.stderr)
        return False
    return True


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return env


if __name__ == "__main__":
    raise SystemExit(main())
