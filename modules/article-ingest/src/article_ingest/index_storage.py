from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .index_models import IndexFetchStats
from .timestamps import now_utc


def local_run_date() -> str:
    return datetime.now().astimezone().date().isoformat()


def write_daily_markdown(root: Path, source_slug: str, content: str, run_date: str) -> Path:
    daily_dir = root / "daily" / source_slug
    daily_dir.mkdir(parents=True, exist_ok=True)
    path = daily_dir / f"{run_date}.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_index_stats(
    root: Path,
    source_slug: str,
    run_date: str,
    stats: IndexFetchStats,
    items_count: int,
    comments_count: int,
    errors: list[str],
    skipped: bool = False,
) -> Path:
    stats_dir = root / "index" / source_slug
    stats_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_slug": source_slug,
        "run_date_local": run_date,
        "generated_at": now_utc(),
        "items_count": items_count,
        "comments_count": comments_count,
        "fetch_stats": {
            "requests": stats.requests,
            "duration_ms": stats.duration_ms,
            "errors": stats.errors,
        },
        "errors": errors,
        "skipped": skipped,
    }
    path = stats_dir / f"{run_date}.json"
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return path
