from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from .adapters import AdapterError, adapter_for_mode
from .index_ingest import index_slugs, run_index_source
from .ingest_fetch import FetchJob, FetchOutcome, Throttle, build_session, fetch_candidate
from .ingest_runtime import RunSignalHandler, start_heartbeat, stop_heartbeat
from .models import ItemCandidate, Source, SourcePolicy
from .run_logger import RunLogger
from .storage import download_assets, write_markdown
from .store import Store
from .text_processing import hash_content
from .timestamps import now_utc

STALE_RUN_SECONDS = 60 * 60
HEARTBEAT_SECONDS = 60.0
SOURCE_CONCURRENCY_LIMIT = 8
@dataclass
class RunStats:
    total_items: int = 0
    new_items: int = 0
    updated_items: int = 0
    errors_count: int = 0


def _source_from_row(row: Any) -> Source:
    policy_data = json.loads(row["policy_json"] or "{}")
    policy_fields = {k: v for k, v in policy_data.items() if k in SourcePolicy.__dataclass_fields__}
    policy = SourcePolicy(**policy_fields)
    config = json.loads(row["config_json"] or "{}")
    return Source(
        id=int(row["id"]),
        slug=row["slug"],
        name=row["name"],
        homepage_url=row["homepage_url"],
        enabled=bool(row["enabled"]),
        policy=policy,
        config=config,
    )


