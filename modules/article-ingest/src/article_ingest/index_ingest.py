from __future__ import annotations

from pathlib import Path

from .index_fetchers import fetch_index_entries
from .index_models import IndexFetchStats
from .index_render import render_daily_markdown
from .index_storage import local_run_date, write_daily_markdown, write_index_stats
from .run_logger import RunLogger


def run_index_source(root: Path, logger: RunLogger, source_slug: str) -> None:
    run_date = local_run_date()
    daily_path = root / "daily" / source_slug / f"{run_date}.md"
    if daily_path.exists():
        logger.log(f"index source={source_slug} skipped reason=already_exists")
        write_index_stats(
            root,
            source_slug,
            run_date,
            IndexFetchStats(requests=0, errors=0, duration_ms=0),
            items_count=0,
            comments_count=0,
            errors=[],
            skipped=True,
        )
        return
    result = fetch_index_entries(source_slug)
    markdown = render_daily_markdown(
        source_slug,
        result.entries,
        result.stats,
        result.errors,
        run_date,
    )
    write_daily_markdown(root, source_slug, markdown, run_date)
    write_index_stats(
        root,
        source_slug,
        run_date,
        result.stats,
        items_count=len(result.entries),
        comments_count=sum(len(entry.comments) for entry in result.entries),
        errors=result.errors,
        skipped=False,
    )
    logger.log(
        f"index source={source_slug} items={len(result.entries)} errors={result.stats.errors}"
    )


def list_index_sources():
    from . import index_sources

    return index_sources.list_index_sources()


def index_slugs():
    from . import index_sources

    return index_sources.index_slugs()
