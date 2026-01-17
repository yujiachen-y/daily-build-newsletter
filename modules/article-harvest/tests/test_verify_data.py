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
