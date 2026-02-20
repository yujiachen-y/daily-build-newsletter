from __future__ import annotations

import json

from article_harvest.verify_data import verify_data_root


def test_verify_data_reports_blog_issues(tmp_path):
    data_root = tmp_path
    source_id = "blog"
    source_root = data_root / "sources" / source_id
    items_root = source_root / "items"
    items_root.mkdir(parents=True)

    ok_id = "ok-1234abcd"
    short_id = "short-1234abcd"
    empty_id = "empty-1234abcd"

    (items_root / ok_id).mkdir()
    ok_content = "hello\\n" * 200
    (items_root / ok_id / "content.md").write_text(ok_content, encoding="utf-8")
    ok_meta = {
        "id": ok_id,
        "source_id": source_id,
        "title": "OK",
        "url": "https://example.com/ok",
        "published_at": None,
        "archived_at": "2026-01-13T00:00:00Z",
        "author": None,
        "summary": None,
        "content_path": f"sources/{source_id}/items/{ok_id}/content.md",
    }
    (items_root / ok_id / "meta.json").write_text(json.dumps(ok_meta), encoding="utf-8")

    (items_root / short_id).mkdir()
    (items_root / short_id / "content.md").write_text("tiny", encoding="utf-8")
    short_meta = dict(ok_meta)
    short_meta.update(
        {
            "id": short_id,
            "title": "Short",
            "url": "https://example.com/short",
            "content_path": f"sources/{source_id}/items/{short_id}/content.md",
        }
    )
    (items_root / short_id / "meta.json").write_text(json.dumps(short_meta), encoding="utf-8")

    (items_root / empty_id).mkdir()
    (items_root / empty_id / "content.md").write_text("", encoding="utf-8")
    empty_meta = dict(ok_meta)
    empty_meta.update(
        {
            "id": empty_id,
            "title": "Empty",
            "url": "https://example.com/empty",
            "content_path": f"sources/{source_id}/items/{empty_id}/content.md",
        }
    )
    (items_root / empty_id / "meta.json").write_text(json.dumps(empty_meta), encoding="utf-8")

    manifest = "\n".join(
        [
            json.dumps({**ok_meta, "id": ok_id}),
            json.dumps({**short_meta, "id": short_id}),
            json.dumps({**empty_meta, "id": empty_id}),
        ]
    )
    (source_root / "manifest.jsonl").write_text(manifest + "\n", encoding="utf-8")

    report = verify_data_root(
        data_root,
        min_content_chars=20,
        max_issues=50,
        include_snippets=True,
    )
    by_type = report["totals"]["issues_by_type"]
    assert by_type.get("content_empty", 0) == 1
    assert by_type.get("content_too_short", 0) == 1


def test_verify_data_reports_aggregation_snapshot_issues(tmp_path):
    data_root = tmp_path
    source_id = "agg"
    snapshots_dir = data_root / "sources" / source_id / "snapshots"
    snapshots_dir.mkdir(parents=True)

    (snapshots_dir / "2026-01-01.json").write_text(
        json.dumps({"source_id": source_id, "items": []}),
        encoding="utf-8",
    )

    report = verify_data_root(data_root)
    by_type = report["totals"]["issues_by_type"]
    assert by_type["snapshot_items_empty"] == 1


