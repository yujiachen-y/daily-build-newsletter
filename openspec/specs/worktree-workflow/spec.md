# worktree-workflow Specification

## Purpose
Document and support a Git worktree-based workflow for parallel development, including a one-way sync of `modules/article-harvest/data/` from the main worktree into linked worktrees.

## Requirements
### Requirement: Worktree Workflow Documentation
The system SHALL document a worktree workflow that uses per-worktree virtual environments and shared dependency caches.

#### Scenario: Set up worktree
- **WHEN** a user creates a worktree
- **THEN** the documentation specifies how to create a new virtual environment in that worktree

### Requirement: One-Way Data Sync
The system SHALL provide a script to sync untracked data from the main worktree to other worktrees, limited to article-harvest data.

#### Scenario: Sync data from main
- **WHEN** the sync script runs
- **THEN** it copies `modules/article-harvest/data/` from the main worktree into the destination worktree and refuses to write into the main worktree
