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
        if not content_html.strip():
            content_html = html
        elif not BeautifulSoup(content_html, "lxml").get_text(strip=True):
            content_html = html
    except Exception:
        content_html = html
    soup = BeautifulSoup(content_html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    markdown = md(str(soup), heading_style="ATX")
    cleaned = markdown.strip()
    if not cleaned:
        raise ValueError("Extracted content empty")
    return cleaned
