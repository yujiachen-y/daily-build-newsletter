# article-harvest Specification

## Purpose
Provide a local-first ingestion module (`modules/article-harvest/`) that harvests newsletter and blog sources into a filesystem data store, with an optional SQLite index to speed up queries.

## Requirements
### Requirement: Article Harvest Module
The system SHALL provide a new module named `article-harvest` under `modules/` that operates independently as a standalone module.

#### Scenario: CLI isolation
- **WHEN** a user runs the article-harvest CLI
- **THEN** it reads and writes only the new module's code and data directories

### Requirement: File-Based Storage Root
The system MUST store all ingest data under a single module-local data root directory and MUST ignore that directory in `.gitignore`.

#### Scenario: Data root enforcement
- **WHEN** an ingest run completes
- **THEN** all new files exist only under the module's data root

### Requirement: Filesystem Source-Of-Truth With Optional SQLite Index
The system MUST store harvested data in the filesystem as the source of truth and MAY maintain an optional SQLite index (`index.sqlite`) to speed up queries.

#### Scenario: Query without SQLite index
- **WHEN** `index.sqlite` does not exist
- **THEN** results are derived from filesystem data without any SQLite dependency

### Requirement: Per-Source Script With Single Retrieval Method
The system SHALL implement each source as a standalone script/module that uses exactly one retrieval method chosen during implementation (official API, RSS/Atom, HTML, or agent-based browser).

#### Scenario: No runtime fallback method
- **WHEN** a source fetch fails
- **THEN** the failure is recorded, the run continues with other sources, and the system does not attempt alternative retrieval methods for that source

### Requirement: Aggregation Snapshots
The system MUST support aggregation sources that write one snapshot per day containing the ordered items for that day; for Hacker News it MUST also capture up to the top 20 comments per item.

#### Scenario: Daily HN snapshot
- **WHEN** ingest runs for Hacker News on a given date
- **THEN** a snapshot is stored for that date with items in the source order and up to 20 comments per item

### Requirement: Blog Update Detection
The system MUST support blog sources that check for new posts and only store newly discovered items.

#### Scenario: No new posts
- **WHEN** a blog source has no new posts on a run
- **THEN** no new content files are created for that source

### Requirement: Query Interfaces
The system SHALL provide CLI and Python API queries by source (newest-first), keyword/title match, and archive date or date range.

#### Scenario: Query by archive date range
- **WHEN** a user queries a date range
- **THEN** results include only items archived within that range

### Requirement: Crawl Entrypoints
The system SHALL expose only two crawl entrypoints: ingest all sources and ingest a specific source via a `--source` parameter.

#### Scenario: Ingest a single source
- **WHEN** a user runs ingest with `--source <id>`
- **THEN** only that source is fetched

### Requirement: Additional Newsletter Sources
The system SHALL add new article-harvest sources for the requested newsletters and blogs.

#### Scenario: Ingest new source
- **WHEN** a user runs ingest for a new source
- **THEN** it fetches and stores items using the source's recommended access method
