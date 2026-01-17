## Context
We are adding a new, local-first ingest module that runs alongside the existing article-ingest module. The new module should prioritize simplicity, per-source scripts, and filesystem storage first, then add SQLite indexing after all sources are implemented.

## Goals / Non-Goals
- Goals:
  - Local file storage under a single data root directory per module.
  - Per-source scripts with a single chosen retrieval method.
  - Aggregation daily snapshots and blog update detection.
  - CLI + Python API for ingest and queries (source/keyword/date).
  - Failfast behavior and minimal abstraction.
  - Add SQLite index/storage after all sources are implemented.
- Non-Goals:
  - Multi-layer retry or automatic fallback between multiple retrieval methods.
  - Production-grade scaling, scheduling, or observability.

## Decisions
- Module name: `article-harvest` (package `article_harvest`, CLI `article-harvest`).
- Data root: `modules/article-harvest/data/` and ignore it in `.gitignore`.
- Storage layout: one subdirectory per source under the data root; each source stores daily snapshots or blog items and a lightweight manifest for querying.
- Source registry: a simple registry listing source id, type (aggregation/blog), and the script used to fetch it.
- Retrieval method selection: each source chooses exactly one method (official API, RSS/Atom, HTML, or agent-based browser) decided during implementation; no runtime fallback.
- Ingest orchestration: a single `ingest` entrypoint runs all sources or a specified source and records failures without stopping the entire run.
- Query strategy: scan source manifests to filter by source, keyword in title, and archive date/range.
- SQLite index/storage: introduced after all sources are implemented; file data remains source of truth.
- Source inclusion: if a source cannot be accessed with its chosen method after reasonable effort, mark it skipped and move on.
- E2E validation: run a live ingest for each source three times before committing that source.

## Source Access Research (recommended methods)
Aggregation sources:
- hn: Hacker News Firebase API (`https://hacker-news.firebaseio.com/v0`) + sort by comment count; use API for comments.
- lobsters: JSON API (`https://lobste.rs/hottest.json`).
- releasebot: JSON data endpoint (`https://releasebot.io/updates/__data.json`).
- hf-papers: Hugging Face daily papers API (`https://huggingface.co/api/daily_papers`).
- github-trending: GitHub Search API (`https://api.github.com/search/repositories`) with recent-created window, avoid HTML scraping.
- product-hunt: RSS feed (`https://www.producthunt.com/feed`).
- papers-with-code: currently behind HF WAF/JS; no stable unauth access identified. Skip unless a stable API is found.

Blog sources:
- 01.me: Atom feed (`https://01.me/atom.xml`).
- antirez: RSS feed (`https://antirez.com/rss`).
- ben-evans: RSS feed (`https://www.ben-evans.com/benedictevans?format=rss`).
- founders-fund-anatomy: WordPress REST API (`https://foundersfund.com/wp-json/wp/v2/posts?categories=21&per_page=30`).
- fs-blog: RSS feed (`https://fs.blog/feed/`).
- gwern-changelog: RSS feed (`https://gwern.net/rss`).
- hf-blog: RSS feed (`https://huggingface.co/blog/feed.xml`).
- huyenchip: RSS feed (`https://huyenchip.com/feed.xml`).
- latent-space: RSS feed (`https://www.latent.space/feed`).
- lilian-weng: RSS feed (`https://lilianweng.github.io/index.xml`).
- lucumr: Atom feed (`https://lucumr.pocoo.org/feed.atom`).
- paul-graham: RSS feed (`http://www.aaronsw.com/2002/feeds/pgessays.rss`).
- pragmatic-engineer: RSS feed (`https://newsletter.pragmaticengineer.com/feed`).
- simon: Atom feed (`https://simonwillison.net/atom/everything/`).
- sorrycc: RSS feed (`https://sorrycc.com/feed`).
- stratechery: RSS feed (`https://stratechery.com/feed/`).
- trends-vc: RSS feed (`https://trends.vc/feed/`).

## Risks / Trade-offs
- File scanning for queries may be slower than SQLite, but acceptable for local usage.
- Single retrieval method per source may break when sites change; failures are expected and fixed iteratively.
- GitHub API rate limits may affect repeated E2E runs; keep request volume low.

## Migration Plan
- Scaffold the module and core ingest/query workflow.
- Add sources one by one with an E2E (x3) validation and a commit after each source.
- Defer SQLite design until stable, shared data fields emerge.

## Open Questions
- Final manifest format per source (JSON lines vs. per-item JSON).
- Whether to include any shared metadata normalization utilities across sources.
