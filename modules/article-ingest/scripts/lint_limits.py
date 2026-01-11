#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

MAX_FUNCTION_LINES = 240
MAX_FILE_LINES = 500


def iter_python_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for folder in [root / "src" / "article_ingest", root / "tests"]:
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            paths.append(path)
    return paths


def check_file_length(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) > MAX_FILE_LINES:
        return [f"{path}: file too long ({len(lines)} > {MAX_FILE_LINES})"]
    return []


def check_function_length(path: Path) -> list[str]:
    errors: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.end_lineno or not node.lineno:
                continue
            length = node.end_lineno - node.lineno + 1
            if length > MAX_FUNCTION_LINES:
                errors.append(
                    f"{path}:{node.lineno} {node.name} too long ({length} > {MAX_FUNCTION_LINES})"
                )
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    for path in iter_python_files(root):
        failures.extend(check_file_length(path))
        failures.extend(check_function_length(path))
    if failures:
        for failure in failures:
            print(failure)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
