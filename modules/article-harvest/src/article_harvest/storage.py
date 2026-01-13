from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .models import AggregationItem, BlogItem, Record, Source
from .slug import slugify
from .time_utils import iso_date_today, iso_now


def module_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_data_root() -> Path:
    return module_root() / "data"


class Storage:
    def __init__(self, data_root: Path | None = None) -> None:
        self.data_root = data_root or default_data_root()

    def source_root(self, source_id: str) -> Path:
        return self.data_root / "sources" / source_id

    def manifest_path(self, source_id: str) -> Path:
        return self.source_root(source_id) / "manifest.jsonl"

    def snapshots_dir(self, source_id: str) -> Path:
        return self.source_root(source_id) / "snapshots"

    def items_dir(self, source_id: str) -> Path:
        return self.source_root(source_id) / "items"

    def content_path(self, source_id: str, item_id: str) -> Path:
        return self.items_dir(source_id) / item_id / "content.md"

    def runs_dir(self) -> Path:
        return self.data_root / "runs"

    def ensure_dirs(self, source_id: str) -> None:
        self.snapshots_dir(source_id).mkdir(parents=True, exist_ok=True)
        self.items_dir(source_id).mkdir(parents=True, exist_ok=True)

    def load_manifest(self, source_id: str) -> list[dict[str, str | int | None]]:
        path = self.manifest_path(source_id)
        if not path.exists():
            return []
        records: list[dict[str, str | int | None]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                records.append(json.loads(line))
        return records

    def existing_urls(self, source_id: str) -> set[str]:
        return {
            str(record.get("url"))
            for record in self.load_manifest(source_id)
            if record.get("url")
        }

    def append_manifest(self, source_id: str, records: Iterable[dict[str, str | int | None]]) -> None:
        path = self.manifest_path(source_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")

    def _item_id(self, title: str, url: str) -> str:
        base = slugify(title or url)
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        return f"{base}-{digest}"

    def save_blog_items(self, source: Source, items: list[BlogItem]) -> list[Record]:
        self.ensure_dirs(source.id)
        archived_at = iso_now()
        existing = self.existing_urls(source.id)
        stored_records: list[Record] = []
        manifest_records: list[dict[str, str | int | None]] = []

        for item in items:
            if item.url in existing:
                continue
            item_id = self._item_id(item.title, item.url)
            item_dir = self.items_dir(source.id) / item_id
            item_dir.mkdir(parents=True, exist_ok=True)
            content_path = item_dir / "content.md"
            content = item.content_markdown or item.summary or ""
            content_path.write_text(content, encoding="utf-8")

            meta = {
                "id": item_id,
                "source_id": source.id,
                "title": item.title,
                "url": item.url,
                "published_at": item.published_at,
                "archived_at": archived_at,
                "author": item.author,
                "summary": item.summary,
                "content_path": str(content_path.relative_to(self.data_root)),
            }
            (item_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            manifest_records.append(meta)
            stored_records.append(
                Record(
                    source_id=source.id,
                    source_name=source.name,
                    kind=source.kind,
                    title=item.title,
                    url=item.url,
                    archived_at=archived_at,
                    published_at=item.published_at,
                    author=item.author,
                    extra={},
                    item_id=item_id,
                    content_path=str(content_path.relative_to(self.data_root)),
                )
            )

        if manifest_records:
            self.append_manifest(source.id, manifest_records)
        return stored_records

    def save_snapshot(self, source: Source, items: list[AggregationItem]) -> Path:
        self.ensure_dirs(source.id)
        snapshot_date = iso_date_today()
        path = self.snapshots_dir(source.id) / f"{snapshot_date}.json"
        payload = {
            "source_id": source.id,
            "source_name": source.name,
            "archived_at": snapshot_date,
            "generated_at": iso_now(),
            "items": [self._aggregation_to_dict(item) for item in items],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def iter_snapshot_records(self, source: Source) -> list[Record]:
        records: list[Record] = []
        snapshots_dir = self.snapshots_dir(source.id)
        if not snapshots_dir.exists():
            return records
        for path in sorted(snapshots_dir.glob("*.json"), reverse=True):
            payload = json.loads(path.read_text(encoding="utf-8"))
            snapshot_date = str(payload.get("archived_at"))
            for item in payload.get("items", []):
                records.append(
                    Record(
                        source_id=source.id,
                        source_name=source.name,
                        kind=source.kind,
                        title=str(item.get("title")),
                        url=str(item.get("url")),
                        archived_at=snapshot_date,
                        published_at=item.get("published_at"),
                        author=item.get("author"),
                        snapshot_date=snapshot_date,
                        rank=item.get("rank"),
                        comments_count=item.get("comments_count"),
                        score=item.get("score"),
                        extra=item.get("extra") or {},
                    )
                )
        return records

    def records_for_source(self, source: Source) -> list[Record]:
        if source.kind == "aggregation":
            return self.iter_snapshot_records(source)
        records: list[Record] = []
        for row in self.load_manifest(source.id):
            records.append(
                Record(
                    source_id=source.id,
                    source_name=source.name,
                    kind=source.kind,
                    title=str(row.get("title")),
                    url=str(row.get("url")),
                    archived_at=str(row.get("archived_at")),
                    published_at=row.get("published_at"),
                    author=row.get("author"),
                    extra={},
                    item_id=row.get("id"),
                    content_path=row.get("content_path"),
                )
            )
        return records

    def record_run(self, run_id: str, payload: dict) -> Path:
        self.runs_dir().mkdir(parents=True, exist_ok=True)
        path = self.runs_dir() / f"run-{run_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _aggregation_to_dict(item: AggregationItem) -> dict:
        return {
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at,
            "author": item.author,
            "score": item.score,
            "comments_count": item.comments_count,
            "rank": item.rank,
            "discussion_url": item.discussion_url,
            "comments": [asdict(comment) for comment in item.comments],
            "extra": item.extra or {},
        }
