from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

from article_ingest import cli
from article_ingest.store import Store


class FakeIngestor:
    def __init__(self, store):
        self.store = store

    def run(self, source_slugs=None):
        return 99


class FakeImporter:
    def __init__(self, store, root=None):
        self.store = store

    def run(self, source_slug=None):
        return 100


def run_cli(args, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["article-ingest", *args])
    cli.main()


def seed_store(tmp_path):
    store = Store(root=tmp_path)
    run_id = store.create_run(status="success")
    source_id = store.upsert_source(
        slug="demo",
        name="Demo",
        homepage_url="https://example.com",
        enabled=True,
        policy={},
        config={},
    )
    item_id, _ = store.upsert_item(
        source_id,
        "demo-1",
        "https://example.com/post",
        "Post",
        "Author",
        "2026-01-11T00:00:00+00:00",
        run_id,
    )
    item_two_id, _ = store.upsert_item(
        source_id,
        "demo-2",
        "https://example.com/other",
        "Other",
        "Author",
        "2026-01-10T00:00:00+00:00",
        run_id,
    )
    content_file = tmp_path / "content.md"
    content_file.write_text("hello", encoding="utf-8")
    (tmp_path / "comments.md").write_text("comments", encoding="utf-8")
    version_id, _ = store.create_item_version(
        item_id,
        "hash",
        "pending",
        "2026-01-11T00:00:00+00:00",
        run_id,
        "Post",
        "2026-01-11T00:00:00+00:00",
        1,
    )
    store.update_version_content_path(version_id, content_file, tmp_path)
    content_file_two = tmp_path / "content-two.md"
    content_file_two.write_text("---\nfront: yes\n---\nworld", encoding="utf-8")
    version_two_id, _ = store.create_item_version(
        item_two_id,
        "hash-2",
        "pending",
        "2026-01-10T00:00:00+00:00",
        run_id,
        "Other",
        "2026-01-10T00:00:00+00:00",
        1,
    )
    store.update_version_content_path(version_two_id, content_file_two, tmp_path)
    return run_id, item_id, item_two_id, source_id


def test_cli_commands(monkeypatch, tmp_path, capsys):
    run_id, item_id, item_two_id, source_id = seed_store(tmp_path)
    store = Store(root=tmp_path)
    missing_id, _ = store.upsert_item(
        source_id,
        "demo-missing",
        "https://example.com/missing",
        "Missing",
        "Author",
        "2026-01-09T00:00:00+00:00",
        run_id,
    )
    store.create_item_version(
        missing_id,
        "hash-missing",
        "missing.md",
        "2026-01-09T00:00:00+00:00",
        run_id,
        "Missing",
        "2026-01-09T00:00:00+00:00",
        1,
    )

    monkeypatch.setattr(cli, "Ingestor", FakeIngestor)
    monkeypatch.setattr(cli, "Importer", FakeImporter)

    run_cli(["--data-root", str(tmp_path), "source", "list"], monkeypatch)
    assert "demo" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "items", "--source", "demo"], monkeypatch)
    assert "item_id" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "items", "--query", "Post"], monkeypatch)
    assert "Post" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "items", "--query", "Other"], monkeypatch)
    assert "Other" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "items", "--query", "Absent"], monkeypatch)
    assert "item_id" not in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "items", "--after", "2026-01-11"], monkeypatch)
    output = capsys.readouterr().out
    assert "Post" in output
    assert "Other" not in output

    run_cli(["--data-root", str(tmp_path), "items", "--since", "2026-01-11"], monkeypatch)
    output = capsys.readouterr().out
    assert "Post" in output
    assert "Other" not in output

    run_cli(["--data-root", str(tmp_path), "items", "--verbose"], monkeypatch)
    output = capsys.readouterr().out
    assert "author=" in output
    assert "snippet=hello" in output

    run_cli(["--data-root", str(tmp_path), "items", "--json"], monkeypatch)
    items_payload = json.loads(capsys.readouterr().out)
    assert len(items_payload) == 3
    assert items_payload[0]["source_slug"] == "demo"

    run_cli(
        [
            "--data-root",
            str(tmp_path),
            "source",
            "add",
            "new",
            "New",
            "https://example.com",
            "--policy",
            "{}",
            "--config",
            "{}",
        ],
        monkeypatch,
    )
    assert "source added" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "runs"], monkeypatch)
    assert "status" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "updates"], monkeypatch)
    assert "updates" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "item", "show", str(item_id)], monkeypatch)
    assert "versions" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "item", str(item_id)], monkeypatch)
    assert "versions" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "item", "content", str(item_id)], monkeypatch)
    assert "hello" in capsys.readouterr().out
    run_cli(["--data-root", str(tmp_path), "item", "comments", str(item_id)], monkeypatch)
    assert "comments" in capsys.readouterr().out

    run_cli(
        [
            "--data-root",
            str(tmp_path),
            "item",
            "content",
            str(item_id),
            str(item_two_id),
            str(missing_id),
            "--json",
        ],
        monkeypatch,
    )
    content_payload = json.loads(capsys.readouterr().out)
    assert len(content_payload) == 3
    assert any(entry.get("content") for entry in content_payload)
    assert any(entry.get("error") for entry in content_payload)

    run_cli(["--data-root", str(tmp_path), "ingest"], monkeypatch)
    assert "ingest complete" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "import"], monkeypatch)
    assert "import complete" in capsys.readouterr().out


def test_parse_relative_hours(monkeypatch):
    fixed = datetime(2026, 1, 11, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz else fixed.replace(tzinfo=None)

    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    result = cli._parse_relative("24 hours ago")
    assert result == fixed - timedelta(hours=24)
