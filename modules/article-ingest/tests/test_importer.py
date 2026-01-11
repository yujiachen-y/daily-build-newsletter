from __future__ import annotations

import json
from pathlib import Path

from article_ingest.front_matter import split_front_matter
from article_ingest.importer import Importer
from article_ingest.store import Store


def test_importer_stores_markdown_with_front_matter(tmp_path):
    store = Store(root=tmp_path)
    store.upsert_source(
        slug="demo",
        name="Demo",
        homepage_url="https://example.com",
        enabled=True,
        policy={},
        config={},
    )

    inbox = tmp_path / "inbox" / "demo"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "post.md").write_text("# Title\n\nHello world", encoding="utf-8")
    (inbox / "post.meta.json").write_text(
        json.dumps(
            {
                "canonical_url": "https://example.com/post",
                "title": "Post",
                "published_at": "2026-01-11T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    importer = Importer(store, root=tmp_path)
    run_id = importer.run()
    assert run_id > 0

    items = store.list_items()
    assert len(items) == 1
    item_id = int(items[0]["id"])
    versions = store.get_item_versions(item_id)
    assert len(versions) == 1
    content_path = versions[0]["content_path"]
    if content_path.startswith("/"):
        content_file = Path(content_path)
    else:
        content_file = tmp_path / content_path
    content = content_file.read_text(encoding="utf-8")
    front, body = split_front_matter(content)
    assert front is not None
    assert "item_id" in front
    assert body.strip().startswith("# Title")
