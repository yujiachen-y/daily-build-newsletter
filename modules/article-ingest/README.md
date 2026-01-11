# Article Ingest Module

Local-first article ingestion for newsletter sources. This module stores versioned Markdown content with YAML front matter in the filesystem and uses SQLite for indexing, runs, and error logs.

## Layout

```
modules/article-ingest/
├── data/
│   ├── index.sqlite
│   ├── content/{source_slug}/{item_slug}/v{version_index}/content.md
│   ├── content/{source_slug}/{item_slug}/v{version_index}/comments.md
│   ├── logs/run-<id>.log
│   ├── failures/run-<id>.jsonl
│   └── inbox/
└── src/article_ingest/
```

## Quick Start

Install dependencies (from this directory):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run an ingest:

```bash
article-ingest ingest
```

Show updates from the latest run:

```bash
article-ingest updates
```

List items (optionally filter by source):

```bash
article-ingest items --source lobsters
```

Show comments for an item (if available):

```bash
article-ingest item comments <item_id>
```

## Sources

Add a source (policy + config as JSON):

```bash
article-ingest source add "hn" "Hacker News" "https://news.ycombinator.com" \
  --policy '{"mode":"html","max_rpm":30,"always_refetch":true}' \
  --config '{"list_url":"https://news.ycombinator.com/","item_selector":".athing","url_selector":".titleline a"}'
```

List sources:

```bash
article-ingest source list
```

### HTML source config (example)

```json
{
  "list_url": "https://example.com/blog",
  "item_selector": ".post",
  "url_selector": "a.post-link",
  "title_selector": ".post-title",
  "date_selector": "time",
  "author_selector": ".byline",
  "summary_selector": ".summary",
  "limit": 20
}
```

### RSS source config (example)

```json
{
  "feed_url": "https://example.com/feed.xml"
}
```

### Source policy notes

- `concurrency`: number of parallel detail/comment fetches per source (default `1`). If you want faster runs, raise this and consider adjusting `max_rpm`.

### Comment sites (HN/Lobsters)

Use adapter modes `"hn"` or `"lobsters"` and set a top-comment limit:

```json
{
  "list_url": "https://news.ycombinator.com/",
  "top_comments_limit": 5,
  "limit": 30
}
```

## Manual Import

Drop files in `data/inbox/{source_slug}/` and run:

```bash
article-ingest import
```

Accepted inputs:
- `post.md` + `post.meta.json`
- `post.html` + `post.meta.json`
- `post.md` or `post.html` + `meta.json` (shared for the folder)

`meta.json` minimal fields:

```json
{
  "canonical_url": "https://example.com/post",
  "title": "Post title",
  "published_at": "2026-01-11T00:00:00+00:00",
  "author": "optional"
}
```

If both `.md` and `.html` exist, `.md` is preferred. Successful imports are archived under `data/inbox/archive/run-<id>/`.

## Front Matter

Each stored Markdown file begins with YAML front matter:

```yaml
---
item_id: 1
source_id: 2
canonical_url: "https://example.com/post"
title: "Post title"
published_at: "2026-01-11T00:00:00+00:00"
version_id: 3
content_hash: "..."
extracted_at: "2026-01-11T00:00:00+00:00"
run_id: 4
---
```

## Tests

```bash
pytest
```
