from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def stable_item_key(canonical_url: str | None) -> str:
    if canonical_url:
        return canonical_url
    return hashlib.sha1("".encode("utf-8")).hexdigest()


def slugify(value: str, max_length: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    if not cleaned:
        cleaned = "item"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip("-") or "item"
    return cleaned


def item_slug(item_key: str) -> str:
    parts = urlsplit(item_key)
    if parts.scheme and parts.netloc:
        base = f"{parts.netloc}{parts.path}"
        base = unquote(base)
    else:
        base = item_key
    slug = slugify(base, max_length=60)
    suffix = hashlib.sha1(item_key.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{suffix}"
