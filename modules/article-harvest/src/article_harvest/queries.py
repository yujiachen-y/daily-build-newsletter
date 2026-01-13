from __future__ import annotations

from datetime import date

from .models import Record, Source
from .sqlite_index import SQLiteIndex
from .storage import Storage
from .time_utils import parse_date, parse_datetime


def records_for_source(storage: Storage, source: Source) -> list[Record]:
    return _sort_records(storage.records_for_source(source))


def query_by_source(storage: Storage, source: Source, limit: int | None = None) -> list[Record]:
    index = _sqlite_index(storage)
    if index:
        return index.query_by_source(source.id, limit=limit)
    records = records_for_source(storage, source)
    return records[:limit] if limit else records


def query_by_keyword(
    storage: Storage,
    sources: list[Source],
    keyword: str,
    source_id: str | None = None,
    limit: int | None = None,
) -> list[Record]:
    index = _sqlite_index(storage)
    if index:
        selected_sources = [source.id for source in sources if not source_id or source.id == source_id]
        return index.query_by_keyword(keyword, source_ids=selected_sources, limit=limit)
    keyword_lower = keyword.lower()
    records: list[Record] = []
    for source in sources:
        if source_id and source.id != source_id:
            continue
        for record in records_for_source(storage, source):
            if keyword_lower in record.title.lower():
                records.append(record)
    records = _sort_records(records)
    return records[:limit] if limit else records


def query_by_archive_date(
    storage: Storage,
    sources: list[Source],
    on: str | None = None,
    start: str | None = None,
    end: str | None = None,
    source_id: str | None = None,
    limit: int | None = None,
) -> list[Record]:
    start_date, end_date = _resolve_range(on, start, end)
    index = _sqlite_index(storage)
    if index:
        selected_sources = [source.id for source in sources if not source_id or source.id == source_id]
        return index.query_by_archive_date(
            start_date.isoformat(),
            end_date.isoformat(),
            source_ids=selected_sources,
            limit=limit,
        )
    records: list[Record] = []
    for source in sources:
        if source_id and source.id != source_id:
            continue
        for record in records_for_source(storage, source):
            archived_date = parse_date(record.archived_at)
            if start_date <= archived_date <= end_date:
                records.append(record)
    records = _sort_records(records)
    return records[:limit] if limit else records


def _resolve_range(on: str | None, start: str | None, end: str | None) -> tuple[date, date]:
    if on:
        target = parse_date(on)
        return target, target
    if not start or not end:
        raise ValueError("Both start and end are required for range queries")
    return parse_date(start), parse_date(end)


def _sort_records(records: list[Record]) -> list[Record]:
    return sorted(records, key=lambda item: parse_datetime(item.archived_at), reverse=True)


def _sqlite_index(storage: Storage) -> SQLiteIndex | None:
    index = SQLiteIndex(storage.data_root)
    return index if index.exists() else None
