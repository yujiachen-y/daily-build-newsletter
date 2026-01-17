## Context
The newsletter system needs a local-first article ingestion module that can crawl diverse sources, detect updates, store versioned Markdown content, and support manual recovery of failed crawls.

## Goals / Non-Goals
- Goals:
  - Provide a reliable ingest pipeline with per-source policy control and run tracking.
  - Store extracted content as Markdown with full version history.
  - Support manual import of HTML/Markdown with consistent metadata.
- Non-Goals:
  - Building a web UI or server deployment.
  - Bypassing paywalls or CAPTCHAs.

## Decisions
- Decision: Use Python for the ingest toolchain.
- Decision: Persist structured metadata in SQLite and store Markdown content in the filesystem.
- Decision: Treat content hash changes as version updates and preserve all versions.
- Decision: Do not write content files when detail download or extraction fails; log errors instead.
- Decision: Support both HTML and Markdown manual imports via an inbox workflow.
- Decision: Store Markdown with YAML front matter for system metadata.

## Risks / Trade-offs
- Anti-scraping limits can cause partial runs; mitigation is per-source policy, backoff, and error logging.
- Extraction quality varies by site; mitigation is multiple extraction strategies and fixtures for regressions.

## Migration Plan
- None. This is a new capability.

## Open Questions
- None currently.
