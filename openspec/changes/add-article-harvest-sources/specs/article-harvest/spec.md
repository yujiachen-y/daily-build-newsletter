## ADDED Requirements
### Requirement: Additional Newsletter Sources
The system SHALL add new article-harvest sources for the requested newsletters and blogs.

#### Scenario: Ingest new source
- **WHEN** a user runs ingest for a new source
- **THEN** it fetches and stores items using the source's recommended access method

### Requirement: Source Access Method
Each new source SHALL use exactly one retrieval method chosen during implementation (RSS/HTML/agent).

#### Scenario: Single method
- **WHEN** a source is configured
- **THEN** it does not attempt alternative retrieval methods at runtime
