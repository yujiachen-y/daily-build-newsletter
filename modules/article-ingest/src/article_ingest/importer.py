from __future__ import annotations

import json
import shutil
from pathlib import Path

import requests

from .extract import extract_markdown
from .front_matter import split_front_matter
from .run_logger import RunLogger
from .storage import download_assets, write_markdown
from .store import Store
from .text_processing import hash_content
from .timestamps import now_utc


class Importer:
    def __init__(self, store: Store, root: Path | None = None) -> None:
        self.store = store
        self.root = store.root if root is None else root

    def run(self, source_slug: str | None = None) -> int:
        run_id = self.store.create_run(status="import")
        logger = RunLogger(self.root, run_id)
        inbox_root = self.root / "inbox"
        archive_root = self.root / "inbox" / "archive" / f"run-{run_id}"
        archive_root.mkdir(parents=True, exist_ok=True)

        total_items = 0
        new_items = 0
        updated_items = 0
        errors_count = 0

        def record_error(
            source_id: int | None,
            url: str | None,
            stage: str,
            error_code: str,
            message: str,
            input_path: str | None = None,
            retriable: bool = True,
        ) -> None:
            nonlocal errors_count
            self.store.record_error(
                run_id,
                source_id,
                url,
                stage,
                None,
                error_code,
                message,
                retriable,
                input_path,
            )
            logger.failure(
                {
                    "run_id": run_id,
                    "source_id": source_id,
                    "url": url,
                    "stage": stage,
                    "error_code": error_code,
                    "message": message,
                    "input_path": input_path,
                }
            )
            errors_count += 1

        source_dirs = [d for d in inbox_root.iterdir() if d.is_dir() and d.name != "archive"]
        if source_slug:
            source_dirs = [d for d in source_dirs if d.name == source_slug]

        for source_dir in source_dirs:
            source_row = self.store.get_source_by_slug(source_dir.name)
            if source_row is None:
                logger.log(f"import missing source={source_dir.name}")
                record_error(
                    None,
                    None,
                    "import",
                    "source",
                    f"Source not found: {source_dir.name}",
                )
                continue
            source_id = int(source_row["id"])
            source_slug_name = source_dir.name

            content_files = list(source_dir.glob("*.md")) + list(source_dir.glob("*.html"))
            by_stem: dict[str, list[Path]] = {}
            for file in content_files:
                by_stem.setdefault(file.stem, []).append(file)

            for stem, files in by_stem.items():
                total_items += 1
                md_file = next((f for f in files if f.suffix == ".md"), None)
                html_file = next((f for f in files if f.suffix == ".html"), None)
                if md_file and html_file:
                    logger.log(f"import prefer-md stem={stem}")
                content_file = md_file or html_file
                if content_file is None:
                    continue

                meta_path = source_dir / f"{stem}.meta.json"
                if not meta_path.exists():
                    meta_path = source_dir / "meta.json"
                if not meta_path.exists():
                    logger.log(f"import missing meta stem={stem}")
                    record_error(
                        source_id,
                        None,
                        "import",
                        "meta",
                        "Missing meta.json",
                        str(content_file),
                    )
                    continue

                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    logger.log(f"import invalid meta stem={stem} {exc}")
                    record_error(
                        source_id,
                        None,
                        "import",
                        "meta",
                        f"Invalid meta.json: {exc}",
                        str(meta_path),
                        retriable=False,
                    )
                    continue

                canonical_url = meta.get("canonical_url") or meta.get("url") or None
                item_key = meta.get("item_key") or canonical_url or stem
                title = meta.get("title")
                author = meta.get("author")
                published_at = meta.get("published_at")

                item_id, created = self.store.upsert_item(
                    source_id,
                    item_key,
                    canonical_url,
                    title,
                    author,
                    published_at,
                    run_id,
                )
                if created:
                    new_items += 1

                try:
                    if content_file.suffix == ".md":
                        raw_markdown = content_file.read_text(encoding="utf-8")
                        _, raw_markdown = split_front_matter(raw_markdown)
                    else:
                        html = content_file.read_text(encoding="utf-8")
                        raw_markdown = extract_markdown(html)
                except Exception as exc:
                    logger.log(f"import extract error stem={stem} {exc}")
                    record_error(
                        source_id,
                        canonical_url,
                        "import",
                        "extract",
                        str(exc),
                        str(content_file),
                    )
                    continue

                content_hash = hash_content(raw_markdown)
                if self.store.has_version_hash(item_id, content_hash):
                    continue

                extracted_at = now_utc()
                version_id, version_index = self.store.create_item_version(
                    item_id,
                    content_hash,
                    "pending",
                    extracted_at,
                    run_id,
                    title,
                    published_at,
                    len(raw_markdown.split()),
                )

                session = requests.Session()
                markdown_with_assets, assets = download_assets(
                    self.root,
                    source_slug_name,
                    item_key,
                    version_index,
                    raw_markdown,
                    canonical_url,
                    session,
                )

                front_matter = {
                    "item_id": item_id,
                    "source_id": source_id,
                    "canonical_url": canonical_url,
                    "title": title,
                    "published_at": published_at,
                    "version_id": version_id,
                    "content_hash": content_hash,
                    "extracted_at": extracted_at,
                    "run_id": run_id,
                }

                try:
                    content_path = write_markdown(
                        self.root,
                        source_slug_name,
                        item_key,
                        version_index,
                        markdown_with_assets,
                        front_matter,
                    )
                except Exception as exc:
                    logger.log(f"import write error stem={stem} {exc}")
                    record_error(
                        source_id,
                        canonical_url,
                        "import",
                        "write",
                        str(exc),
                        str(content_file),
                    )
                    self.store.delete_item_version(version_id)
                    continue
                self.store.update_version_content_path(version_id, content_path, self.root)
                self.store.record_assets(version_id, assets)
                for asset in assets:
                    if asset.get("status") != "stored":
                        record_error(
                            source_id,
                            asset.get("url"),
                            "assets",
                            asset.get("status") or "asset",
                            "Asset download failed",
                            str(content_file),
                        )
                updated_items += 1

                destination = archive_root / source_dir.name
                destination.mkdir(parents=True, exist_ok=True)
                shutil.move(str(content_file), destination / content_file.name)
                if meta_path.exists() and meta_path.parent == source_dir:
                    shutil.move(str(meta_path), destination / meta_path.name)

        self.store.finish_run(
            run_id,
            status="success",
            total_items=total_items,
            new_items=new_items,
            updated_items=updated_items,
            errors_count=errors_count,
        )
        return run_id
