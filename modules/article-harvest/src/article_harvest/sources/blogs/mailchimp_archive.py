from __future__ import annotations

import re

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ..rss import make_rss_source

MAILCHIMP_FEED = "https://us7.campaign-archive.com/feed?u=6507bf4e4c2df3fdbae6ef738&id=547725049b"

_MAILCHIMP_STRIP_TAGS: set[str] = {
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
}

_MAILCHIMP_BATCH_BREAK_RE = re.compile(r"(\b[FSW]\d{4})\s{2,}\[")


def mailchimp_archive_html_to_markdown(html: str) -> str:
    """
    Mailchimp archive pages are table-layout HTML emails. Naively converting the full HTML to
    Markdown
    produces enormous Markdown tables (mostly empty layout cells), which our verifier flags as
    `content_placeholder`.

    Strategy:
    - Extract only Mailchimp's text blocks (`.mcnTextContent`).
    - Strip table tags during conversion so we keep text/links without Markdown table artifacts.
    - Drop the unsubscribe/footer block.
    - Lightly post-process to reflow YC Launchpad items (batch codes like F2025/S2025/W2025).
    """
    soup = BeautifulSoup(html or "", "lxml")
    blocks = soup.select(".mcnTextContent")
    if not blocks:
        return md(html or "")

    parts: list[str] = []
    for block in blocks:
        rendered = md(block.decode_contents(), strip=_MAILCHIMP_STRIP_TAGS)
        rendered = _normalize_markdown(rendered)
        if not rendered:
            continue
        lowered = rendered.lower()
        if "unsubscribe" in lowered or "update your preferences" in lowered:
            continue
        parts.append(rendered)

    combined = "\n\n".join(parts).strip()
    combined = combined.replace("\u00a0", " ")
    combined = _MAILCHIMP_BATCH_BREAK_RE.sub(r"\1\n\n[", combined)
    return combined.strip()


def _normalize_markdown(text: str) -> str:
    lines = [line.rstrip() for line in (text or "").splitlines()]
    # Collapse leading/trailing empty lines and compress large empty runs.
    out: list[str] = []
    empty_run = 0
    for line in lines:
        if not line.strip():
            empty_run += 1
            if empty_run <= 2:
                out.append("")
            continue
        empty_run = 0
        out.append(line)
    return "\n".join(out).strip()


def source():
    return make_rss_source(
        "mailchimp-archive",
        "Mailchimp Archive",
        MAILCHIMP_FEED,
        html_to_markdown=mailchimp_archive_html_to_markdown,
    )
