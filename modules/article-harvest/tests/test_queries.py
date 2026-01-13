from __future__ import annotations

from datetime import datetime

from article_harvest.models import AggregationItem, BlogItem, Source
from article_harvest.queries import query_by_archive_date, query_by_keyword, query_by_source
from article_harvest.storage import Storage


def test_query_by_source_keyword_and_date(tmp_path):
    storage = Storage(tmp_path)
    blog_source = Source(
        id="blog",
        name="Blog",
        kind="blog",
        method="rss",
        fetch=lambda ctx: [],
    )
    agg_source = Source(
        id="agg",
        name="Agg",
        kind="aggregation",
        method="api",
        fetch=lambda ctx: [],
    )

    storage.save_blog_items(blog_source, [BlogItem(title="Hello LLM", url="https://x.com")])
    storage.save_snapshot(agg_source, [AggregationItem(title="Daily", url="https://y.com")])

    blog_records = query_by_source(storage, blog_source)
    assert len(blog_records) == 1

    keyword_records = query_by_keyword(storage, [blog_source, agg_source], "LLM")
    assert len(keyword_records) == 1

    today = datetime.utcnow().date().isoformat()
    date_records = query_by_archive_date(storage, [blog_source, agg_source], on=today)
    assert len(date_records) == 2
