## 0. Research
- [x] 0.1 Document recommended access method for each source in design.md

## 1. Implementation
- [x] 1.1 Create module scaffolding under modules/article-harvest (pyproject, package, CLI entrypoint)
- [x] 1.2 Define local data root layout and write helpers for metadata/content files
- [x] 1.3 Add source registry + per-source script interface (single retrieval method per source)
- [x] 1.4 Implement ingest orchestrator (all sources + single source) with run logging and failure capture
- [x] 1.5 Implement query layer (by source, keyword/title match, archive date/range) for CLI + Python API
- [x] 1.6 Add CLI commands + Python API wrappers for ingest + queries
- [x] 1.7 Add unit tests and fixtures to satisfy coverage gates
- [x] 1.8 Add module README with usage and data layout
- [x] 1.9 Implement E2E runner that executes a source ingest and validates stored output

## 2. Aggregation Sources (one source per commit, run E2E x3 before commit)
- [x] 2.1 Hacker News (Firebase API + top 20 comments)
- [x] 2.2 Lobsters (JSON API)
- [x] 2.3 Releasebot (JSON data)
- [x] 2.4 Hugging Face Papers (daily_papers API)
- [x] 2.5 GitHub Trending (GitHub Search API)
- [x] 2.6 Product Hunt (RSS feed)
- [x] 2.7 Papers with Code (skipped: no stable access identified)

## 3. Blog Sources (one source per commit, run E2E x3 before commit)
- [x] 3.1 01.me (Atom)
- [x] 3.2 antirez (RSS)
- [x] 3.3 Ben Evans (RSS)
- [x] 3.4 Founders Fund Anatomy of Next (WordPress API)
- [x] 3.5 Farnam Street (RSS)
- [x] 3.6 gwern changelog (RSS)
- [x] 3.7 Hugging Face blog (RSS)
- [x] 3.8 Huyen Chip blog (RSS)
- [x] 3.9 Latent Space (RSS)
- [x] 3.10 Lilian Weng archives (RSS)
- [x] 3.11 lucumr blog (Atom)
- [x] 3.12 Paul Graham articles (RSS)
- [x] 3.13 Pragmatic Engineer (RSS)
- [x] 3.14 Simon Willison blog (Atom)
- [x] 3.15 sorrycc archive (RSS)
- [x] 3.16 Stratechery (RSS)
- [x] 3.17 Trends.vc archive (RSS)

## 4. SQLite Storage Layer (after all sources are implemented)
- [x] 4.1 Define shared fields and schema based on collected sources
- [x] 4.2 Implement SQLite index/storage layer that mirrors file data
- [x] 4.3 Update CLI + Python API to query via SQLite when present (fallback to file scan)
- [x] 4.4 Add migration/bootstrapping command to build SQLite from existing files
- [x] 4.5 Add tests covering SQLite indexing and query parity
