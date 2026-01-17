from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class VerifyIssue:
    source_id: str
    kind: str
    issue_type: str
    item_id: str | None = None
    path: str | None = None
    detail: str | None = None
    snippet: str | None = None


def verify_data_root(
    data_root: Path,
    *,
    source_ids: set[str] | None = None,
    min_content_chars: int = 400,
    max_issues: int = 200,
    include_snippets: bool = False,
) -> dict:
    sources_root = data_root / "sources"
    collector = _IssueCollector(max_issues=max_issues)

    if not sources_root.exists():
        collector.add(
            VerifyIssue(
                source_id="(none)",
                kind="unknown",
                issue_type="sources_root_missing",
                path=str(sources_root),
            )
        )
        return collector.report(data_root)

    for source_dir in sorted([path for path in sources_root.iterdir() if path.is_dir()]):
        source_id = source_dir.name
        if source_ids is not None and source_id not in source_ids:
            continue

        manifest_path = source_dir / "manifest.jsonl"
        snapshots_dir = source_dir / "snapshots"
        if manifest_path.exists():
            _verify_blog_source(
                data_root,
                source_id,
                manifest_path,
                source_dir / "items",
                collector=collector,
                min_content_chars=min_content_chars,
                include_snippets=include_snippets,
            )
            continue

        if snapshots_dir.exists() and any(snapshots_dir.glob("*.json")):
            _verify_aggregation_source(
                source_id,
                snapshots_dir,
                collector=collector,
            )
            continue

        collector.add(
            VerifyIssue(
                source_id=source_id,
                kind="unknown",
                issue_type="source_unrecognized_layout",
                path=str(source_dir),
            )
        )

    return collector.report(data_root)


class _IssueCollector:
    def __init__(self, *, max_issues: int) -> None:
        self._max_issues = max_issues
        self._issues: list[VerifyIssue] = []
        self._counts_by_type: Counter[str] = Counter()
        self._counts_by_source: dict[str, Counter[str]] = defaultdict(Counter)
        self._items_by_source: Counter[str] = Counter()
        self._kinds_by_source: dict[str, str] = {}

    def note_item(self, source_id: str, kind: str) -> None:
        self._items_by_source[source_id] += 1
        self._kinds_by_source[source_id] = kind

    def add(self, issue: VerifyIssue) -> None:
        self._counts_by_type[issue.issue_type] += 1
        self._counts_by_source[issue.source_id][issue.issue_type] += 1
        self._kinds_by_source[issue.source_id] = issue.kind
        if len(self._issues) < self._max_issues:
            self._issues.append(issue)

    def report(self, data_root: Path) -> dict:
        sources = []
        for source_id in sorted(set(self._items_by_source) | set(self._counts_by_source)):
            kind = self._kinds_by_source.get(source_id, "unknown")
            sources.append(
                {
                    "source_id": source_id,
                    "kind": kind,
                    "items_checked": int(self._items_by_source[source_id]),
                    "issues": dict(self._counts_by_source[source_id]),
                }
            )
        return {
            "data_root": str(data_root),
            "sources": sources,
            "totals": {
                "items_checked": int(sum(self._items_by_source.values())),
                "issues_total": int(sum(self._counts_by_type.values())),
                "issues_by_type": dict(self._counts_by_type),
                "issues_truncated": int(sum(self._counts_by_type.values())) > len(self._issues),
            },
            "issues": [asdict(issue) for issue in self._issues],
        }


def _verify_blog_source(
    data_root: Path,
    source_id: str,
    manifest_path: Path,
    items_dir: Path,
    *,
    collector: _IssueCollector,
    min_content_chars: int,
    include_snippets: bool,
) -> None:
    kind = "blog"
    try:
        lines = [
            line
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except UnicodeDecodeError:
        collector.add(
            VerifyIssue(
                source_id=source_id,
                kind=kind,
                issue_type="manifest_bad_utf8",
                path=str(manifest_path),
            )
        )
        return

    if not lines:
        collector.add(
            VerifyIssue(
                source_id=source_id,
                kind=kind,
                issue_type="manifest_empty",
                path=str(manifest_path),
            )
        )
        return

    for idx, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="manifest_bad_json",
                    path=str(manifest_path),
                    detail=f"line={idx}",
                )
            )
            continue

        item_id = record.get("id")
        collector.note_item(source_id, kind)
        if not isinstance(item_id, str) or not item_id:
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="manifest_missing_id",
                    path=str(manifest_path),
                    detail=f"line={idx}",
                )
            )
            continue

        url = record.get("url")
        if not isinstance(url, str) or not url:
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="manifest_missing_url",
                    item_id=item_id,
                    path=str(manifest_path),
                    detail=f"line={idx}",
                )
            )

        content_rel = record.get("content_path")
        expected_content_path = items_dir / item_id / "content.md"
        content_path = _content_path(data_root, content_rel, expected_content_path)
        if not content_path.exists():
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="content_missing",
                    item_id=item_id,
                    path=str(content_path),
                )
            )
            continue

        meta_path = items_dir / item_id / "meta.json"
        if not meta_path.exists():
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="meta_missing",
                    item_id=item_id,
                    path=str(meta_path),
                )
            )
        else:
            _verify_meta_consistency(
                source_id,
                item_id,
                meta_path,
                record,
                collector=collector,
            )

        try:
            content = content_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="content_bad_utf8",
                    item_id=item_id,
                    path=str(content_path),
                )
            )
            continue

        normalized = content.strip()
        if not normalized:
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="content_empty",
                    item_id=item_id,
                    path=str(content_path),
                )
            )
            continue

        content_len = len(normalized)
        if content_len < min_content_chars:
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="content_too_short",
                    item_id=item_id,
                    path=str(content_path),
                    detail=f"chars={content_len} (<{min_content_chars})",
                    snippet=_maybe_snippet(normalized, include_snippets),
                )
            )

        if _looks_like_placeholder(normalized):
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="content_placeholder",
                    item_id=item_id,
                    path=str(content_path),
                    snippet=_maybe_snippet(normalized, include_snippets),
                )
            )

        if "\x00" in normalized:
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="content_has_nul",
                    item_id=item_id,
                    path=str(content_path),
                )
            )

        if "�" in normalized:
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="content_has_replacement_char",
                    item_id=item_id,
                    path=str(content_path),
                )
            )


