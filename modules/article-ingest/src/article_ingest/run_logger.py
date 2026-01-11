from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .timestamps import now_utc


class RunLogger:
    def __init__(self, root: Path, run_id: int) -> None:
        self.log_path = root / "logs" / f"run-{run_id}.log"
        self.failures_path = root / "failures" / f"run-{run_id}.jsonl"

    def log(self, message: str) -> None:
        line = f"{now_utc()} {message}\n"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def failure(self, record: dict[str, Any]) -> None:
        record_with_time = {"occurred_at": now_utc(), **record}
        self.failures_path.parent.mkdir(parents=True, exist_ok=True)
        with self.failures_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record_with_time, ensure_ascii=True) + "\n")
