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
- [ ] 2.1 https://blog.pragmaticengineer.com/
- [ ] 2.2 https://stratechery.com/
- [ ] 2.3 https://paulgraham.com/articles.html
- [ ] 2.4 https://www.ben-evans.com/
- [ ] 2.5 https://foundersfund.com/anatomy-of-next/
- [ ] 2.6 https://deeperlearning.producthunt.com/archive
- [ ] 2.7 https://trends.vc/archive/
- [ ] 2.8 https://fs.blog/blog/
- [ ] 2.9 https://01.me/archives/
- [ ] 2.10 https://blog.fsck.com/
- [ ] 2.11 https://lucumr.pocoo.org/
- [ ] 2.12 https://sorrycc.com/archive
- [ ] 2.13 https://huyenchip.com/blog/
- [ ] 2.14 https://antirez.com/latest/0
- [ ] 2.15 https://gwern.net/changelog
- [ ] 2.16 https://lilianweng.github.io/archives/

## 3. Known Issues / Follow-ups
- [ ] 3.1 Releasebot pagination: `offset` parameter does not advance; currently capped to latest 10 items.
- [ ] 3.2 Hugging Face Papers detail pages can return upload prompt content; add blocked-text detection for that pattern and re-run cleanup.
