## Context
We are adding additional newsletter/blog sources to the article-harvest module. Each source must use a single, recommended retrieval method.

## Decisions
- Prefer RSS/Atom feeds when available.
- Use HTML parsing only if no stable feed exists.
- Use agent-browser only if RSS/HTML fail or content is rendered in a hard-to-access iframe.
- If access is blocked or unstable, skip the source and record the reason.

## Source Access Research (recommended methods)
- lennysnewsletter: Substack RSS feed at `https://www.lennysnewsletter.com/feed`.
- mailchimp-archive: Mailchimp RSS feed derived from the archive URL `https://us7.campaign-archive.com/feed?u=6507bf4e4c2df3fdbae6ef738&id=547725049b`.
- crunchbase-news: RSS feed at `https://news.crunchbase.com/feed/`.
- cbinsights-newsletter: CloudFront blocks RSS/HTML (403 in direct HTTP). Try agent-browser; if still blocked, skip.
- techmeme: RSS feed at `https://techmeme.com/feed.xml`.
- alphasignal-last-email: Page uses an iframe with dynamic content; use agent-browser to extract iframe srcdoc.

## E2E Validation
Each source requires three successful live E2E runs before commit.
