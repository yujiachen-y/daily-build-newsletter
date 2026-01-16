# Change: Add worktree workflow guidance

## Why
We want a documented and repeatable way to use Git worktrees with this repo while keeping local data and environments consistent.

## What Changes
- Document the preferred worktree workflow (per-worktree venv, shared cache).
- Add a one-way sync script for `modules/article-harvest/data/` from main to other worktrees.

## Impact
- Affected specs: worktree-workflow
- Affected code: AGENTS.md, scripts/worktree-sync-data.sh, modules/article-harvest/scripts/worktree-sync-data.sh
