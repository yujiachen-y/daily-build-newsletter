# Change: Add article ingest module

## Why
We need a local, versioned ingestion module to collect articles from multiple sources and track updates over time for a larger newsletter system.

## What Changes
- Add a new article ingest capability with local storage, versioning, and update detection.
- Provide CLI and Python API for ingest and retrieval.
- Define a manual import workflow for failed crawls.
- Define source policies for anti-scraping resilience.

## Impact
- Affected specs: article-ingest
- Affected code: new module under modules/article-ingest (not created yet)
