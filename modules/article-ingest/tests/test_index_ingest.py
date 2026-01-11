from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

from article_ingest.cli import build_parser
from article_ingest.index_fetchers import (
    _apply_query,
    _collect_hn_comments,
    _collect_lobsters_comments,
    _decode_devalue_data,
    _fetch_hf_papers_entries,
    _fetch_hn_entries,
    _fetch_lobsters_entries,
    _fetch_product_hunt_entries,
    _fetch_releasebot_entries,
    _parse_github_trending_html,
)
from article_ingest.index_ingest import run_index_source
from article_ingest.index_models import (
    IndexComment,
    IndexEntry,
    IndexFetchResult,
    IndexFetchStats,
)
from article_ingest.index_render import render_daily_markdown
from article_ingest.index_storage import write_daily_markdown, write_index_stats
from article_ingest.run_logger import RunLogger


@dataclass
class _StubRequestor:
    items: dict[int, dict]

    def get_json(self, url: str) -> dict:
        item_id = int(url.rsplit("/", 1)[-1].split(".")[0])
        return self.items[item_id]


class _JsonRequestor:
    def __init__(self, payloads: dict[str, object]) -> None:
        self.payloads = payloads

    def get_json(self, url: str) -> object:
        return self.payloads[url]


class _BytesRequestor:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def get_bytes(self, url: str) -> bytes:
        return self.payload


def test_collect_hn_comments_bfs_limit():
    items = {
        1: {"type": "comment", "by": "alice", "time": 100, "text": "root", "kids": [3]},
        2: {"type": "comment", "by": "bob", "time": 101, "text": "root2"},
        3: {"type": "comment", "by": "carol", "time": 102, "text": "child"},
    }
    requestor = _StubRequestor(items)
    comments = _collect_hn_comments(requestor, [1, 2], max_count=2)
    assert len(comments) == 2
    assert comments[0].author == "alice"
    assert comments[0].depth == 0
    assert comments[1].author == "bob"
    assert comments[1].depth == 0


def test_collect_lobsters_comments_depth():
    data = [
        {"depth": 0, "comment_plain": "Top", "commenting_user": {"username": "a"}},
        {"depth": 1, "comment_plain": "Child", "commenting_user": "b"},
    ]
    comments = _collect_lobsters_comments(data)
    assert [comment.depth for comment in comments] == [0, 1]
    assert comments[0].author == "a"
    assert comments[1].author == "b"


def test_parse_github_trending_html():
    html = """
    <article class="Box-row">
      <h2><a href="/owner/repo">owner / repo</a></h2>
      <span class="d-inline-block float-sm-right">1,234 stars today</span>
    </article>
    """
    entries = _parse_github_trending_html(html)
    assert len(entries) == 1
    assert entries[0].title == "owner / repo"
    assert entries[0].url == "https://github.com/owner/repo"
    assert entries[0].score == 1234


def test_fetch_hn_entries_sort_and_external_link():
    mapping = {
        "https://hacker-news.firebaseio.com/v0/topstories.json": [1, 2],
        "https://hacker-news.firebaseio.com/v0/item/1.json": {
            "title": "First",
            "by": "alice",
            "time": 1,
            "descendants": 10,
            "kids": [],
        },
        "https://hacker-news.firebaseio.com/v0/item/2.json": {
            "title": "Second",
            "by": "bob",
            "time": 2,
            "descendants": 1,
            "kids": [],
            "url": "https://example.com/post",
        },
    }
    requestor = _JsonRequestor(mapping)
    entries = _fetch_hn_entries(requestor)
    assert [entry.title for entry in entries] == ["First", "Second"]
    assert entries[0].external_link_missing is True
    assert entries[0].url.endswith("item?id=1")
    assert entries[1].external_link_missing is False


def test_fetch_lobsters_entries_reads_story_json(monkeypatch):
    entries = [
        {
            "title": "First",
            "comments": "https://lobste.rs/s/first",
            "published": "2026-01-10T00:00:00+00:00",
        },
        {
            "title": "Second",
            "comments": "https://lobste.rs/s/second",
            "link": "https://example.com/second",
            "published": "2026-01-09T00:00:00+00:00",
        },
    ]
    monkeypatch.setattr(
        "article_ingest.index_fetchers.feedparser.parse",
        lambda _: SimpleNamespace(bozo=False, entries=entries),
    )
    requestor = _JsonRequestor(
        {
            "https://lobste.rs/s/first.json": {
                "comment_count": 5,
                "score": 10,
                "created_at": "2026-01-10T00:00:00+00:00",
                "submitter_user": {"username": "alice"},
                "comments": [
                    {
                        "depth": 0,
                        "comment_plain": "Nice",
                        "commenting_user": {"username": "bob"},
                        "created_at": "2026-01-10T01:00:00+00:00",
                    }
                ],
            },
            "https://lobste.rs/s/second.json": {
                "comment_count": 1,
                "score": 2,
                "created_at": "2026-01-09T00:00:00+00:00",
                "submitter_user": "carol",
                "comments": [],
            },
        }
    )
    results = _fetch_lobsters_entries(requestor)
    assert [entry.title for entry in results] == ["First", "Second"]
    assert results[0].external_link_missing is True
    assert results[1].external_link_missing is False
    assert results[0].comments[0].author == "bob"
    assert results[1].author == "carol"


