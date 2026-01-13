# Change: Add article harvest module

## Why
We need a simpler, local-first ingest module that stores articles in the filesystem, supports per-source scripts, and exposes CLI/Python queries. SQLite will be introduced only after all sources are implemented.

## What Changes
- Add a new module under modules/ with its own CLI and Python API, running alongside the existing article-ingest module.
- Store all ingest data under a single module-local data directory and ignore it in .gitignore.
- Implement per-source scripts with one chosen retrieval method each (official API, RSS/Atom, HTML, or agent-based browser), no runtime fallback.
- Add aggregation snapshots (daily) and blog update detection, with HN top-20 comments captured.
- Provide query interfaces by source, keyword (title match), and archive date/range.
- After all sources are implemented, add a SQLite-backed index/storage layer without breaking the file-based workflow.

## Impact
- Affected specs: article-harvest (new)
- Affected code: new module under modules/article-harvest, root .gitignore
