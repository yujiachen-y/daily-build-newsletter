## Context
We want a repeatable worktree workflow that isolates development while keeping dependency installs fast and local data consistent.

## Decisions
- Use Option B: each worktree has its own virtual environment.
- Share dependency caches via pip's default cache.
- Sync local data only from the main worktree to other worktrees.
- Only sync `modules/article-harvest/data/` for now.

## Risks
- Manual sync is required to keep worktree data up to date.
- One-way sync avoids accidental overwrites in main.
