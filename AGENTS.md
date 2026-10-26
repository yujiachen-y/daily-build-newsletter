# Repository Guidelines

## Project Structure & Module Organization

- `modules/`: standalone components. Today this is primarily `modules/article-harvest/` (Python CLI + library).
- `modules/article-harvest/src/article_harvest/`: implementation code.
- `modules/article-harvest/tests/`: pytest tests (`test_*.py`).
- `modules/article-harvest/data/`: local run artifacts (ignored by git).
- `editorial_workspace/`: newsletter drafts, typically named like `YYYY-MM-DD-daily-build.md`.
- `docs/` and `scripts/`: general documentation and repo-level utilities (when present).

## Build, Test, and Development Commands

Most development happens inside a module directory (example: `modules/article-harvest/`):

- `uv tool install --force --managed-python --python 3.10 -c constraints.txt -e .`: install (or reinstall) the `article-harvest` CLI as a uv tool on Python 3.10, with dependency versions pinned by `constraints.txt`.
- `uv venv --managed-python --python 3.10 --clear && source .venv/bin/activate`: create/activate a local virtualenv for dev tooling.
- `uv pip install -c constraints.txt -e ".[dev]"`: install the module in editable mode plus dev tooling into that virtualenv.
- `article-harvest ingest`: fetch sources and persist snapshots/items under `data/`.
- `pytest`: run unit tests.
- `ruff check .`: run lint + import sorting checks.
- `ruff format .`: apply formatting (keep diffs small and intentional).

## Coding Style & Naming Conventions

- Python `>=3.10`, 4-space indentation, and 100-char lines (enforced via Ruff config).
- Prefer clear, testable helpers over dense one-liners; keep module boundaries intact (avoid cross-module coupling).
- Editorial files: `editorial_workspace/YYYY-MM-DD-*.md`.

## Testing Guidelines

- Add/modify tests close to the code: `modules/<module>/tests/test_*.py`.
- If you change behavior, add a focused unit test and run: `pytest -q` (and optionally `pytest --cov=article_harvest`).

## Commit & Pull Request Guidelines

- Follow the existing history style: short, imperative subjects; common prefixes include `feat:`, `docs:`, `chore:`, `refactor:`.
- PRs should include: what/why, commands run, and any relevant output paths (e.g., `modules/article-harvest/data/runs/...`).

## (Optional) Git Hooks

- To enable repo hooks: `git config core.hooksPath .githooks` (review/update hook scripts before relying on them).

