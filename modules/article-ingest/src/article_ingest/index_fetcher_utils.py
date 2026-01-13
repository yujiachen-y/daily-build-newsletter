from __future__ import annotations

from typing import Any

from .index_models import IndexFetchError


def apply_query(url: str, params: dict[str, Any]) -> str:
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v is not None})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def decode_devalue_data(data: list[Any]) -> Any:
    def resolve_value(value: Any) -> Any:
        if isinstance(value, list):
            return [
                resolve_ref(item)
                if isinstance(item, int) and not isinstance(item, bool) and item >= 0
                else resolve_value(item)
                for item in value
            ]
        if isinstance(value, dict):
            return {
                key: resolve_ref(item)
                if isinstance(item, int) and not isinstance(item, bool) and item >= 0
                else resolve_value(item)
                for key, item in value.items()
            }
        return value

    def resolve_ref(index: int) -> Any:
        return resolve_value(data[index])

    if not data:
        return None
    return resolve_value(data[0])


def extract_release_root(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload.get("nodes", [])
    for node in nodes:
        data = node.get("data") if isinstance(node, dict) else None
        if not isinstance(data, list) or not data:
            continue
        root = decode_devalue_data(data)
        if isinstance(root, dict) and "releases" in root:
            return root
    raise IndexFetchError("Releasebot data missing releases")
