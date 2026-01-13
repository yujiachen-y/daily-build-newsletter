# Article Harvest Module

Local-first ingestion for newsletter sources. This module stores source snapshots and blog items in the filesystem, with optional SQLite indexing added later.

## Layout

```
modules/article-harvest/
├── data/
│   ├── runs/run-YYYYMMDD-HHMMSS.json
│   ├── index.sqlite               # optional SQLite index
│   └── sources/{source_id}/
│       ├── manifest.jsonl            # blog items only
│       ├── items/{item_id}/
│       │   ├── meta.json
│       │   └── content.md
│       └── snapshots/YYYY-MM-DD.json # aggregation sources
└── src/article_harvest/
```

All data lives under `modules/article-harvest/data/` and is ignored by git.

## Quick Start

Install dependencies (from this directory):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run an ingest:

```bash
article-harvest ingest
```

Ingest a single source:

```bash
article-harvest ingest --source hn
```

List sources:

```bash
article-harvest sources
```

Query by source:

```bash
article-harvest query source hn
```

Items with local content are prefixed with `*` in text output.

Query by keyword:

```bash
article-harvest query keyword "llm" --source hn
```

Query by archive date or range:

```bash
article-harvest query archive --on 2026-01-13
article-harvest query archive --from 2026-01-01 --to 2026-01-13
```

Build or rebuild the SQLite index (optional):

```bash
article-harvest sqlite rebuild
```

JSON output (for scripting):

```bash
article-harvest query source hn --json
```

Read a stored blog item by id:

```bash
article-harvest read antirez <item_id>
```

Use `--json` to retrieve `item_id` and `has_content` flags from queries.

## Python API

```python
from article_harvest import ingest_all, ingest_source, rebuild_sqlite_index
from article_harvest import query_by_archive_date, query_by_keyword, query_by_source
from article_harvest.sources.registry import get_source
from article_harvest.storage import Storage

report = ingest_all()
storage = Storage()
source = get_source("hn")
items = query_by_source(storage, source)
sqlite_report = rebuild_sqlite_index()
```

## Notes

- Each source uses a single retrieval method (API, RSS, HTML, or agent-based browser) with no runtime fallback.
- If a source fails to fetch, the failure is recorded and the run continues.
- End-to-end validation runs should be executed against live sources before committing a new source.
- SQLite indexing is optional and only used for queries when `index.sqlite` exists.
