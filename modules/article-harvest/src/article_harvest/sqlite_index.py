from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Record, Source
from .sources.registry import list_sources
from .storage import Storage, default_data_root
from .time_utils import iso_now, parse_date

DEFAULT_DB_NAME = "index.sqlite"


class SQLiteIndex:
    def __init__(self, data_root: Path | None = None) -> None:
        self.data_root = data_root or default_data_root()

    def path(self) -> Path:
        return self.data_root / DEFAULT_DB_NAME

    def exists(self) -> bool:
        return self.path().exists()

    def connect(self) -> sqlite3.Connection:
        self.data_root.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path())
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                archived_at TEXT NOT NULL,
                archived_date TEXT NOT NULL,
                published_at TEXT,
                author TEXT,
                snapshot_date TEXT,
                item_id TEXT,
                content_path TEXT,
                rank INTEGER,
                comments_count INTEGER,
                score INTEGER,
                extra_json TEXT
            )
            """
        )
        _ensure_columns(conn, ["item_id", "content_path"])
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_source ON records(source_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_archived_date ON records(archived_date)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_title ON records(title)")

    def rebuild(self, storage: Storage, sources: list[Source]) -> int:
        path = self.path()
        if path.exists():
            path.unlink()
        total = 0
        with self.connect() as conn:
            self.ensure_schema(conn)
            for source in sources:
                records = storage.records_for_source(source)
                total += self._insert_records(conn, records)
        return total

    def upsert_records(self, records: Iterable[Record]) -> int:
        records_list = list(records)
        if not records_list:
            return 0
        with self.connect() as conn:
            self.ensure_schema(conn)
            return self._insert_records(conn, records_list)

    def query_by_source(self, source_id: str, limit: int | None = None) -> list[Record]:
        sql = "SELECT * FROM records WHERE source_id = ? ORDER BY archived_at DESC"
        params: list[object] = [source_id]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_record(row) for row in rows]

    def query_by_keyword(
        self,
        keyword: str,
        source_ids: list[str] | None = None,
        limit: int | None = None,
    ) -> list[Record]:
        sql = "SELECT * FROM records WHERE lower(title) LIKE ?"
        params: list[object] = [f"%{keyword.lower()}%"]
        if source_ids:
            placeholders = ", ".join("?" for _ in source_ids)
            sql += f" AND source_id IN ({placeholders})"
            params.extend(source_ids)
        sql += " ORDER BY archived_at DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_record(row) for row in rows]

    def query_by_archive_date(
        self,
        start_date: str,
        end_date: str,
        source_ids: list[str] | None = None,
        limit: int | None = None,
    ) -> list[Record]:
        sql = "SELECT * FROM records WHERE archived_date BETWEEN ? AND ?"
        params: list[object] = [start_date, end_date]
        if source_ids:
            placeholders = ", ".join("?" for _ in source_ids)
            sql += f" AND source_id IN ({placeholders})"
            params.extend(source_ids)
        sql += " ORDER BY archived_at DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_record(row) for row in rows]

    def _insert_records(self, conn: sqlite3.Connection, records: list[Record]) -> int:
        rows = [_row_from_record(record) for record in records]
        if not rows:
            return 0
        conn.executemany(
            """
            INSERT OR REPLACE INTO records (
                id,
                source_id,
                source_name,
                kind,
                title,
                url,
                archived_at,
                archived_date,
                published_at,
                author,
                snapshot_date,
                item_id,
                content_path,
                rank,
                comments_count,
                score,
                extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)


def rebuild_sqlite_index(
    storage: Storage | None = None,
    sources: list[Source] | None = None,
) -> dict:
    storage = storage or Storage()
    sources = sources or list_sources(include_disabled=False)
    index = SQLiteIndex(storage.data_root)
    started_at = iso_now()
    total = index.rebuild(storage, sources)
    return {
        "path": str(index.path()),
        "sources": [source.id for source in sources],
        "records": total,
        "started_at": started_at,
        "finished_at": iso_now(),
    }


def _row_from_record(record: Record) -> tuple:
    record_id = _record_id(record)
    archived_date = parse_date(record.archived_at).isoformat()
    extra_json = json.dumps(record.extra, ensure_ascii=False) if record.extra else None
    return (
        record_id,
        record.source_id,
        record.source_name,
        record.kind,
        record.title,
        record.url,
        record.archived_at,
        archived_date,
        record.published_at,
        record.author,
        record.snapshot_date,
        record.item_id,
        record.content_path,
        record.rank,
        record.comments_count,
        record.score,
        extra_json,
    )


def _row_to_record(row: sqlite3.Row) -> Record:
    extra_raw = row["extra_json"]
    extra = json.loads(extra_raw) if extra_raw else {}
    return Record(
        source_id=row["source_id"],
        source_name=row["source_name"],
        kind=row["kind"],
        title=row["title"],
        url=row["url"],
        archived_at=row["archived_at"],
        published_at=row["published_at"],
        author=row["author"],
        snapshot_date=row["snapshot_date"],
        item_id=row["item_id"],
        content_path=row["content_path"],
        rank=row["rank"],
        comments_count=row["comments_count"],
        score=row["score"],
        extra=extra,
    )


def _record_id(record: Record) -> str:
    raw = f"{record.source_id}|{record.archived_at}|{record.url}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _column_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(records)").fetchall()
    return {row[1] for row in rows}


def _add_column(conn: sqlite3.Connection, name: str, col_type: str) -> None:
    conn.execute(f"ALTER TABLE records ADD COLUMN {name} {col_type}")


def _ensure_column(conn: sqlite3.Connection, name: str, col_type: str) -> None:
    if name in _column_names(conn):
        return
    _add_column(conn, name, col_type)


def _ensure_columns(conn: sqlite3.Connection, names: list[str]) -> None:
    for name in names:
        _ensure_column(conn, name, "TEXT")
