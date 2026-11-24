from __future__ import annotations

import gzip
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def module_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_data_root() -> Path:
    override = os.environ.get("PLUGIN_RADAR_DATA")
    return Path(override) if override else module_root() / "data"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def local_day(ts: datetime) -> str:
    """The newsletter's day: the machine's local date (Asia/Singapore on the author's Mac)."""
    return ts.astimezone().date().isoformat()


class Storage:
    """Snapshots keyed by source and local day. Re-running a day overwrites that day's files.

    data/
      snapshots/<source>/<day>.json   parsed observation (origin: live or wayback)
      raw/<day>/<name>.gz             the response the snapshot was parsed from
      runs/<day>.json                 per-source status of the day's run
      reports/<day>.{md,json}
    """

    def __init__(self, data_root: Path | None = None) -> None:
        self.root = data_root or default_data_root()

    def snapshot_path(self, source: str, day: str) -> Path:
        return self.root / "snapshots" / source / f"{day}.json"

    def raw_path(self, day: str, name: str) -> Path:
        return self.root / "raw" / day / f"{_safe_name(name)}.gz"

    def run_path(self, day: str) -> Path:
        return self.root / "runs" / f"{day}.json"

    def report_md_path(self, day: str) -> Path:
        return self.root / "reports" / f"{day}.md"

    def report_json_path(self, day: str) -> Path:
        return self.root / "reports" / f"{day}.json"

    def snapshot_days(self, source: str) -> list[str]:
        folder = self.root / "snapshots" / source
        if not folder.exists():
            return []
        return sorted(p.stem for p in folder.glob("*.json") if DATE_RE.match(p.stem))

    def load_snapshot(self, source: str, day: str) -> dict[str, Any] | None:
        return read_json(self.snapshot_path(source, day))

    def history(self, source: str, before_day: str) -> list[dict[str, Any]]:
        """Snapshots of earlier days, oldest first."""
        out = []
        for d in self.snapshot_days(source):
            if d < before_day:
                snap = self.load_snapshot(source, d)
                if snap:
                    out.append(snap)
        return out

    def save_raw(self, day: str, name: str, text: str) -> str:
        path = self.raw_path(day, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write(text)
        return str(path.relative_to(self.root))


def _safe_name(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", text.strip()) or "_"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
