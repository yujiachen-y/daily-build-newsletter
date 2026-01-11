# Tasks: Add index ingest mode

## 1. Implementation
- [x] 1.1 Add index allowlist and slug overlap validation (fail fast) in ingest flow.
- [x] 1.2 Add `--type` filtering to `ingest` and `source list` (`content|index|all`).
- [x] 1.3 Implement index ingest orchestration inside `ingest.py` (no new commands).
- [x] 1.4 Implement per-source index fetchers:
  - HN (Firebase API + BFS comments, max 50)
  - Lobsters (RSS list + story.json fallback)
  - Releasebot (list + published_at ordering)
  - HF Papers (API)
  - GitHub Trending (HTML → RSS → community API → Search)
  - Product Hunt (RSS)
- [x] 1.5 Implement daily Markdown renderer with YAML front matter and nested comment lists.
- [x] 1.6 Write index run stats under `modules/article-ingest/data/index/`.
- [x] 1.7 Add tests for index fetchers, comment BFS, renderer, and `--type` filtering.

## 2. Documentation
- [x] 2.1 Update module README with index mode behavior and `--type` flags.
