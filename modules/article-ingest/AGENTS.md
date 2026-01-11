# Article Ingest Instructions

- Do not edit SQLite files or other local data files directly, except for explicit debug work.
- All data operations MUST go through the Article Ingest Python program (prefer `article-ingest` CLI).
- Do not lower or relax test coverage thresholds; add or improve tests to meet required coverage.
- Only consider git status and commits within `modules/article-ingest/`; ignore other modules.