def test_verify_data_placeholder_pipe_table(tmp_path):
    """Content containing |  | is flagged as placeholder."""
    data_root = tmp_path
    source_id = "blog-ph"
    source_root = data_root / "sources" / source_id
    items_root = source_root / "items"
    items_root.mkdir(parents=True)

    item_id = "placeholder-12345678"
    (items_root / item_id).mkdir()
    content = "|  | Some table artifact |  |\n" * 50
    (items_root / item_id / "content.md").write_text(content, encoding="utf-8")
    meta = {
        "id": item_id,
        "source_id": source_id,
        "title": "Placeholder",
        "url": "https://example.com/ph",
        "published_at": None,
        "archived_at": "2026-01-01T00:00:00Z",
        "author": None,
        "summary": None,
        "content_path": f"sources/{source_id}/items/{item_id}/content.md",
    }
    (items_root / item_id / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (source_root / "manifest.jsonl").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    report = verify_data_root(data_root, min_content_chars=20)
    by_type = report["totals"]["issues_by_type"]
    assert by_type.get("content_placeholder", 0) >= 1


def test_verify_data_placeholder_signup_prefix(tmp_path):
    """Content starting with [Signup] is flagged as placeholder."""
    data_root = tmp_path
    source_id = "blog-signup"
    source_root = data_root / "sources" / source_id
    items_root = source_root / "items"
    items_root.mkdir(parents=True)

    item_id = "signup-12345678"
    (items_root / item_id).mkdir()
    content = "[Signup] to read this premium content\n" * 50
    (items_root / item_id / "content.md").write_text(content, encoding="utf-8")
    meta = {
        "id": item_id,
        "source_id": source_id,
        "title": "Signup",
        "url": "https://example.com/signup",
        "published_at": None,
        "archived_at": "2026-01-01T00:00:00Z",
        "author": None,
        "summary": None,
        "content_path": f"sources/{source_id}/items/{item_id}/content.md",
    }
    (items_root / item_id / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (source_root / "manifest.jsonl").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    report = verify_data_root(data_root, min_content_chars=20)
    by_type = report["totals"]["issues_by_type"]
    assert by_type.get("content_placeholder", 0) >= 1


def test_verify_data_placeholder_single_pipe_line(tmp_path):
    """Content with a bare | line is flagged as placeholder."""
    data_root = tmp_path
    source_id = "blog-pipe"
    source_root = data_root / "sources" / source_id
    items_root = source_root / "items"
    items_root.mkdir(parents=True)

    item_id = "pipe-12345678"
    (items_root / item_id).mkdir()
    content = "Some text\n|\nMore text\n" * 30
    (items_root / item_id / "content.md").write_text(content, encoding="utf-8")
    meta = {
        "id": item_id,
        "source_id": source_id,
        "title": "Pipe",
        "url": "https://example.com/pipe",
        "published_at": None,
        "archived_at": "2026-01-01T00:00:00Z",
        "author": None,
        "summary": None,
        "content_path": f"sources/{source_id}/items/{item_id}/content.md",
    }
    (items_root / item_id / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (source_root / "manifest.jsonl").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    report = verify_data_root(data_root, min_content_chars=20)
    by_type = report["totals"]["issues_by_type"]
    assert by_type.get("content_placeholder", 0) >= 1


def test_verify_data_aggregation_valid_snapshot(tmp_path):
    """Aggregation source with valid items produces no issues."""
    data_root = tmp_path
    source_id = "agg-valid"
    snapshots_dir = data_root / "sources" / source_id / "snapshots"
    snapshots_dir.mkdir(parents=True)

    snapshot = {
        "source_id": source_id,
        "items": [
            {"title": "Item 1", "url": "https://example.com/1"},
            {"title": "Item 2", "url": "https://example.com/2"},
        ],
    }
    (snapshots_dir / "2026-01-01.json").write_text(json.dumps(snapshot), encoding="utf-8")

    report = verify_data_root(data_root)
    by_type = report["totals"]["issues_by_type"]
    assert by_type.get("snapshot_items_empty", 0) == 0
    assert report["totals"]["items_checked"] == 1


def test_verify_data_unrecognized_layout(tmp_path):
    """Source directory with no manifest or snapshots."""
    data_root = tmp_path
    (data_root / "sources" / "mystery").mkdir(parents=True)

    report = verify_data_root(data_root)
    by_type = report["totals"]["issues_by_type"]
    assert by_type.get("source_unrecognized_layout", 0) == 1


def test_verify_data_missing_content_path_uses_fallback(tmp_path):
    """Manifest record without content_path falls back to items dir."""
    data_root = tmp_path
    source_id = "blog-nopath"
    source_root = data_root / "sources" / source_id
    items_root = source_root / "items"
    items_root.mkdir(parents=True)

    item_id = "nopath-12345678"
    (items_root / item_id).mkdir()
    content = "Real content here.\n" * 50
    (items_root / item_id / "content.md").write_text(content, encoding="utf-8")
    meta = {
        "id": item_id,
        "source_id": source_id,
        "title": "No Path",
        "url": "https://example.com/nopath",
        "published_at": None,
        "archived_at": "2026-01-01T00:00:00Z",
        "author": None,
        "summary": None,
    }
    (items_root / item_id / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (source_root / "manifest.jsonl").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    report = verify_data_root(data_root, min_content_chars=20)
    by_type = report["totals"]["issues_by_type"]
    assert by_type.get("content_missing", 0) == 0


def test_verify_data_sources_root_missing(tmp_path):
    """Missing sources/ directory is reported."""
    report = verify_data_root(tmp_path)
    by_type = report["totals"]["issues_by_type"]
    assert by_type.get("sources_root_missing", 0) == 1
