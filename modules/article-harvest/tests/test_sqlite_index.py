from __future__ import annotations

from article_harvest.models import AggregationItem, BlogItem, Source
from article_harvest.queries import (
    query_by_archive_date,
    query_by_keyword,
    query_by_source,
)
from article_harvest.sqlite_index import rebuild_sqlite_index
from article_harvest.storage import Storage
from article_harvest.time_utils import parse_date


def test_sqlite_rebuild_parity(tmp_path):
    storage = Storage(tmp_path)
    blog_source = Source(
        id="test-blog",
        name="Test Blog",
        kind="blog",
        method="rss",
        fetch=lambda ctx: [],
    )
    agg_source = Source(
        id="test-agg",
        name="Test Agg",
        kind="aggregation",
        method="api",
        fetch=lambda ctx: [],
    )

    storage.save_blog_items(
        blog_source,
        [BlogItem(title="Hello World", url="https://example.com/hello")],
    )
    storage.save_snapshot(
        agg_source,
        [AggregationItem(title="Top Story", url="https://example.com/top")],
    )

    sources = [blog_source, agg_source]
    file_source = query_by_source(storage, blog_source)
    file_keyword = query_by_keyword(storage, sources, "hello")
    archived_date = parse_date(file_source[0].archived_at).isoformat()
    file_archive = query_by_archive_date(
        storage, sources, on=archived_date, source_id=blog_source.id
    )

    report = rebuild_sqlite_index(storage, sources)
    assert report["records"] >= 2

    sqlite_source = query_by_source(storage, blog_source)
    sqlite_keyword = query_by_keyword(storage, sources, "hello")
    sqlite_archive = query_by_archive_date(
        storage,
        sources,
        on=archived_date,
        source_id=blog_source.id,
    )

    assert sqlite_source == file_source
    assert sqlite_keyword == file_keyword
    assert sqlite_archive == file_archive
