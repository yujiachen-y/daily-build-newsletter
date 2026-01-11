## ADDED Requirements
### Requirement: Source Registry and Policy
The system SHALL maintain a registry of sources with per-source policies (mode, rate limits, headless allowed) and enforce these policies during ingest.

#### Scenario: Enforced policy during ingest
- **WHEN** an ingest run processes a source with configured rate limits
- **THEN** requests are scheduled so the policy limits are not exceeded

### Requirement: Run Tracking and Failure Logs
The system SHALL record each ingest or import run with status and counters, and SHALL record failures with source_id, url, stage, and timestamps to allow locating the failed page.

#### Scenario: Detail fetch fails
- **WHEN** a detail fetch returns an error status
- **THEN** a failure record is written with the failing url and stage

### Requirement: Item Discovery and De-duplication
The system SHALL upsert items by (source_id, item_key) and track first_seen_at, last_seen_at, and published_at.

#### Scenario: Existing item discovered again
- **WHEN** a source lists an item with an existing (source_id, item_key)
- **THEN** the item is updated with a new last_seen_at without creating a duplicate

### Requirement: Markdown Version Storage
The system SHALL store extracted Markdown content for each item version under a stable filesystem path and create a new version when content_hash changes.
The system SHALL NOT write content files or create versions when detail download or extraction fails.

#### Scenario: Content changes
- **WHEN** a newly extracted Markdown hash differs from the latest version
- **THEN** a new item version is created and stored

#### Scenario: Extraction fails
- **WHEN** detail download or extraction fails
- **THEN** no content file is written and a failure record is created

### Requirement: Markdown Front Matter
The system SHALL store each Markdown content file with a YAML front matter block that includes item_id, source_id, canonical_url, title, published_at, version_id, content_hash, extracted_at, and run_id.
Missing values SHALL be encoded as null.

#### Scenario: Stored content includes front matter
- **WHEN** a new item version is stored
- **THEN** content.md begins with YAML front matter including the required fields

#### Scenario: Import adds front matter
- **WHEN** a Markdown file without front matter is imported
- **THEN** the stored content includes generated front matter

### Requirement: Asset Colocation
The system SHALL store downloadable assets next to the Markdown content and rewrite Markdown links to relative asset paths when downloads succeed.

#### Scenario: Image downloaded
- **WHEN** a referenced image is successfully downloaded
- **THEN** the Markdown link is rewritten to the local asset path

### Requirement: Update Reporting
The system SHALL report items with new versions created since the previous run.

#### Scenario: New version in the latest run
- **WHEN** a run creates a new item version
- **THEN** that item appears in the updates report for the latest run

### Requirement: Manual Import
The system SHALL import Markdown or HTML files with meta.json from a local inbox and process them as item versions.

#### Scenario: Markdown inbox import
- **WHEN** a Markdown file with valid meta.json is placed in the inbox
- **THEN** the system imports it as a new item version

### Requirement: Content Retrieval API
The system SHALL provide read_content(item_id, version_id=None) that returns the latest version when version_id is omitted and returns the specified version when it belongs to the item.

#### Scenario: Read latest content
- **WHEN** read_content is called with only item_id
- **THEN** the latest version content is returned
