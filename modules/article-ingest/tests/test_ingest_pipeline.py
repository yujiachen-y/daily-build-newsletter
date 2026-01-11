from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from article_ingest.ingest import Ingestor
from article_ingest.models import ItemCandidate
from article_ingest.store import Store


class FakeAdapter:
    def __init__(self, html: str, candidates: list[ItemCandidate]) -> None:
        self._html = html
        self._candidates = candidates

    def discover(self, source, session):
        return list(self._candidates)

    def fetch_detail(self, candidate, session):
        return self._html


class FailingAdapter:
    def __init__(self, candidates: list[ItemCandidate]) -> None:
        self._candidates = candidates

    def discover(self, source, session):
        return list(self._candidates)

    def fetch_detail(self, candidate, session):
        raise RuntimeError("boom")


class CommentAdapter:
    def __init__(self, html: str, candidates: list[ItemCandidate], comments: str) -> None:
        self._html = html
        self._candidates = candidates
        self._comments = comments

    def discover(self, source, session):
        return list(self._candidates)

    def fetch_detail(self, candidate, session):
        return self._html

    def fetch_comments(self, candidate, session, limit=None):
        return self._comments, 1


def _add_source(store: Store) -> None:
    store.upsert_source(
        slug="demo",
        name="Demo",
        homepage_url="https://example.com",
        enabled=True,
        policy={"mode": "html", "always_refetch": True},
        config={},
    )


def test_ingest_creates_version_and_dedup(monkeypatch, tmp_path):
    store = Store(root=tmp_path)
    _add_source(store)

    candidate = ItemCandidate(
        item_key="demo-1",
        canonical_url="https://example.com/post",
        title="Post",
        author="Author",
        published_at="2026-01-11T00:00:00+00:00",
        detail_url="https://example.com/post",
    )
    adapter = FakeAdapter("<html>ok</html>", [candidate])

    monkeypatch.setattr("article_ingest.ingest.adapter_for_mode", lambda mode: adapter)
    monkeypatch.setattr(
        "article_ingest.ingest_fetch.extract_markdown", lambda html: "Hello world " * 5
    )

    ingestor = Ingestor(store, root=tmp_path)
    run_id = ingestor.run(run_type="content")
    items = store.list_items()
    assert len(items) == 1
    item_id = int(items[0]["id"])
    versions = store.get_item_versions(item_id)
    assert len(versions) == 1
    updates = store.get_updates_for_run(run_id)
    assert len(updates) == 1

    run_id2 = ingestor.run(run_type="content")
    versions_after = store.get_item_versions(item_id)
    assert len(versions_after) == 1
    updates_after = store.get_updates_for_run(run_id2)
    assert len(updates_after) == 0


def test_ingest_records_error_on_detail_failure(monkeypatch, tmp_path):
    store = Store(root=tmp_path)
    _add_source(store)

    candidate = ItemCandidate(
        item_key="demo-1",
        canonical_url="https://example.com/post",
        title="Post",
        author=None,
        published_at=None,
        detail_url="https://example.com/post",
    )
    adapter = FailingAdapter([candidate])

    monkeypatch.setattr("article_ingest.ingest.adapter_for_mode", lambda mode: adapter)

    ingestor = Ingestor(store, root=tmp_path)
    ingestor.run(run_type="content")

    items = store.list_items()
    assert len(items) == 1
    item_id = int(items[0]["id"])
    versions = store.get_item_versions(item_id)
    assert versions == []

    errors = store.connect().execute("SELECT * FROM run_errors").fetchall()
    assert len(errors) == 1
    assert errors[0]["url"] == "https://example.com/post"


