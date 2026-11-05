from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def module_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_data_root() -> Path:
    override = os.environ.get("APP_RADAR_DATA")
    return Path(override) if override else module_root() / "data"


class Storage:
    """Day-keyed files under data/. Re-running a day overwrites that day's files."""

    def __init__(self, data_root: Path | None = None) -> None:
        self.root = data_root or default_data_root()

    def charts_path(self, day: str) -> Path:
        return self.root / "charts" / f"{day}.jsonl"

    def lookups_path(self, day: str) -> Path:
        return self.root / "lookups" / f"{day}.jsonl"

    def run_path(self, day: str) -> Path:
        return self.root / "runs" / f"{day}.json"

    def report_md_path(self, day: str) -> Path:
        return self.root / "reports" / f"{day}.md"

    def report_json_path(self, day: str) -> Path:
        return self.root / "reports" / f"{day}.json"

    def index_path(self, platform: str, keyword: str) -> Path:
        return self.root / "indices" / platform / f"{_safe_name(keyword)}.json"

    def supply_search_path(self, country: str, term: str) -> Path:
        return self.root / "supply" / "search" / f"{country}_{_safe_name(term)}.json"

    def supply_path(self, day: str) -> Path:
        return self.root / "supply" / f"{day}.json"

    def backtest_raw_path(self, kind: str, key: str) -> Path:
        return self.root / "backtest" / "raw" / kind / f"{_safe_name(key)}.json"

    def backtest_report_path(self, suffix: str) -> Path:
        return self.root / "backtest" / f"report.{suffix}"

    def chart_days(self) -> list[str]:
        folder = self.root / "charts"
        if not folder.exists():
            return []
        return sorted(p.stem for p in folder.glob("*.jsonl") if DATE_RE.match(p.stem))


def _safe_name(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", text.strip()) or "_"


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    tmp.replace(path)
    return count


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
