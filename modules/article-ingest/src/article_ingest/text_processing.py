from __future__ import annotations

import hashlib
import re

_BLOCK_PATTERNS = (
    re.compile(r"you can.?t perform that action at this time", re.IGNORECASE),
    re.compile(r"attention required", re.IGNORECASE),
    re.compile(r"checking your browser before accessing", re.IGNORECASE),
    re.compile(r"enable javascript and cookies to continue", re.IGNORECASE),
    re.compile(r"please enable javascript", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
    re.compile(r"verify you are human", re.IGNORECASE),
)


def normalize_markdown(markdown: str) -> str:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    return normalized.strip() + "\n"


def hash_content(markdown: str) -> str:
    normalized = normalize_markdown(markdown)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def detect_blocked_text(markdown: str) -> str | None:
    if not markdown:
        return None
    text = " ".join(markdown.split())
    if not text:
        return None
    word_count = len(text.split())
    if word_count > 120 or len(text) > 1200:
        return None
    for pattern in _BLOCK_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    for pattern in _BLOCK_PATTERNS:
        match = pattern.search(ascii_text)
        if match:
            return match.group(0)
    return None
