#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <source-worktree> <dest-worktree>" >&2
  exit 1
fi

SRC=$(cd "$1" && pwd)
DST=$(cd "$2" && pwd)

if [ ! -d "$SRC/.git" ]; then
  echo "Source must be the main worktree (missing .git directory): $SRC" >&2
  exit 1
fi

if [ -d "$DST/.git" ]; then
  echo "Refusing to sync into main worktree: $DST" >&2
  exit 1
fi

sync_dir() {
  local src_dir="$1"
  local dst_dir="$2"
  if [ ! -d "$src_dir" ]; then
    echo "Skip missing: $src_dir" >&2
    return
  fi
  mkdir -p "$dst_dir"
  rsync -a --delete "$src_dir"/ "$dst_dir"/
}

sync_dir "$SRC/modules/article-harvest/data" "$DST/modules/article-harvest/data"

MODULE_DIR="$DST/modules/article-harvest"
if [ ! -d "$MODULE_DIR" ]; then
  echo "Missing module directory: $MODULE_DIR" >&2
  exit 1
fi

if [ ! -d "$MODULE_DIR/.venv" ]; then
  python -m venv "$MODULE_DIR/.venv"
fi

# shellcheck disable=SC1091
source "$MODULE_DIR/.venv/bin/activate"
python -m pip install -e "$MODULE_DIR"

echo "Synced article-harvest data from $SRC to $DST and installed deps"