class Ingestor:
    def __init__(self, store: Store, root: Path | None = None) -> None:
        self.store = store
        self.root = store.root if root is None else root

    def run(self, source_slugs: list[str] | None = None, run_type: str = "all") -> int:
        run_id = self.store.create_run()
        logger = RunLogger(self.root, run_id)
        logger.log("run started")
        stop_event, heartbeat_thread = start_heartbeat(logger, HEARTBEAT_SECONDS)
        stats = RunStats()
        status = "success"
        signal_handler = RunSignalHandler(logger)
        try:
            with signal_handler:
                self._cleanup_stale_runs(logger)
                self._validate_slug_overlap()
                sources: list[Source] = []
                if run_type in ("all", "content"):
                    sources = self._load_sources(source_slugs)
                if sources:
                    self._process_sources(sources, run_id, logger, stats)
                if run_type in ("all", "index"):
                    self._run_index_sources(source_slugs, logger)
        except KeyboardInterrupt:
            status = "failed"
            if not signal_handler.interrupted:
                logger.log("run interrupted")
            raise
        except BaseException as exc:
            status = "failed"
            logger.log(f"run error={exc}")
            raise
        finally:
            stop_heartbeat(stop_event, heartbeat_thread)
            logger.log(
                f"run finished status={status} total_items={stats.total_items} "
                f"new_items={stats.new_items} updated_items={stats.updated_items} "
                f"errors={stats.errors_count}"
            )
            self.store.finish_run(
                run_id,
                status=status,
                total_items=stats.total_items,
                new_items=stats.new_items,
                updated_items=stats.updated_items,
                errors_count=stats.errors_count,
            )
        return run_id
    def _cleanup_stale_runs(self, logger: RunLogger) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_RUN_SECONDS)
        stale_run_ids = self.store.cleanup_stale_runs(cutoff.isoformat())
        if stale_run_ids:
            logger.log(
                f"stale_runs_marked_failed count={len(stale_run_ids)} ids={stale_run_ids}"
            )
    def _process_sources(
        self,
        sources: list[Source],
        run_id: int,
        logger: RunLogger,
        stats: RunStats,
    ) -> None:
        if len(sources) <= 1:
            for source in sources:
                self._process_source(source, run_id, logger, stats)
            return
        max_workers = min(SOURCE_CONCURRENCY_LIMIT, len(sources))
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._process_source_thread, source, run_id, logger)
                for source in sources
            ]
            for future in as_completed(futures):
                self._merge_stats(stats, future.result())
    def _process_source_thread(
        self,
        source: Source,
        run_id: int,
        logger: RunLogger,
    ) -> RunStats:
        local_stats = RunStats()
        thread_store = Store(root=self.root)
        thread_ingestor = Ingestor(thread_store, root=self.root)
        thread_ingestor._process_source(source, run_id, logger, local_stats)
        thread_store.close()
        return local_stats
    def _merge_stats(self, target: RunStats, delta: RunStats) -> None:
        target.total_items += delta.total_items
        target.new_items += delta.new_items
        target.updated_items += delta.updated_items
        target.errors_count += delta.errors_count
    def _validate_slug_overlap(self) -> None:
        registry = {row["slug"] for row in self.store.list_sources()}
        overlap = registry.intersection(set(index_slugs()))
        if overlap:
            raise ValueError(f"Index allowlist overlaps source registry: {sorted(overlap)}")
    def _run_index_sources(self, source_slugs: list[str] | None, logger: RunLogger) -> None:
        allowlist = index_slugs()
        if source_slugs is not None:
            allowlist = [slug for slug in allowlist if slug in source_slugs]
        for slug in allowlist:
            run_index_source(self.root, logger, slug)
    def _record_error(
        self,
        run_id: int,
        logger: RunLogger,
        stats: RunStats,
        source_id: int | None,
        url: str | None,
        stage: str,
        error_code: str,
        message: str,
        http_status: int | None = None,
    ) -> None:
        self.store.record_error(
            run_id,
            source_id,
            url,
            stage,
            http_status,
            error_code,
            message,
        )
        logger.failure(
            {
                "run_id": run_id,
                "source_id": source_id,
                "url": url,
                "stage": stage,
                "error_code": error_code,
                "message": message,
                "http_status": http_status,
            }
        )
        stats.errors_count += 1

    def _load_sources(self, source_slugs: list[str] | None) -> list[Source]:
        source_rows = self.store.list_sources()
        sources = [_source_from_row(row) for row in source_rows]
        if source_slugs:
            sources = [s for s in sources if s.slug in source_slugs]
        return [s for s in sources if s.enabled]

    def _process_source(
        self,
        source: Source,
        run_id: int,
        logger: RunLogger,
        stats: RunStats,
    ) -> None:
        try:
            adapter = adapter_for_mode(source.policy.mode)
        except AdapterError as exc:
            logger.log(f"source={source.slug} error=adapter {exc}")
            self._record_error(run_id, logger, stats, source.id, None, "list", "adapter", str(exc))
            return

        session = build_session(source.config.get("user_agent"))
        throttle = Throttle(source.policy)
        candidates = self._discover_candidates(
            adapter,
            source,
            session,
            throttle,
            run_id,
            logger,
            stats,
        )
        if candidates is None:
            return

        fetch_jobs = self._build_fetch_jobs(source, candidates, run_id, stats)
        if fetch_jobs:
            outcomes = self._run_fetch_jobs(adapter, source, throttle, fetch_jobs)
            self._apply_outcomes(source, outcomes, session, run_id, logger, stats)
        logger.log(f"source={source.slug} items={len(candidates)}")

    def _discover_candidates(
        self,
        adapter: Any,
        source: Source,
        session: requests.Session,
        throttle: Throttle,
        run_id: int,
        logger: RunLogger,
        stats: RunStats,
    ) -> list[ItemCandidate] | None:
        try:
            throttle.wait()
            return adapter.discover(source, session)
        except Exception as exc:
            logger.log(f"source={source.slug} error=list {exc}")
            self._record_error(run_id, logger, stats, source.id, None, "list", "list", str(exc))
            return None

    def _build_fetch_jobs(
        self,
        source: Source,
        candidates: list[ItemCandidate],
        run_id: int,
        stats: RunStats,
    ) -> list[FetchJob]:
        fetch_jobs: list[FetchJob] = []
        for candidate in candidates:
            stats.total_items += 1
            item_key = candidate.item_key or candidate.canonical_url
            if not item_key:
                continue
            item_id, created = self.store.upsert_item(
                source.id,
                item_key,
                candidate.canonical_url,
                candidate.title,
                candidate.author,
                candidate.published_at,
                run_id,
            )
            if created:
                stats.new_items += 1

            should_fetch = created or source.policy.always_refetch
            if not should_fetch:
                continue
            fetch_jobs.append(FetchJob(candidate=candidate, item_id=item_id, item_key=item_key))
        return fetch_jobs

    def _run_fetch_jobs(
        self,
        adapter: Any,
        source: Source,
        throttle: Throttle,
        fetch_jobs: list[FetchJob],
    ) -> list[FetchOutcome]:
        concurrency = max(1, int(source.policy.concurrency or 1))
        user_agent = source.config.get("user_agent")
        if concurrency <= 1:
            return [
                fetch_candidate(
                    adapter,
                    job,
                    source.config,
                    throttle,
                    user_agent,
                )
                for job in fetch_jobs
            ]
        from concurrent.futures import ThreadPoolExecutor, as_completed

        outcomes: list[FetchOutcome] = []
        executor = ThreadPoolExecutor(max_workers=concurrency)
        futures = [
            executor.submit(
                fetch_candidate,
                adapter,
                job,
                source.config,
                throttle,
                user_agent,
            )
            for job in fetch_jobs
        ]
        interrupted = False
        try:
            for future in as_completed(futures):
                outcomes.append(future.result())
        except KeyboardInterrupt:
            interrupted = True
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        finally:
            if not interrupted:
                executor.shutdown(wait=True)
        return outcomes

    def _apply_outcomes(
        self,
        source: Source,
        outcomes: list[FetchOutcome],
        session: requests.Session,
        run_id: int,
        logger: RunLogger,
        stats: RunStats,
    ) -> None:
        for outcome in outcomes:
            self._handle_outcome(source, outcome, session, run_id, logger, stats)

    def _handle_outcome(
        self,
        source: Source,
        outcome: FetchOutcome,
        session: requests.Session,
        run_id: int,
        logger: RunLogger,
        stats: RunStats,
    ) -> None:
        candidate = outcome.job.candidate
        item_id = outcome.job.item_id
        item_key = outcome.job.item_key
        if outcome.error:
            logger.log(
                f"source={source.slug} item={item_id} error={outcome.error.code} "
                f"{outcome.error.message}"
            )
            self._record_error(
                run_id,
                logger,
                stats,
                source.id,
                outcome.error.url,
                outcome.error.stage,
                outcome.error.code,
                outcome.error.message,
            )
            return
        if outcome.comments_error:
            logger.log(
                f"source={source.slug} item={item_id} error=comments "
                f"{outcome.comments_error.message}"
            )
            self._record_error(
                run_id,
                logger,
                stats,
                source.id,
                outcome.comments_error.url,
                outcome.comments_error.stage,
                outcome.comments_error.code,
                outcome.comments_error.message,
            )

        raw_markdown = outcome.raw_markdown or ""
        hash_input = raw_markdown
        if outcome.comments_markdown:
            hash_input = f"{raw_markdown}\n\n{outcome.comments_markdown}"
        content_hash = hash_content(hash_input)
        if self.store.has_version_hash(item_id, content_hash):
            return

        extracted_at = now_utc()
        version_id, version_index = self.store.create_item_version(
            item_id,
            content_hash,
            "pending",
            extracted_at,
            run_id,
            candidate.title,
            candidate.published_at,
            len(raw_markdown.split()),
        )

        markdown_with_assets, assets = download_assets(
            self.root,
            source.slug,
            item_key,
            version_index,
            raw_markdown,
            candidate.detail_url,
            session,
        )

        front_matter = {
            "item_id": item_id,
            "source_id": source.id,
            "canonical_url": candidate.canonical_url or None,
            "comment_url": candidate.comment_url or None,
            "title": candidate.title,
            "published_at": candidate.published_at,
            "version_id": version_id,
            "content_hash": content_hash,
            "extracted_at": extracted_at,
            "run_id": run_id,
        }

        try:
            content_path = write_markdown(
                self.root,
                source.slug,
                item_key,
                version_index,
                markdown_with_assets,
                front_matter,
            )
        except Exception as exc:
            logger.log(f"source={source.slug} item={item_id} error=write {exc}")
            self._record_error(
                run_id,
                logger,
                stats,
                source.id,
                candidate.detail_url,
                "detail",
                "write",
                str(exc),
            )
            self.store.delete_item_version(version_id)
            return
        if outcome.comments_markdown:
            comments_front_matter = {
                "item_id": item_id,
                "source_id": source.id,
                "canonical_url": candidate.canonical_url or None,
                "comment_url": candidate.comment_url or None,
                "title": candidate.title,
                "published_at": candidate.published_at,
                "version_id": version_id,
                "content_hash": content_hash,
                "extracted_at": extracted_at,
                "run_id": run_id,
                "content_kind": "comments",
                "comment_count": outcome.comments_count,
            }
            try:
                write_markdown(
                    self.root,
                    source.slug,
                    item_key,
                    version_index,
                    outcome.comments_markdown,
                    comments_front_matter,
                    filename="comments.md",
                )
            except Exception as exc:
                logger.log(f"source={source.slug} item={item_id} error=comments_write {exc}")
                self._record_error(
                    run_id,
                    logger,
                    stats,
                    source.id,
                    candidate.comment_url or candidate.detail_url,
                    "comments",
                    "write",
                    str(exc),
                )
        self.store.update_version_content_path(version_id, content_path, self.root)
        self.store.record_assets(version_id, assets)
        for asset in assets:
            if asset.get("status") != "stored":
                self._record_error(
                    run_id,
                    logger,
                    stats,
                    source.id,
                    asset.get("url"),
                    "assets",
                    asset.get("status") or "asset",
                    "Asset download failed",
                )
        stats.updated_items += 1
