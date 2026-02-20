from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from article_harvest.errors import FetchError
from article_harvest.ingest import _as_blog_items, ingest_all, ingest_source
from article_harvest.models import AggregationItem, BlogItem, Source
from article_harvest.storage import Storage


def _make_source(source_id="test-src", kind="aggregation", items=None, raises=None):
    def _fetch(ctx):
        if raises:
            raise raises
        return items or []

    return Source(id=source_id, name="Test Source", kind=kind, method="api", fetch=_fetch)


def _agg_items(n=2):
    return [
        AggregationItem(title=f"Item {i}", url=f"https://example.com/{i}", rank=i)
        for i in range(1, n + 1)
    ]


def _blog_items(n=2):
    return [
        BlogItem(
            title=f"Blog {i}",
            url=f"https://example.com/blog/{i}",
            content_markdown=f"Content {i}",
        )
        for i in range(1, n + 1)
    ]


# -- _as_blog_items --


def test_as_blog_items_valid():
    items = _blog_items(2)
    result = _as_blog_items(items)
    assert len(result) == 2
    assert all(isinstance(item, BlogItem) for item in result)


def test_as_blog_items_rejects_non_blog():
    items = _agg_items(1)
    with pytest.raises(FetchError, match="non-blog item"):
        _as_blog_items(items)


# -- ingest_all / ingest_source --


@patch("article_harvest.ingest.create_session")
@patch("article_harvest.ingest.list_sources")
def test_ingest_all_aggregation(mock_list_sources, mock_create_session, tmp_path):
    mock_create_session.return_value = MagicMock()
    source = _make_source(items=_agg_items(3))
    mock_list_sources.return_value = [source]

    storage = Storage(data_root=tmp_path)
    report = ingest_all(storage=storage)

    assert len(report["successes"]) == 1
    assert report["successes"][0]["stored"] == 3
    assert len(report["failures"]) == 0
    assert "run_id" in report


@patch("article_harvest.ingest.create_session")
@patch("article_harvest.ingest.list_sources")
def test_ingest_all_blog(mock_list_sources, mock_create_session, tmp_path):
    mock_create_session.return_value = MagicMock()
    source = _make_source(source_id="test-blog", kind="blog", items=_blog_items(2))
    mock_list_sources.return_value = [source]

    storage = Storage(data_root=tmp_path)
    report = ingest_all(storage=storage)

    assert len(report["successes"]) == 1
    assert report["successes"][0]["fetched"] == 2
    assert len(report["failures"]) == 0


@patch("article_harvest.ingest.create_session")
@patch("article_harvest.ingest.get_source")
def test_ingest_source_success(mock_get_source, mock_create_session, tmp_path):
    mock_create_session.return_value = MagicMock()
    source = _make_source(items=_agg_items(2))
    mock_get_source.return_value = source

    storage = Storage(data_root=tmp_path)
    report = ingest_source("test-src", storage=storage)

    assert len(report["successes"]) == 1
    assert report["successes"][0]["stored"] == 2


@patch("article_harvest.ingest.create_session")
@patch("article_harvest.ingest.list_sources")
def test_ingest_all_empty_items_records_failure(mock_list_sources, mock_create_session, tmp_path):
    mock_create_session.return_value = MagicMock()
    source = _make_source(items=[])
    mock_list_sources.return_value = [source]

    storage = Storage(data_root=tmp_path)
    report = ingest_all(storage=storage)

    assert len(report["failures"]) == 1
    assert "no items" in report["failures"][0]["error"]
