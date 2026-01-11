from __future__ import annotations

from pathlib import Path


def module_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_root(root_override: Path | None = None) -> Path:
    return root_override if root_override is not None else module_root() / "data"


def ensure_data_dirs(root: Path) -> None:
    (root / "content").mkdir(parents=True, exist_ok=True)
    (root / "daily").mkdir(parents=True, exist_ok=True)
    (root / "index").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "failures").mkdir(parents=True, exist_ok=True)
    (root / "inbox").mkdir(parents=True, exist_ok=True)
