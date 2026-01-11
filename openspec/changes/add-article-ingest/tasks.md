## 1. Implementation
- [x] 1.1 Create module scaffolding under modules/article-ingest
- [x] 1.2 Implement storage layer (SQLite schema + content FS layout)
- [x] 1.3 Implement source registry and per-source policy enforcement
- [x] 1.4 Implement ingest orchestrator with run tracking and error logging
- [x] 1.5 Implement content extraction to Markdown, normalization, and hashing
- [x] 1.6 Implement manual import workflow for HTML/Markdown inputs
- [x] 1.7 Implement CLI commands (ingest, updates, item, source, runs)
- [x] 1.8 Add unit and fixture-based adapter tests
- [x] 1.9 Add module README documenting usage and interfaces

## 2. Pending Sources (Not Yet Added)
- [x] 2.1 https://blog.pragmaticengineer.com/
- [x] 2.2 https://stratechery.com/
- [x] 2.3 https://paulgraham.com/articles.html
- [x] 2.4 https://www.ben-evans.com/
- [x] 2.5 https://foundersfund.com/anatomy-of-next/
- [ ] 2.6 https://deeperlearning.producthunt.com/archive (Cloudflare managed challenge: /cdn-cgi/challenge-platform; list blocked as of 2026-01-11)
- [x] 2.7 https://trends.vc/archive/
- [x] 2.8 https://fs.blog/blog/
- [x] 2.9 https://01.me/archives/
- [x] 2.10 https://blog.fsck.com/
- [x] 2.11 https://lucumr.pocoo.org/
- [x] 2.12 https://sorrycc.com/archive
- [x] 2.13 https://huyenchip.com/blog/
- [x] 2.14 https://antirez.com/latest/0
- [x] 2.15 https://gwern.net/changelog
- [x] 2.16 https://lilianweng.github.io/archives/

## 3. Known Issues / Follow-ups
- [ ] 3.1 Releasebot pagination: `offset` parameter does not advance; currently capped to latest 10 items.
- [ ] 3.2 Hugging Face Papers detail pages can return upload prompt content; add blocked-text detection for that pattern and re-run cleanup.
- [ ] 3.3 Data sampling (3–5 items/source) shows gaps that need remediation:
  - No data present in `data/` for: antirez, blog-fsck, deeper-learning, gwern-changelog, huyenchip, lilian-weng, lucumr, sorrycc.
  - hf-blog: items exist but no versions/content stored (content lookup returns “Content not found for item/version”).
  - hn: sample shows intermittent missing content (2/5 items missing).
  - founders-fund-anatomy, 01-me: occasional missing content (1/5 each).
- [ ] 3.4 Prefer official feeds/APIs where available (reduce scrape failures):
  - Product Hunt: use official API endpoints where possible for newsletters/archives.
  - GitHub: use public site endpoints or GitHub API for release/issue/news sources.
  - Hacker News: use Firebase API and/or RSS feeds to avoid item HTML fetch gaps.
