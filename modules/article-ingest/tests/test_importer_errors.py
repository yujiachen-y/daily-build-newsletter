from __future__ import annotations

from article_ingest.importer import Importer
from article_ingest.store import Store


def test_importer_missing_meta_records_error(tmp_path):
    store = Store(root=tmp_path)
    store.upsert_source(
        slug="demo",
        name="Demo",
        homepage_url="https://example.com",
        enabled=True,
        policy={},
        config={},
    )

    inbox = tmp_path / "inbox" / "demo"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "post.md").write_text("# Title\n\nBody", encoding="utf-8")

    importer = Importer(store, root=tmp_path)
    importer.run()

    versions = store.connect().execute("SELECT * FROM item_versions").fetchall()
    assert versions == []

    errors = store.connect().execute("SELECT * FROM run_errors").fetchall()
    assert len(errors) == 1
    assert errors[0]["stage"] == "import"
