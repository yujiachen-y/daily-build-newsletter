from __future__ import annotations

from .front_matter import build_front_matter
from .index_models import IndexComment, IndexEntry, IndexFetchStats
from .timestamps import now_utc


def _render_meta_line(entry: IndexEntry) -> str:
    parts: list[str] = []
    if entry.author:
        parts.append(f"author={entry.author}")
    if entry.published_at:
        parts.append(f"published_at={entry.published_at}")
    if entry.comments_count is not None:
        parts.append(f"comments={entry.comments_count}")
    if entry.score is not None:
        parts.append(f"score={entry.score}")
    if entry.external_link_missing:
        parts.append("external_link=none")
    if not parts:
        return "meta:"
    return "meta: " + " ".join(parts)


def _render_summary_line(entry: IndexEntry) -> str | None:
    if not entry.summary:
        return None
    summary = " ".join(entry.summary.split())
    return f"summary: {summary}"


def _render_tags_line(entry: IndexEntry) -> str | None:
    if not entry.tags:
        return None
    return f"tags: {', '.join(entry.tags)}"


def _render_comments(comments: list[IndexComment]) -> list[str]:
    lines: list[str] = []
    if not comments:
        return lines
    lines.append("### Comments")
    for comment in comments:
        indent = "  " * comment.depth
        author = comment.author or "unknown"
        header = f"{indent}- **{author}**"
        if comment.created_at:
            header = f"{header} · {comment.created_at}"
        if comment.is_deleted:
            header = f"{header} (deleted)"
        lines.append(header)
        body = comment.body.strip() if comment.body else ""
        if body:
            for line in body.splitlines():
                lines.append(f"{indent}  {line.strip()}")
    return lines


def render_daily_markdown(
    source_slug: str,
    entries: list[IndexEntry],
    stats: IndexFetchStats,
    errors: list[str],
    run_date_local: str,
) -> str:
    front_matter = build_front_matter(
        {
            "source_slug": source_slug,
            "generated_at": now_utc(),
            "run_date_local": run_date_local,
            "items_count": len(entries),
            "comments_count": sum(len(entry.comments) for entry in entries),
            "truncated": False,
            "fetch_stats": {
                "requests": stats.requests,
                "duration_ms": stats.duration_ms,
                "errors": stats.errors,
            },
            "errors": errors if errors else None,
        }
    )
    lines: list[str] = [front_matter.strip(), ""]
    for entry in entries:
        lines.append(f"## {entry.title}")
        lines.append(_render_meta_line(entry))
        lines.append(f"link: {entry.url}")
        summary_line = _render_summary_line(entry)
        if summary_line:
            lines.append(summary_line)
        tags_line = _render_tags_line(entry)
        if tags_line:
            lines.append(tags_line)
        if entry.details:
            lines.append("")
            lines.extend(entry.details.strip().splitlines())
        lines.extend(_render_comments(entry.comments))
        lines.append("")
    return "\n".join(lines).strip() + "\n"
