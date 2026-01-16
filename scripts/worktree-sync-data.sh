#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 0 ]; then
  echo "Usage: $0" >&2
  exit 1
fi

ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$ROOT" ]; then
  echo "Not inside a git worktree." >&2
  exit 1
fi

if [ -d "$ROOT/.git" ]; then
  echo "Refusing to run from main worktree. Run from a linked worktree instead." >&2
  exit 1
fi

MAIN=""
current_worktree=""
while IFS= read -r line; do
  case "$line" in
    worktree\ *)
      current_worktree=${line#worktree }
      if [ -d "$current_worktree/.git" ]; then
        MAIN=$current_worktree
        break
      fi
      ;;
  esac
done < <(git worktree list --porcelain)

if [ -z "$MAIN" ]; then
  echo "Unable to locate main worktree." >&2
  exit 1
fi

MODULE_SCRIPT="$ROOT/modules/article-harvest/scripts/worktree-sync-data.sh"
if [ ! -x "$MODULE_SCRIPT" ]; then
  echo "Missing module sync script: $MODULE_SCRIPT" >&2
  exit 1
fi

"$MODULE_SCRIPT" "$MAIN" "$ROOT"
