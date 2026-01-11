from __future__ import annotations

from article_ingest.paths import data_root, ensure_data_dirs
from article_ingest.store import Store


def test_data_root_override_creates_dirs(tmp_path):
    root = data_root(tmp_path)
    ensure_data_dirs(root)
    assert (root / "content").exists()
    assert (root / "logs").exists()
    assert (root / "failures").exists()
    assert (root / "inbox").exists()


def test_store_version_path_and_read_content(tmp_path):
    store = Store(root=tmp_path)
    run_id = store.create_run()
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

    markdown, _ = store.read_content(item_id)
    assert markdown == "hello"
    comments_file = tmp_path / "comments.md"
    comments_file.write_text("top comments", encoding="utf-8")
    comments, _ = store.read_sidecar(item_id, None, "comments.md")
    assert comments == "top comments"


def test_store_run_helpers(tmp_path):
    store = Store(root=tmp_path)
    first = store.create_run(status="success")
    second = store.create_run(status="success")
    assert store.get_latest_run_id() == second
    assert store.get_previous_run_id(second) == first
