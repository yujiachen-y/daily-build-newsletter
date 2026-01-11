from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from ..models import ItemCandidate, Source
from ..url_slug import normalize_url
from .base import AdapterError


def _apply_query(url: str, params: dict[str, Any]) -> str:
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


@dataclass
class ReleasebotRelease:
    item_key: str
    candidate: ItemCandidate
    markdown: str


class ReleasebotAdapter:
    def __init__(self) -> None:
        self._markdown_by_key: dict[str, str] = {}

    def discover(self, source: Source, session: requests.Session) -> list[ItemCandidate]:
        data_url = source.config.get("data_url")
        if not data_url:
            raise AdapterError("Missing data_url in source config")
        limit = int(source.config.get("limit") or 10)
        offset_param = source.config.get("offset_param") or "offset"
        offset_value = source.config.get("offset")
        max_pages = source.config.get("max_pages")

        releases: list[ReleasebotRelease] = []
        seen_ids: set[str] = set()
        current_offset = offset_value
        pages = 0

        while True:
            url = (
                _apply_query(data_url, {offset_param: current_offset})
                if current_offset is not None
                else data_url
            )
            response = session.get(url, timeout=20)
            if response.status_code >= 400:
                raise AdapterError(f"HTTP {response.status_code}")
            payload = response.json()
            root = _extract_release_root(payload)
            page_releases = root.get("releases") or []
            for release in page_releases:
                release_id = release.get("id") or release.get("slug")
                if release_id is None:
                    continue
                release_key = str(release_id)
                if release_key in seen_ids:
                    continue
                seen_ids.add(release_key)
                parsed = _parse_release(release)
                if parsed is None:
                    continue
                releases.append(parsed)
                if len(releases) >= limit:
                    break
            if len(releases) >= limit:
                break
            next_offset = root.get("nextOffset")
            if next_offset is None or next_offset == current_offset:
                break
            current_offset = next_offset
            pages += 1
            if max_pages is not None and pages >= int(max_pages):
                break

        candidates = []
        for release in releases:
            self._markdown_by_key[release.item_key] = release.markdown
            candidates.append(release.candidate)
        return candidates

    def fetch_detail(self, candidate: ItemCandidate, session: requests.Session) -> str:
        markdown = self._markdown_by_key.get(candidate.item_key)
        if markdown is None:
            raise AdapterError("Missing cached content for release")
        escaped = escape(markdown)
        return f"<article><div>{escaped}</div></article>"


def _extract_release_root(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload.get("nodes", [])
    for node in nodes:
        data = node.get("data") if isinstance(node, dict) else None
        if not isinstance(data, list) or not data:
            continue
        root = decode_devalue_data(data)
        if isinstance(root, dict) and "releases" in root:
            return root
    raise AdapterError("Releasebot data missing releases")


def _parse_release(release: dict[str, Any]) -> ReleasebotRelease | None:
    product = release.get("product") or {}
    vendor = product.get("vendor") or {}
    vendor_slug = vendor.get("slug") or "vendor"
    product_slug = product.get("slug") or "product"
    release_id = release.get("id") or release.get("slug")
    if release_id is None:
        return None
    item_key = f"releasebot:{vendor_slug}:{product_slug}:{release_id}"
    source_url = None
    source = release.get("source")
    if isinstance(source, dict):
        source_url = source.get("source_url")
    canonical_url = normalize_url(source_url) if source_url else None
    detail_url = canonical_url
    if not detail_url:
        detail_url = f"https://releasebot.io/updates/{vendor_slug}/{product_slug}"

    release_details = release.get("release_details") or {}
    release_name = (
        release_details.get("release_name")
        or release_details.get("release_number")
        or release.get("slug")
        or "Release"
    )
    product_name = product.get("display_name") or vendor.get("display_name")
    title = f"{product_name} — {release_name}" if product_name else str(release_name)
    summary = release_details.get("release_summary")
    published_at = release.get("release_date") or release.get("created_at")

    formatted = release.get("formatted_content") or ""
    if not formatted.strip():
        summary_text = summary or ""
        if summary_text.strip():
            formatted = f"# {title}\n\n{summary_text}"
        else:
            formatted = f"# {title}\n\nNo release details provided."

    candidate = ItemCandidate(
        item_key=item_key,
        canonical_url=detail_url,
        title=title,
        author=None,
        published_at=published_at,
        summary=summary,
        detail_url=detail_url,
    )
    return ReleasebotRelease(item_key=item_key, candidate=candidate, markdown=formatted)