def test_fetch_releasebot_entries_from_payload():
    payload = {
        "nodes": [
            {
                "data": [
                    {
                        "releases": [
                            {
                                "product": {
                                    "display_name": "Widget",
                                    "slug": "widget",
                                    "vendor": {"display_name": "Acme", "slug": "acme"},
                                },
                                "release_details": {
                                    "release_name": "v1",
                                    "release_summary": "Summary text",
                                },
                                "source": {"source_url": "https://example.com/release"},
                                "release_date": "2026-01-11T00:00:00+00:00",
                                "formatted_content": "### Notes\n\n- change",
                            }
                        ]
                    }
                ]
            }
        ]
    }
    requestor = _JsonRequestor({"https://releasebot.io/updates/__data.json": payload})
    entries = _fetch_releasebot_entries(requestor)
    assert len(entries) == 1
    assert entries[0].title == "Widget — v1"
    assert entries[0].url == "https://example.com/release"
    assert entries[0].summary == "Summary text"
    assert "### Notes" in (entries[0].details or "")


def test_fetch_hf_papers_entries():
    requestor = _JsonRequestor(
        {
            "https://huggingface.co/api/daily_papers": [
                {
                    "title": "Paper A",
                    "paper": {
                        "id": "abc",
                        "authors": [{"name": "Alice"}],
                        "upvotes": 3,
                    },
                }
            ]
        }
    )
    entries = _fetch_hf_papers_entries(requestor)
    assert len(entries) == 1
    assert entries[0].author == "Alice"
    assert entries[0].url.endswith("/papers/abc")


def test_fetch_product_hunt_entries(monkeypatch):
    monkeypatch.setattr(
        "article_ingest.index_fetchers.feedparser.parse",
        lambda _: SimpleNamespace(
            bozo=False,
            entries=[
                {
                    "title": "Tool",
                    "link": "https://example.com",
                    "summary": "Short summary",
                    "tags": [{"term": "AI"}],
                }
            ],
        ),
    )
    requestor = _BytesRequestor(b"<xml/>")
    entries = _fetch_product_hunt_entries(requestor)
    assert len(entries) == 1
    assert entries[0].title == "Tool"
    assert entries[0].summary == "Short summary"
    assert entries[0].tags == ["AI"]


def test_index_storage_writes_files(tmp_path):
    markdown_path = write_daily_markdown(tmp_path, "hn", "# demo\n", "2026-01-11")
    assert markdown_path.exists()
    stats = IndexFetchStats(requests=2, errors=0, duration_ms=5)
    stats_path = write_index_stats(
        tmp_path,
        "hn",
        "2026-01-11",
        stats,
        items_count=1,
        comments_count=2,
        errors=[],
        skipped=False,
    )
    payload = json.loads(stats_path.read_text(encoding="utf-8"))
    assert payload["items_count"] == 1
    assert payload["skipped"] is False


def test_run_index_source_writes_and_skips(tmp_path, monkeypatch):
    run_date = "2026-01-11"

    def fake_fetch_index_entries(slug: str):
        stats = IndexFetchStats(requests=1, errors=0, duration_ms=5)
        entry = IndexEntry(title="Demo", url="https://example.com")
        return IndexFetchResult(entries=[entry], stats=stats, errors=[])

    monkeypatch.setattr("article_ingest.index_ingest.fetch_index_entries", fake_fetch_index_entries)
    monkeypatch.setattr("article_ingest.index_ingest.local_run_date", lambda: run_date)
    logger = RunLogger(tmp_path, 1)

    run_index_source(tmp_path, logger, "hn")
    daily_path = tmp_path / "daily" / "hn" / f"{run_date}.md"
    assert daily_path.exists()

    run_index_source(tmp_path, logger, "hn")
    stats_path = tmp_path / "index" / "hn" / f"{run_date}.json"
    payload = json.loads(stats_path.read_text(encoding="utf-8"))
    assert payload["skipped"] is True


def test_apply_query_and_decode_devalue():
    query = _apply_query("https://example.com/path?a=1", {"b": "2"})
    assert query == "https://example.com/path?a=1&b=2"
    decoded = _decode_devalue_data([{"foo": "bar"}])
    assert decoded == {"foo": "bar"}


def test_render_daily_markdown_includes_meta_and_comments():
    entry = IndexEntry(
        title="Example",
        url="https://example.com",
        author="someone",
        published_at="2026-01-01T00:00:00+00:00",
        score=5,
        comments_count=2,
        comments=[
            IndexComment(depth=0, author="a", body="hello", created_at="2026-01-01"),
            IndexComment(depth=1, author="b", body="child", created_at=None),
        ],
    )
    stats = IndexFetchStats(requests=3, errors=0, duration_ms=5)
    markdown = render_daily_markdown("hn", [entry], stats, [], "2026-01-11")
    assert "source_slug: \"hn\"" in markdown
    assert "fetch_stats" in markdown
    assert "## Example" in markdown
    assert "meta:" in markdown
    assert "### Comments" in markdown


def test_cli_type_flags():
    parser = build_parser()
    args = parser.parse_args(["ingest", "--type", "index"])
    assert args.type == "index"
    args = parser.parse_args(["source", "list", "--type", "content"])
    assert args.type == "content"
