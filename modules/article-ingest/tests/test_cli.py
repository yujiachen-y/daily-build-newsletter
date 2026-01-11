from __future__ import annotations

import sys

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
    return run_id, item_id


def test_cli_commands(monkeypatch, tmp_path, capsys):
    seed_store(tmp_path)

    monkeypatch.setattr(cli, "Ingestor", FakeIngestor)
    monkeypatch.setattr(cli, "Importer", FakeImporter)

    run_cli(["--data-root", str(tmp_path), "source", "list"], monkeypatch)
    assert "demo" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "items", "--source", "demo"], monkeypatch)
    assert "item_id" in capsys.readouterr().out

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

    run_cli(["--data-root", str(tmp_path), "item", "show", "1"], monkeypatch)
    assert "versions" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "item", "content", "1"], monkeypatch)
    assert "hello" in capsys.readouterr().out
    run_cli(["--data-root", str(tmp_path), "item", "comments", "1"], monkeypatch)
    assert "comments" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "ingest"], monkeypatch)
    assert "ingest complete" in capsys.readouterr().out

    run_cli(["--data-root", str(tmp_path), "import"], monkeypatch)
    assert "import complete" in capsys.readouterr().out
