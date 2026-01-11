# Design: Index ingest mode

## Context
Aggregation sources (HN, Lobsters, Releasebot, HF Papers, GitHub Trending, Product Hunt RSS) should be treated as index-only feeds. We want a single CLI (`article-ingest ingest`) with minimal configuration and no new modules.

## Goals / Non-Goals
- Goals:
  - Integrate index ingestion into the existing ingest flow without new commands.
  - Produce daily Markdown summaries with titles, links, metadata, and comments where applicable.
  - Keep index sources hard-coded to avoid extra configuration overhead.
  - Fail fast if index slugs overlap with registry slugs.
- Non-Goals:
  - Storing item versions for index sources.
  - Adding schema changes or data migrations.
  - Extending runs/updates views to index runs.

## Decisions
- Decision: `ingest` runs both content registry sources and index allowlist by default; `--type` filters to `content|index|all`.
- Decision: Index sources are a hard-coded allowlist and do not consult the source registry.
- Decision: Index runs write daily Markdown to `modules/article-ingest/data/daily/{source_slug}/YYYY-MM-DD.md` and skip if the file already exists.
- Decision: Index run stats are stored in `modules/article-ingest/data/index/` with counts and request/error totals.
- Decision: HN/Lobsters only use homepage lists; comments are collected BFS up to 50 per story and rendered as nested Markdown lists.
- Decision: Releasebot is sorted by published_at; other index sources preserve feed order.
- Decision: No size cap on daily Markdown output.

## Risks / Trade-offs
- Hard-coded allowlist reduces configurability but avoids accidental misclassification.
- Defaulting `ingest` to run index sources increases runtime/network usage; `--type` mitigates this.
- Without schema changes, index runs are not visible in existing run history tables.

## Migration Plan
- None. Index mode is additive; no data migration required.

## Open Questions
- None.
