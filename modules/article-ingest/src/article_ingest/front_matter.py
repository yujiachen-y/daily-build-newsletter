from __future__ import annotations

import json
from typing import Any


def yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(str(value), ensure_ascii=True)


def build_front_matter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {yaml_value(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def split_front_matter(markdown: str) -> tuple[str | None, str]:
    if not markdown.startswith("---\n"):
        return None, markdown
    end = markdown.find("\n---\n", 4)
    if end == -1:
        return None, markdown
    front = markdown[: end + 5]
    body = markdown[end + 5 :]
    return front, body
