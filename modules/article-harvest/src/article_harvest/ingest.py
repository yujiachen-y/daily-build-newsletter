from __future__ import annotations

from datetime import datetime

from .errors import FetchError
from .http import create_session
from .models import BlogItem, FetchContext, Source
from .sqlite_index import SQLiteIndex
from .sources.registry import get_source, list_sources
from .storage import Storage
from .time_utils import iso_now


def ingest_all(storage: Storage | None = None) -> dict:
    storage = storage or Storage()
    sources = list_sources(include_disabled=False)
    return _run_ingest(storage, sources)


def ingest_source(source_id: str, storage: Storage | None = None) -> dict:
    storage = storage or Storage()
    source = get_source(source_id)
    return _run_ingest(storage, [source])


def _run_ingest(storage: Storage, sources: list[Source]) -> dict:
    run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    started_at = iso_now()
    session = create_session()
    ctx = FetchContext(session=session, run_id=run_id, now=datetime.utcnow())
    sqlite_index = SQLiteIndex(storage.data_root)
    sqlite_enabled = sqlite_index.exists()

    successes: list[dict] = []
    failures: list[dict] = []

    for source in sources:
        try:
            items = source.fetch(ctx)
            if not items:
                raise FetchError("no items returned")
            if source.kind == "aggregation":
                storage.save_snapshot(source, items)
                if sqlite_enabled:
                    sqlite_index.upsert_records(storage.iter_snapshot_records(source))
                successes.append({"source_id": source.id, "stored": len(items)})
            else:
                stored = storage.save_blog_items(source, _as_blog_items(items))
                if sqlite_enabled and stored:
                    sqlite_index.upsert_records(stored)
                successes.append(
                    {
                        "source_id": source.id,
                        "stored": len(stored),
                        "fetched": len(items),
                    }
                )
        except Exception as exc:  # pragma: no cover - error formatting
            failures.append({"source_id": source.id, "error": str(exc)})

    report = {
        "run_id": run_id,
        "started_at": started_at,
        "sources": [source.id for source in sources],
        "successes": successes,
        "failures": failures,
        "finished_at": iso_now(),
    }
    storage.record_run(run_id, report)
    return report


def _as_blog_items(items: list[BlogItem] | list) -> list[BlogItem]:
    blog_items: list[BlogItem] = []
    for item in items:
        if not isinstance(item, BlogItem):
            raise FetchError("non-blog item returned for blog source")
        blog_items.append(item)
    return blog_items
