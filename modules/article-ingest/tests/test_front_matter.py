from __future__ import annotations

from article_ingest.front_matter import build_front_matter, split_front_matter
from article_ingest.storage import write_markdown
from article_ingest.text_processing import normalize_markdown


def test_write_markdown_adds_front_matter(tmp_path):
    front = {
        "item_id": 1,
        "source_id": 2,
        "canonical_url": None,
        "title": "Hello",
        "published_at": None,
        "version_id": 3,
        "content_hash": "abc",
        "extracted_at": "2026-01-11T00:00:00+00:00",
        "run_id": 4,
    }
    content_path = write_markdown(
        tmp_path,
        source_slug="demo",
        item_key="https://example.com/post",
        version_index=1,
        markdown="Body text",
        front_matter_fields=front,
    )
    content = content_path.read_text(encoding="utf-8")
    front_matter, body = split_front_matter(content)
    assert front_matter is not None
    assert "item_id: 1" in front_matter
    assert "canonical_url: null" in front_matter
    assert body.strip().startswith("Body text")


def test_front_matter_roundtrip():
    front = build_front_matter({"title": "Hello"})
    content = front + normalize_markdown("Body")
    head, body = split_front_matter(content)
    assert head is not None
    assert "title" in head
    assert body.strip() == "Body"
