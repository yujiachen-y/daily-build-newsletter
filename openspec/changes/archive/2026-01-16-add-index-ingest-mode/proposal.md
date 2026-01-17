# Change: Add index ingest mode to article-ingest

## Why
We need to treat aggregation sources as index-only feeds (titles, links, and comments) without attempting full content extraction, while keeping a single CLI and module.

## What Changes
- Add an index ingest path inside `article-ingest ingest` for a fixed allowlist of aggregation sources.
- Add `--type` filtering to `ingest` and `source list` so operators can select `content`, `index`, or `all`.
- Generate daily Markdown summaries under `modules/article-ingest/data/daily/{source_slug}/YYYY-MM-DD.md` and record index run stats in `modules/article-ingest/data/index/`.
- Implement per-source index fetchers (HN API, Lobsters RSS/JSON, Releasebot, HF Papers API, GitHub Trending fallbacks, Product Hunt RSS).
- **Behavior change:** `ingest` without `--type` runs both content sources and index allowlist.

## Impact
- Affected specs: article-ingest
- Affected code: `modules/article-ingest/src/article_ingest/ingest.py`, new index fetchers, CLI flags, daily output writers
