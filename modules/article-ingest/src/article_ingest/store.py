from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .paths import data_root, ensure_data_dirs
from .timestamps import now_utc


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = data_root(root)
        ensure_data_dirs(self.root)
        self.db_path = self.root / "index.sqlite"
        self._conn: sqlite3.Connection | None = None
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def init_db(self) -> None:
        conn = self.connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                homepage_url TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                policy_json TEXT NOT NULL DEFAULT '{}',
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_run_id INTEGER,
                last_success_at TEXT,
                last_error TEXT
            );

            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL,
                item_key TEXT NOT NULL,
                canonical_url TEXT,
                title TEXT,
                author TEXT,
                published_at TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_seen_run_id INTEGER,
                latest_version_id INTEGER,
                UNIQUE(source_id, item_key)
            );

            CREATE TABLE IF NOT EXISTS item_versions (
                id INTEGER PRIMARY KEY,
                item_id INTEGER NOT NULL,
                version_index INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                content_path TEXT NOT NULL,
                extracted_at TEXT NOT NULL,
                run_id INTEGER NOT NULL,
                title_snapshot TEXT,
                published_at_snapshot TEXT,
                word_count INTEGER,
                UNIQUE(item_id, content_hash)
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                total_items INTEGER NOT NULL DEFAULT 0,
                new_items INTEGER NOT NULL DEFAULT 0,
                updated_items INTEGER NOT NULL DEFAULT 0,
                errors_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS run_errors (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL,
                source_id INTEGER,
                url TEXT,
                stage TEXT NOT NULL,
                http_status INTEGER,
                error_code TEXT,
                message TEXT,
                retriable INTEGER NOT NULL DEFAULT 1,
                input_path TEXT,
                occurred_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY,
                item_version_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                local_path TEXT,
                status TEXT NOT NULL,
                mime TEXT,
                size INTEGER,
                sha256 TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_items_source_key ON items(source_id, item_key);
            CREATE INDEX IF NOT EXISTS idx_item_versions_run ON item_versions(run_id);
            CREATE INDEX IF NOT EXISTS idx_items_last_seen_run ON items(last_seen_run_id);
            CREATE INDEX IF NOT EXISTS idx_run_errors_run ON run_errors(run_id);
            """
        )
        conn.commit()

    def _fetchone(self, query: str, params: Iterable[Any]) -> sqlite3.Row | None:
        cur = self.connect().execute(query, params)
        row = cur.fetchone()
        cur.close()
        return row

    def _fetchall(self, query: str, params: Iterable[Any]) -> list[sqlite3.Row]:
        cur = self.connect().execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def create_run(self, status: str = "running") -> int:
        now = now_utc()
        cur = self.connect().execute(
            "INSERT INTO runs (started_at, status) VALUES (?, ?)",
            (now, status),
        )
        self.connect().commit()
        return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        status: str,
        total_items: int,
        new_items: int,
        updated_items: int,
        errors_count: int,
        notes: str | None = None,
    ) -> None:
        finished = now_utc()
        self.connect().execute(
            """
            UPDATE runs
            SET finished_at = ?, status = ?, total_items = ?, new_items = ?,
                updated_items = ?, errors_count = ?, notes = ?
            WHERE id = ?
            """,
            (
                finished,
                status,
                total_items,
                new_items,
                updated_items,
                errors_count,
                notes,
                run_id,
            ),
        )
        self.connect().commit()

    def record_error(
        self,
        run_id: int,
        source_id: int | None,
        url: str | None,
        stage: str,
        http_status: int | None,
        error_code: str | None,
        message: str | None,
        retriable: bool = True,
        input_path: str | None = None,
    ) -> None:
        self.connect().execute(
            """
            INSERT INTO run_errors
            (run_id, source_id, url, stage, http_status, error_code, message,
             retriable, input_path, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                source_id,
                url,
                stage,
                http_status,
                error_code,
                message,
                1 if retriable else 0,
                input_path,
                now_utc(),
            ),
        )
        self.connect().commit()

    def list_runs(self) -> list[sqlite3.Row]:
        return self._fetchall("SELECT * FROM runs ORDER BY id DESC", ())

    def get_latest_run_id(self) -> int | None:
        row = self._fetchone("SELECT id FROM runs ORDER BY id DESC LIMIT 1", ())
        return int(row[0]) if row else None

    def get_previous_run_id(self, run_id: int) -> int | None:
        row = self._fetchone(
            "SELECT id FROM runs WHERE id < ? ORDER BY id DESC LIMIT 1", (run_id,)
        )
        return int(row[0]) if row else None

    def upsert_source(
        self,
        slug: str,
        name: str,
        homepage_url: str | None,
        enabled: bool,
        policy: dict[str, Any],
        config: dict[str, Any],
    ) -> int:
        now = now_utc()
        conn = self.connect()
        row = self._fetchone("SELECT id FROM sources WHERE slug = ?", (slug,))
        if row:
            conn.execute(
                """
                UPDATE sources
                SET name = ?, homepage_url = ?, enabled = ?, policy_json = ?,
                    config_json = ?, updated_at = ?
                WHERE slug = ?
                """,
                (
                    name,
                    homepage_url,
                    1 if enabled else 0,
                    json.dumps(policy, ensure_ascii=True),
                    json.dumps(config, ensure_ascii=True),
                    now,
                    slug,
                ),
            )
            conn.commit()
            return int(row[0])
        cur = conn.execute(
            """
            INSERT INTO sources
            (slug, name, homepage_url, enabled, policy_json, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug,
                name,
                homepage_url,
                1 if enabled else 0,
                json.dumps(policy, ensure_ascii=True),
                json.dumps(config, ensure_ascii=True),
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)

    def update_source_enabled(self, slug: str, enabled: bool) -> None:
        self.connect().execute(
            "UPDATE sources SET enabled = ?, updated_at = ? WHERE slug = ?",
            (1 if enabled else 0, now_utc(), slug),
        )
        self.connect().commit()

    def list_sources(self) -> list[sqlite3.Row]:
        return self._fetchall("SELECT * FROM sources ORDER BY slug ASC", ())

    def get_source_by_slug(self, slug: str) -> sqlite3.Row | None:
        return self._fetchone("SELECT * FROM sources WHERE slug = ?", (slug,))

    def upsert_item(
        self,
        source_id: int,
        item_key: str,
        canonical_url: str | None,
        title: str | None,
        author: str | None,
        published_at: str | None,
        run_id: int,
    ) -> tuple[int, bool]:
        now = now_utc()
        conn = self.connect()
        row = self._fetchone(
            "SELECT id FROM items WHERE source_id = ? AND item_key = ?",
            (source_id, item_key),
        )
        if row:
            conn.execute(
                """
                UPDATE items
                SET canonical_url = ?, title = ?, author = ?, published_at = ?,
                    last_seen_at = ?, last_seen_run_id = ?
                WHERE id = ?
                """,
                (
                    canonical_url,
                    title,
                    author,
                    published_at,
                    now,
                    run_id,
                    int(row[0]),
                ),
            )
            conn.commit()
            return int(row[0]), False
        cur = conn.execute(
            """
            INSERT INTO items
            (source_id, item_key, canonical_url, title, author, published_at,
             first_seen_at, last_seen_at, last_seen_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                item_key,
                canonical_url,
                title,
                author,
                published_at,
                now,
                now,
                run_id,
            ),
        )
        conn.commit()
        return int(cur.lastrowid), True

    def get_latest_version(self, item_id: int) -> sqlite3.Row | None:
        return self._fetchone(
            "SELECT * FROM item_versions WHERE item_id = ? ORDER BY version_index DESC LIMIT 1",
            (item_id,),
        )
    def has_version_hash(self, item_id: int, content_hash: str) -> bool:
        row = self._fetchone(
            "SELECT 1 FROM item_versions WHERE item_id = ? AND content_hash = ?",
            (item_id, content_hash),
        )
        return row is not None
    def create_item_version(
        self,
        item_id: int,
        content_hash: str,
        content_path: str,
        extracted_at: str,
        run_id: int,
        title_snapshot: str | None,
        published_at_snapshot: str | None,
        word_count: int | None,
    ) -> tuple[int, int]:
        latest = self.get_latest_version(item_id)
        next_index = 1 if latest is None else int(latest["version_index"]) + 1
        cur = self.connect().execute(
            """
            INSERT INTO item_versions
            (item_id, version_index, content_hash, content_path, extracted_at, run_id,
             title_snapshot, published_at_snapshot, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                next_index,
                content_hash,
                content_path,
                extracted_at,
                run_id,
                title_snapshot,
                published_at_snapshot,
                word_count,
            ),
        )
        version_id = int(cur.lastrowid)
        self.connect().execute(
            "UPDATE items SET latest_version_id = ? WHERE id = ?",
            (version_id, item_id),
        )
        self.connect().commit()
        return version_id, next_index

    def update_version_content_path(self, version_id: int, content_path: Path, root: Path) -> None:
        path_value = str(content_path)
        try:
            path_value = str(content_path.relative_to(root))
        except ValueError:
            pass
        self.connect().execute(
            "UPDATE item_versions SET content_path = ? WHERE id = ?",
            (path_value, version_id),
        )
        self.connect().commit()

    def record_assets(self, version_id: int, assets: list[dict[str, Any]]) -> None:
        if not assets:
            return
        conn = self.connect()
        for asset in assets:
            conn.execute(
                """
                INSERT INTO assets (item_version_id, url, local_path, status, mime, size, sha256)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    asset.get("url"),
                    asset.get("local_path"),
                    asset.get("status") or "unknown",
                    asset.get("mime"),
                    asset.get("size"),
                    asset.get("sha256"),
                ),
            )
        conn.commit()

    def delete_item_version(self, version_id: int) -> None:
        self.connect().execute(
            "DELETE FROM assets WHERE item_version_id = ?",
            (version_id,),
        )
        self.connect().execute("DELETE FROM item_versions WHERE id = ?", (version_id,))
        self.connect().commit()
    def get_updates_for_run(self, run_id: int) -> list[sqlite3.Row]:
        return self._fetchall(
            """
            SELECT items.*, item_versions.id as version_id, item_versions.content_hash,
                   item_versions.extracted_at
            FROM item_versions
            JOIN items ON items.id = item_versions.item_id
            WHERE item_versions.run_id = ?
            ORDER BY item_versions.id DESC
            """,
            (run_id,),
        )
    def _get_version_row(self, item_id: int, version_id: int | None) -> sqlite3.Row | None:
        if version_id is None:
            return self._fetchone(
                "SELECT * FROM item_versions WHERE item_id = ? ORDER BY version_index DESC LIMIT 1",
                (item_id,),
            )
        return self._fetchone(
            "SELECT * FROM item_versions WHERE id = ? AND item_id = ?",
            (version_id, item_id),
        )
    def _resolve_content_path(self, content_path: str) -> Path:
        path = Path(content_path)
        if not path.is_absolute():
            path = self.root / path
        return path
    def read_content(self, item_id: int, version_id: int | None = None) -> tuple[str, sqlite3.Row]:
        row = self._get_version_row(item_id, version_id)
        if row is None:
            raise ValueError("Content not found for item/version")
        content_path = self._resolve_content_path(row["content_path"])
        markdown = content_path.read_text(encoding="utf-8")
        return markdown, row
    def read_sidecar(
        self,
        item_id: int,
        version_id: int | None,
        filename: str,
    ) -> tuple[str, sqlite3.Row]:
        row = self._get_version_row(item_id, version_id)
        if row is None:
            raise ValueError("Content not found for item/version")
        content_path = self._resolve_content_path(row["content_path"])
        sidecar_path = content_path.parent / filename
        if not sidecar_path.exists():
            raise ValueError("Sidecar file not found")
        markdown = sidecar_path.read_text(encoding="utf-8")
        return markdown, row
    def list_items(self, source_id: int | None = None) -> list[sqlite3.Row]:
        if source_id is None:
            return self._fetchall("SELECT * FROM items ORDER BY id DESC", ())
        return self._fetchall(
            "SELECT * FROM items WHERE source_id = ? ORDER BY id DESC", (source_id,)
        )
    def get_item(self, item_id: int) -> sqlite3.Row | None:
        return self._fetchone("SELECT * FROM items WHERE id = ?", (item_id,))
    def get_item_versions(self, item_id: int) -> list[sqlite3.Row]:
        return self._fetchall(
            "SELECT * FROM item_versions WHERE item_id = ? ORDER BY version_index DESC",
            (item_id,),
        )
