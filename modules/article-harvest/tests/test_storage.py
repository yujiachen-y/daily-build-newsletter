from __future__ import annotations

import json

from article_harvest.models import AggregationItem, BlogItem, Source
from article_harvest.storage import Storage


def test_save_blog_items_and_manifest(tmp_path):
    storage = Storage(tmp_path)
    source = Source(
        id="test-blog",
        name="Test Blog",
        kind="blog",
        method="rss",
        fetch=lambda ctx: [],
    )
    items = [BlogItem(title="Hello", url="https://example.com/hello")]
    stored = storage.save_blog_items(source, items)
    assert len(stored) == 1
    manifest_path = storage.manifest_path(source.id)
    assert manifest_path.exists()
    records = [json.loads(line) for line in manifest_path.read_text().splitlines()]
    assert records[0]["title"] == "Hello"

    stored_again = storage.save_blog_items(source, items)
    assert stored_again == []


def test_save_snapshot_and_iterate(tmp_path):
    storage = Storage(tmp_path)
    source = Source(
        id="test-agg",
        name="Test Agg",
        kind="aggregation",
        method="api",
        fetch=lambda ctx: [],
    )
    items = [AggregationItem(title="Entry", url="https://example.com")]
    storage.save_snapshot(source, items)
    records = storage.iter_snapshot_records(source)
    assert len(records) == 1
    assert records[0].title == "Entry"
