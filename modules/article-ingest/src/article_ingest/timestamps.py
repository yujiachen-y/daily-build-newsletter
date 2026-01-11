from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
