from __future__ import annotations

import re

_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(value: str, max_length: int = 80) -> str:
    cleaned = value.strip().lower()
    cleaned = _slug_re.sub("-", cleaned)
    cleaned = cleaned.strip("-")
    if not cleaned:
        return "item"
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[:max_length].rstrip("-")
