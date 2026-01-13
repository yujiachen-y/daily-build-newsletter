from __future__ import annotations

from typing import Any

from ...errors import FetchError
from ...http import get_json
from ...models import AggregationItem, FetchContext, Source

RELEASEBOT_URL = "https://releasebot.io/updates/__data.json"
RELEASEBOT_LIMIT = 10


def source() -> Source:
    return Source(
        id="releasebot",
        name="Releasebot",
        kind="aggregation",
        method="api",
        fetch=fetch_releasebot,
    )


def fetch_releasebot(ctx: FetchContext) -> list[AggregationItem]:
    payload = get_json(ctx.session, RELEASEBOT_URL)
    if not isinstance(payload, dict):
        raise FetchError("Releasebot payload invalid")
    root = _extract_release_root(payload)
    releases = root.get("releases") or []
    items: list[AggregationItem] = []
    for rank, release in enumerate(releases[:RELEASEBOT_LIMIT], start=1):
        product = release.get("product") or {}
        vendor = product.get("vendor") or {}
        product_name = product.get("display_name") or vendor.get("display_name")
        release_details = release.get("release_details") or {}
        release_name = (
            release_details.get("release_name")
            or release_details.get("release_number")
            or release.get("slug")
            or "Release"
        )
        title = f"{product_name} — {release_name}" if product_name else str(release_name)
        source_url = None
        source_meta = release.get("source")
        if isinstance(source_meta, dict):
            source_url = source_meta.get("source_url")
        if not source_url:
            vendor_slug = vendor.get("slug") or "vendor"
            product_slug = product.get("slug") or "product"
            source_url = f"https://releasebot.io/updates/{vendor_slug}/{product_slug}"
        published_at = release.get("release_date") or release.get("created_at")
        summary = release_details.get("release_summary")
        items.append(
            AggregationItem(
                title=title,
                url=source_url,
                published_at=published_at,
                author=vendor.get("display_name"),
                score=None,
                comments_count=None,
                rank=rank,
                discussion_url=None,
                extra={"summary": summary} if summary else {},
            )
        )
    if not items:
        raise FetchError("Releasebot list empty")
    return items


def _extract_release_root(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload.get("nodes", [])
    for node in nodes:
        data = node.get("data") if isinstance(node, dict) else None
        if not isinstance(data, list) or not data:
            continue
        root = _decode_devalue_data(data)
        if isinstance(root, dict) and "releases" in root:
            return root
    raise FetchError("Releasebot data missing releases")


def _decode_devalue_data(data: list[Any]) -> Any:
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
