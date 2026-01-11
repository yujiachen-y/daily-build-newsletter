from __future__ import annotations

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from readability import Document


def extract_markdown(html: str) -> str:
    if not html.strip():
        raise ValueError("Empty HTML")
    try:
        doc = Document(html)
        content_html = doc.summary(html_partial=True)
    except Exception:
        content_html = html
    soup = BeautifulSoup(content_html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    markdown = md(str(soup), heading_style="ATX")
    cleaned = markdown.strip()
    if len(cleaned) < 20:
        raise ValueError("Extracted content too short")
    return cleaned