def _verify_meta_consistency(
    source_id: str,
    item_id: str,
    meta_path: Path,
    manifest_record: dict,
    *,
    collector: _IssueCollector,
) -> None:
    kind = "blog"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        collector.add(
            VerifyIssue(
                source_id=source_id,
                kind=kind,
                issue_type="meta_bad_json",
                item_id=item_id,
                path=str(meta_path),
            )
        )
        return

    if meta.get("id") != item_id:
        collector.add(
            VerifyIssue(
                source_id=source_id,
                kind=kind,
                issue_type="meta_id_mismatch",
                item_id=item_id,
                path=str(meta_path),
                detail=f"meta.id={meta.get('id')!r}",
            )
        )

    manifest_url = manifest_record.get("url")
    if isinstance(manifest_url, str) and meta.get("url") != manifest_url:
        collector.add(
            VerifyIssue(
                source_id=source_id,
                kind=kind,
                issue_type="meta_url_mismatch",
                item_id=item_id,
                path=str(meta_path),
            )
        )

    manifest_content_path = manifest_record.get("content_path")
    if isinstance(manifest_content_path, str) and meta.get("content_path") != manifest_content_path:
        collector.add(
            VerifyIssue(
                source_id=source_id,
                kind=kind,
                issue_type="meta_content_path_mismatch",
                item_id=item_id,
                path=str(meta_path),
            )
        )


def _verify_aggregation_source(
    source_id: str,
    snapshots_dir: Path,
    *,
    collector: _IssueCollector,
) -> None:
    kind = "aggregation"
    for snapshot_path in sorted(snapshots_dir.glob("*.json")):
        collector.note_item(source_id, kind)
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="snapshot_bad_json",
                    path=str(snapshot_path),
                )
            )
            continue

        items = payload.get("items")
        if not isinstance(items, list):
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="snapshot_items_not_list",
                    path=str(snapshot_path),
                )
            )
            continue

        if not items:
            collector.add(
                VerifyIssue(
                    source_id=source_id,
                    kind=kind,
                    issue_type="snapshot_items_empty",
                    path=str(snapshot_path),
                )
            )
            continue

        for item in items[:50]:
            if not isinstance(item, dict):
                collector.add(
                    VerifyIssue(
                        source_id=source_id,
                        kind=kind,
                        issue_type="snapshot_item_not_object",
                        path=str(snapshot_path),
                    )
                )
                continue
            url = item.get("url")
            title = item.get("title")
            if not isinstance(url, str) or not url:
                collector.add(
                    VerifyIssue(
                        source_id=source_id,
                        kind=kind,
                        issue_type="snapshot_item_missing_url",
                        path=str(snapshot_path),
                    )
                )
            if not isinstance(title, str) or not title:
                collector.add(
                    VerifyIssue(
                        source_id=source_id,
                        kind=kind,
                        issue_type="snapshot_item_missing_title",
                        path=str(snapshot_path),
                    )
                )


def _looks_like_placeholder(content: str) -> bool:
    preview = content[:800]
    if "|  |" in preview:
        return True
    if preview.lstrip().startswith("[Signup]"):
        return True
    return any(line.strip() == "|" for line in preview.splitlines())


def _maybe_snippet(content: str, include_snippets: bool) -> str | None:
    if not include_snippets:
        return None
    snippet = content[:200].replace("\n", " ")
    return snippet + ("…" if len(content) > 200 else "")


def _content_path(data_root: Path, content_rel: object, fallback: Path) -> Path:
    if isinstance(content_rel, str) and content_rel:
        return data_root / content_rel
    return fallback
