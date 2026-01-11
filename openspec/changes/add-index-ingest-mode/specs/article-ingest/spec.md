## ADDED Requirements

### Requirement: Index Ingest Mode
The system SHALL support an index ingest path that processes a fixed allowlist of aggregation sources and generates daily Markdown summaries without storing item versions.

#### Scenario: Index daily summary
- **WHEN** an index source is ingested
- **THEN** the system writes a daily Markdown file under `data/daily/{source_slug}/YYYY-MM-DD.md`
- **AND** no item version is created for index sources

### Requirement: Type Filtering
The system SHALL allow operators to filter ingest runs and source listings by type (`content`, `index`, or `all`), with `all` as the default behavior.

#### Scenario: Type filtering in ingest
- **WHEN** an operator runs `ingest --type index`
- **THEN** only index allowlist sources are processed

#### Scenario: Type filtering in source list
- **WHEN** an operator runs `source list --type index`
- **THEN** only index allowlist sources are displayed

### Requirement: Fail Fast on Slug Overlap
The system SHALL fail the ingest run when a slug exists in both the index allowlist and the content source registry.

#### Scenario: Overlap detected
- **WHEN** an ingest run starts and a slug appears in both index and content sources
- **THEN** the run stops with an error describing the overlapping slug
