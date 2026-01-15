# Change: Add more article-harvest sources

## Why
We need to extend the article-harvest module with additional newsletter/blog sources requested by users.

## What Changes
- Add new sources to article-harvest (RSS where available, HTML/agent where required).
- Update the source registry with the new sources.
- Validate each source with E2E ingest runs (x3 per source) before committing.

## Impact
- Affected specs: article-harvest
- Affected code: modules/article-harvest/src/article_harvest/sources, registry
