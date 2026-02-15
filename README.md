# Daily Build Newsletter

A local-first toolkit for harvesting articles from tech news sources, blogs, and research feeds — then turning them into a curated daily newsletter.

## What It Does

**Article Harvest** (`modules/article-harvest/`) is a Python CLI that pulls content from 30+ sources, stores snapshots locally, and provides query tools for filtering and searching. Sources include:

- **Aggregators**: Hacker News, Lobsters, GitHub Trending, Hugging Face Papers, Product Hunt, Release Bot
- **Tech Blogs**: Paul Graham, Simon Willison, Antirez, Lilian Weng, Gwern, Huyen Chip, Armin Ronacher, and more
- **Industry**: OpenAI Blog, Claude/Anthropic Blog, Vercel Blog, Stratechery, Pragmatic Engineer, Crunchbase News, Techmeme

Data is stored as flat files (JSON + Markdown) under a local `data/` directory (git-ignored). An optional SQLite index enables faster queries.

## Quick Start

```bash
# Clone and set up
git clone https://github.com/yujiachen-y/daily-build-newsletter.git
cd daily-build-newsletter/modules/article-harvest

# Create virtualenv and install
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Fetch articles from all sources
article-harvest ingest

# Query today's articles
article-harvest query archive --on $(date +%Y-%m-%d)

# Query a specific source
article-harvest query source hn

# Search by keyword
article-harvest query keyword "llm" --source hn

# List all available sources
article-harvest sources
```

## Project Structure

```
daily-build-newsletter/
├── modules/article-harvest/     # Core harvesting module (Python CLI)
│   ├── src/article_harvest/     #   Implementation
│   ├── tests/                   #   pytest test suite
│   └── data/                    #   Local run artifacts (git-ignored)
├── openspec/                    # Spec-driven development docs
│   ├── specs/                   #   Capability specifications
│   └── changes/                 #   Change proposals (archived)
├── editorial_workspace/         # Newsletter drafts (YYYY-MM-DD-*.md)
├── docs/                        # Reports and analysis
└── scripts/                     # Repo-level utilities
```

## Development

```bash
cd modules/article-harvest

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Format
ruff format .
```

Requires Python 3.10+.

## CLI Reference

| Command | Description |
|---|---|
| `article-harvest ingest` | Fetch all sources |
| `article-harvest ingest --source hn` | Fetch a single source |
| `article-harvest sources` | List registered sources |
| `article-harvest query source <id>` | Query items from a source |
| `article-harvest query keyword <term>` | Search by keyword |
| `article-harvest query archive --on YYYY-MM-DD` | Query by date |
| `article-harvest query archive --from ... --to ...` | Query date range |
| `article-harvest read <source> <item_id>` | Read stored content |
| `article-harvest sqlite rebuild` | Rebuild SQLite index |

Add `--json` to any query command for machine-readable output.

## License

MIT
