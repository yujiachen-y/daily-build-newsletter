from __future__ import annotations

import sqlite3

from .timestamps import now_utc


class RunStoreMixin:
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

    def list_running_runs(self) -> list[sqlite3.Row]:
        return self._fetchall("SELECT * FROM runs WHERE status = 'running' ORDER BY id ASC", ())

    def count_run_errors(self, run_id: int) -> int:
        row = self._fetchone("SELECT COUNT(*) FROM run_errors WHERE run_id = ?", (run_id,))
        return int(row[0]) if row else 0

    def fail_run(
        self,
        run_id: int,
        errors_count: int | None = None,
        notes: str | None = None,
    ) -> None:
        if errors_count is None:
            errors_count = self.count_run_errors(run_id)
        finished = now_utc()
        self.connect().execute(
            """
            UPDATE runs
            SET finished_at = ?, status = ?, errors_count = ?, notes = ?
            WHERE id = ?
            """,
            (finished, "failed", errors_count, notes, run_id),
        )
        self.connect().commit()

    def cleanup_stale_runs(self, cutoff: str, notes: str | None = None) -> list[int]:
        rows = self._fetchall(
            "SELECT id FROM runs WHERE status = 'running' AND started_at < ?",
            (cutoff,),
        )
        run_ids = [int(row["id"]) for row in rows]
        if not run_ids:
            return []
        for run_id in run_ids:
            run_notes = notes or f"stale_run_cleanup cutoff={cutoff}"
            self.fail_run(run_id, notes=run_notes)
        return run_ids

    def get_latest_run_id(self) -> int | None:
        row = self._fetchone("SELECT id FROM runs ORDER BY id DESC LIMIT 1", ())
        return int(row[0]) if row else None

    def get_previous_run_id(self, run_id: int) -> int | None:
        row = self._fetchone(
            "SELECT id FROM runs WHERE id < ? ORDER BY id DESC LIMIT 1", (run_id,)
        )
        return int(row[0]) if row else None

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
