from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from .front_matter import build_front_matter, split_front_matter
from .text_processing import normalize_markdown
from .url_slug import item_slug, slugify

IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def content_dir(root: Path, source_slug: str, item_key: str, version_index: int) -> Path:
    source_dir = slugify(source_slug, max_length=40)
    item_dir = item_slug(item_key)
    return root / "content" / source_dir / item_dir / f"v{version_index}"


def write_markdown(
    root: Path,
    source_slug: str,
    item_key: str,
    version_index: int,
    markdown: str,
    front_matter_fields: dict[str, Any],
    filename: str = "content.md",
) -> Path:
    directory = content_dir(root, source_slug, item_key, version_index)
    directory.mkdir(parents=True, exist_ok=True)
    _, body = split_front_matter(markdown)
    front_matter = build_front_matter(front_matter_fields)
    content = front_matter + normalize_markdown(body)
    content_path = directory / filename
    content_path.write_text(content, encoding="utf-8")
    return content_path


def download_assets(
    root: Path,
    source_slug: str,
    item_key: str,
    version_index: int,
    markdown: str,
    base_url: str | None,
    session: requests.Session,
) -> tuple[str, list[dict[str, Any]]]:
    assets_dir = content_dir(root, source_slug, item_key, version_index) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, Any]] = []

    def replace(match: re.Match) -> str:
        url = match.group(1).strip()
        resolved = urljoin(base_url, url) if base_url else url
        if not resolved.startswith("http"):
            return match.group(0)
        filename = f"asset-{len(assets) + 1}"
        try:
            response = session.get(resolved, timeout=15)
            if response.status_code >= 400:
                assets.append(
                    {
                        "url": resolved,
                        "local_path": None,
                        "status": f"http-{response.status_code}",
                    }
                )
                return match.group(0)
            content_type = response.headers.get("content-type", "")
            extension = ""
            if "/" in content_type:
                extension = "." + content_type.split("/")[-1].split(";")[0]
            local_path = assets_dir / f"{filename}{extension}"
            local_path.write_bytes(response.content)
            assets.append(
                {
                    "url": resolved,
                    "local_path": str(local_path),
                    "status": "stored",
                    "mime": content_type,
                    "size": len(response.content),
                }
            )
            rel_path = f"assets/{local_path.name}"
            return match.group(0).replace(url, rel_path)
        except requests.RequestException:
            assets.append({"url": resolved, "local_path": None, "status": "error"})
            return match.group(0)

    updated = IMAGE_PATTERN.sub(replace, markdown)
    return updated, assets