def test_ingest_writes_comments_sidecar(monkeypatch, tmp_path):
    store = Store(root=tmp_path)
    store.upsert_source(
        slug="comments",
        name="Comments",
        homepage_url="https://example.com",
        enabled=True,
        policy={"mode": "html", "always_refetch": True, "concurrency": 2},
        config={},
    )

    candidate = ItemCandidate(
        item_key="demo-1",
        canonical_url="https://example.com/post",
        title="Post",
        author="Author",
        published_at="2026-01-11T00:00:00+00:00",
        detail_url="https://example.com/post",
        comment_url="https://example.com/post/comments",
    )
    adapter = CommentAdapter("<html>ok</html>", [candidate], "Top comment")

    monkeypatch.setattr("article_ingest.ingest.adapter_for_mode", lambda mode: adapter)
    monkeypatch.setattr(
        "article_ingest.ingest_fetch.extract_markdown", lambda html: "Hello world " * 5
    )

    ingestor = Ingestor(store, root=tmp_path)
    ingestor.run(run_type="content")

    items = store.list_items()
    assert len(items) == 1
    item_id = int(items[0]["id"])
    comments, _ = store.read_sidecar(item_id, None, "comments.md")
    assert "Top comment" in comments


def test_ingest_detects_blocked_content(monkeypatch, tmp_path):
    store = Store(root=tmp_path)
    _add_source(store)

    candidate = ItemCandidate(
        item_key="blocked-1",
        canonical_url="https://example.com/blocked",
        title="Blocked",
        author=None,
        published_at=None,
        detail_url="https://example.com/blocked",
    )
    adapter = FakeAdapter("<html>blocked</html>", [candidate])

    monkeypatch.setattr("article_ingest.ingest.adapter_for_mode", lambda mode: adapter)
    monkeypatch.setattr(
        "article_ingest.ingest_fetch.extract_markdown",
        lambda html: "You can’t perform that action at this time.",
    )

    ingestor = Ingestor(store, root=tmp_path)
    ingestor.run(run_type="content")

    items = store.list_items()
    assert len(items) == 1
    item_id = int(items[0]["id"])
    versions = store.get_item_versions(item_id)
    assert versions == []
    errors = store.connect().execute("SELECT * FROM run_errors").fetchall()
    assert len(errors) == 1
    assert errors[0]["error_code"] == "blocked"


def test_ingest_marks_failed_on_interrupt(monkeypatch, tmp_path):
    store = Store(root=tmp_path)
    ingestor = Ingestor(store, root=tmp_path)

    def _raise_interrupt(_: list[str] | None) -> list:
        raise KeyboardInterrupt

    monkeypatch.setattr(ingestor, "_load_sources", _raise_interrupt)

    with pytest.raises(KeyboardInterrupt):
        ingestor.run(run_type="content")

    row = store.connect().execute("SELECT status FROM runs ORDER BY id DESC").fetchone()
    assert row is not None
    assert row["status"] == "failed"


def test_ingest_cleans_stale_runs(monkeypatch, tmp_path):
    store = Store(root=tmp_path)
    stale_run_id = store.create_run()
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    store.connect().execute(
        "UPDATE runs SET started_at = ?, status = ? WHERE id = ?",
        (old.isoformat(), "running", stale_run_id),
    )
    store.connect().commit()

    ingestor = Ingestor(store, root=tmp_path)
    monkeypatch.setattr(ingestor, "_load_sources", lambda _: [])
    run_id = ingestor.run(run_type="content")
    assert run_id != stale_run_id

    row = store.connect().execute(
        "SELECT status, notes FROM runs WHERE id = ?", (stale_run_id,)
    ).fetchone()
    assert row is not None
    assert row["status"] == "failed"
    assert "stale_run_cleanup" in (row["notes"] or "")


def test_ingest_logs_start_finish_and_heartbeat(monkeypatch, tmp_path):
    store = Store(root=tmp_path)
    ingestor = Ingestor(store, root=tmp_path)
    monkeypatch.setattr("article_ingest.ingest.HEARTBEAT_SECONDS", 0.01)

    def _slow_sources(_):
        time.sleep(0.03)
        return []

    monkeypatch.setattr(ingestor, "_load_sources", _slow_sources)
    run_id = ingestor.run(run_type="content")
    log_path = tmp_path / "logs" / f"run-{run_id}.log"
    contents = log_path.read_text(encoding="utf-8")
    assert "run started" in contents
    assert "run finished" in contents
    assert "heartbeat" in contents
