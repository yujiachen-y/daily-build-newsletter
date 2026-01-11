from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser

from .importer import Importer
from .ingest import Ingestor
from .store import Store


def _load_json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


_ITEM_SUBCOMMANDS = {"show", "content", "comments"}
_GLOBAL_OPTION_TAKES_VALUE = {"--data-root"}


def _find_command_index(argv: list[str]) -> int | None:
    skip_next = False
    for index, token in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if token in _GLOBAL_OPTION_TAKES_VALUE:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        return index
    return None


def _inject_item_default(argv: list[str]) -> list[str]:
    command_index = _find_command_index(argv)
    if command_index is None:
        return argv
    if argv[command_index] != "item":
        return argv
    if command_index + 1 >= len(argv):
        return argv
    next_token = argv[command_index + 1]
    if next_token in _ITEM_SUBCOMMANDS or next_token.startswith("-"):
        return argv
    return argv[: command_index + 1] + ["show"] + argv[command_index + 1 :]


def _parse_datetime(value: str) -> datetime:
    parsed = date_parser.parse(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_relative(value: str) -> datetime | None:
    match = re.fullmatch(
        r"\s*(\d+)\s+(hours?|days?|weeks?)\s+ago\s*",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    quantity = int(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("hour"):
        delta = timedelta(hours=quantity)
    elif unit.startswith("week"):
        delta = timedelta(weeks=quantity)
    else:
        delta = timedelta(days=quantity)
    return datetime.now(timezone.utc) - delta


def _parse_since(value: str) -> datetime:
    relative = _parse_relative(value)
    if relative is not None:
        return relative
    return _parse_datetime(value)


def _filter_rows_by_after(rows: list[Any], after_dt: datetime | None) -> list[Any]:
    if after_dt is None:
        return rows
    filtered = []
    for row in rows:
        published_at = row["published_at"]
        if not published_at:
            continue
        try:
            published_dt = _parse_datetime(str(published_at))
        except (ValueError, TypeError):
            continue
        if published_dt >= after_dt:
            filtered.append(row)
    return filtered


def _render_items_json(
    store: Store,
    rows: list[Any],
    sources: dict[int, str],
    verbose: bool,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        record = dict(row)
        record["source_slug"] = sources.get(int(row["source_id"]), "unknown")
        if verbose:
            record["snippet"] = _get_snippet(store, int(row["id"]))
        output.append(record)
    return output


def _emit_json(payload: list[dict[str, Any]]) -> None:
    output: Any = payload[0] if len(payload) == 1 else payload
    print(json.dumps(output))


def _get_snippet(store: Store, item_id: int, length: int = 200) -> str | None:
    try:
        markdown, _ = store.read_content(item_id, None)
    except ValueError:
        return None
    snippet = " ".join(_strip_front_matter(markdown).split())
    return snippet[:length] if snippet else None


def _strip_front_matter(markdown: str) -> str:
    if not markdown.startswith("---"):
        return markdown
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return markdown
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :])
    return markdown


def _print_item_show(store: Store, item_id: int) -> None:
    item = store.get_item(item_id)
    if item is None:
        print(f"item not found id={item_id}")
        return
    print(dict(item))
    versions = store.get_item_versions(item_id)
    print(f"versions: {len(versions)}")
    for version in versions:
        print(f"- version_id={version['id']} extracted_at={version['extracted_at']}")


def _item_show_json(store: Store, item_id: int) -> dict[str, Any]:
    item = store.get_item(item_id)
    if item is None:
        return {"item_id": item_id, "error": "item not found"}
    versions = store.get_item_versions(item_id)
    return {"item": dict(item), "versions": [dict(row) for row in versions]}


def _item_content_json(store: Store, item_id: int, version_id: int | None) -> dict[str, Any]:
    try:
        markdown, row = store.read_content(item_id, version_id)
    except ValueError as exc:
        return {"item_id": item_id, "error": str(exc)}
    payload = {
        "item_id": item_id,
        "version_id": int(row["id"]),
        "content": markdown,
    }
    if row["title_snapshot"]:
        payload["title"] = row["title_snapshot"]
    return payload


def _item_comments_json(store: Store, item_id: int, version_id: int | None) -> dict[str, Any]:
    try:
        markdown, row = store.read_sidecar(item_id, version_id, "comments.md")
    except ValueError as exc:
        return {"item_id": item_id, "error": str(exc)}
    return {
        "item_id": item_id,
        "version_id": int(row["id"]),
        "comments": markdown,
    }


def cmd_ingest(store: Store, args: argparse.Namespace) -> None:
    ingestor = Ingestor(store)
    run_id = ingestor.run(source_slugs=args.source, run_type=args.type)
    print(f"ingest complete run_id={run_id}")


def cmd_updates(store: Store, args: argparse.Namespace) -> None:
    run_id = args.run_id or store.get_latest_run_id()
    if run_id is None:
        print("no runs found")
        return
    updates = store.get_updates_for_run(run_id)
    print(f"updates for run {run_id}: {len(updates)}")
    for row in updates:
        print(f"- item_id={row['id']} version_id={row['version_id']} title={row['title']}")


def cmd_item(store: Store, args: argparse.Namespace) -> None:
    item_ids = args.item_id
    if args.subcommand == "show":
        if args.json:
            payload = [_item_show_json(store, item_id) for item_id in item_ids]
            _emit_json(payload)
            return
        multiple = len(item_ids) > 1
        for item_id in item_ids:
            if multiple:
                print(f"item_id={item_id}")
            _print_item_show(store, item_id)
    elif args.subcommand == "content":
        if args.json:
            payload = [
                _item_content_json(store, item_id, args.version_id) for item_id in item_ids
            ]
            _emit_json(payload)
            return
        multiple = len(item_ids) > 1
        for item_id in item_ids:
            if multiple:
                print(f"item_id={item_id}")
            try:
                markdown, _ = store.read_content(item_id, args.version_id)
            except ValueError as exc:
                print(str(exc))
                continue
            print(markdown)
    elif args.subcommand == "comments":
        if args.json:
            payload = [
                _item_comments_json(store, item_id, args.version_id) for item_id in item_ids
            ]
            _emit_json(payload)
            return
        multiple = len(item_ids) > 1
        for item_id in item_ids:
            if multiple:
                print(f"item_id={item_id}")
            try:
                markdown, _ = store.read_sidecar(item_id, args.version_id, "comments.md")
            except ValueError as exc:
                print(str(exc))
                continue
            print(markdown)


def cmd_items(store: Store, args: argparse.Namespace) -> None:
    source_id = None
    source_slug = None
    if args.source:
        source = store.get_source_by_slug(args.source)
        if source is None:
            error = {"error": "source not found"} if args.json else "source not found"
            print(json.dumps(error) if args.json else error)
            return
        source_id = int(source["id"])
        source_slug = source["slug"]

    sources = {int(row["id"]): row["slug"] for row in store.list_sources()}
    rows = store.list_items(source_id=source_id, query=args.query)
    after_dt = None
    if args.since:
        try:
            after_dt = _parse_since(args.since)
        except (ValueError, TypeError):
            error = {"error": "invalid --since value"} if args.json else "invalid --since value"
            print(json.dumps(error) if args.json else error)
            return
    if args.after:
        try:
            after_dt = _parse_datetime(args.after)
        except (ValueError, TypeError):
            error = {"error": "invalid --after value"} if args.json else "invalid --after value"
            print(json.dumps(error) if args.json else error)
            return
    rows = _filter_rows_by_after(rows, after_dt)
    if args.json:
        payload = _render_items_json(store, rows, sources, args.verbose)
        print(json.dumps(payload))
        return
    for row in rows:
        slug = source_slug or sources.get(int(row["source_id"]), "unknown")
        title = row["title"] or ""
        canonical = row["canonical_url"] or ""
        author = row["author"] or ""
        published = row["published_at"] or ""
        line = f"- item_id={row['id']} source={slug} title={title} url={canonical}"
        if args.verbose:
            line = (
                f"{line} author={author} published_at={published}"
                if author or published
                else line
            )
        print(line)
        if args.verbose:
            snippet = _get_snippet(store, int(row["id"]))
            if snippet:
                print(f"  snippet={snippet}")


def cmd_source(store: Store, args: argparse.Namespace) -> None:
    if args.subcommand == "list":
        type_filter = args.type or "all"
        sources = store.list_sources()
        if type_filter in ("all", "content"):
            for row in sources:
                policy = json.loads(row["policy_json"] or "{}")
                mode = policy.get("mode", "html")
                print(
                    f"- {row['slug']} enabled={bool(row['enabled'])} mode={mode} type=content"
                )
        if type_filter in ("all", "index"):
            from .index_ingest import list_index_sources

            for source in list_index_sources():
                print(f"- {source.slug} mode=index type=index (builtin) name={source.name}")
    elif args.subcommand == "add":
        policy = _load_json_arg(args.policy)
        config = _load_json_arg(args.config)
        source_id = store.upsert_source(
            args.slug,
            args.name,
            args.homepage_url,
            True,
            policy,
            config,
        )
        print(f"source added id={source_id}")
    elif args.subcommand == "enable":
        store.update_source_enabled(args.slug, True)
        print("enabled")
    elif args.subcommand == "disable":
        store.update_source_enabled(args.slug, False)
        print("disabled")
    elif args.subcommand == "show":
        row = store.get_source_by_slug(args.slug)
        if row is None:
            print("source not found")
            return
        print(dict(row))


def cmd_runs(store: Store, args: argparse.Namespace) -> None:
    runs = store.list_runs()
    for run in runs:
        summary = (
            f"- id={run['id']} status={run['status']} total={run['total_items']} "
            f"updated={run['updated_items']} errors={run['errors_count']}"
        )
        print(summary)


def cmd_import(store: Store, args: argparse.Namespace) -> None:
    importer = Importer(store)
    run_id = importer.run(source_slug=args.source)
    print(f"import complete run_id={run_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="article-ingest")
    parser.add_argument("--data-root", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("--source", action="append")
    ingest_parser.add_argument("--type", choices=["content", "index", "all"], default="all")
    ingest_parser.set_defaults(func=cmd_ingest)

    updates_parser = subparsers.add_parser("updates")
    updates_parser.add_argument("--run-id", type=int)
    updates_parser.set_defaults(func=cmd_updates)

    item_parser = subparsers.add_parser("item")
    item_sub = item_parser.add_subparsers(dest="subcommand", required=True)
    item_show = item_sub.add_parser("show")
    item_show.add_argument("item_id", type=int, nargs="+")
    item_show.add_argument("--json", action="store_true")
    item_show.set_defaults(func=cmd_item)
    item_content = item_sub.add_parser("content")
    item_content.add_argument("item_id", type=int, nargs="+")
    item_content.add_argument("--version-id", type=int)
    item_content.add_argument("--json", action="store_true")
    item_content.set_defaults(func=cmd_item)
    item_comments = item_sub.add_parser("comments")
    item_comments.add_argument("item_id", type=int, nargs="+")
    item_comments.add_argument("--version-id", type=int)
    item_comments.add_argument("--json", action="store_true")
    item_comments.set_defaults(func=cmd_item)

    items_parser = subparsers.add_parser("items")
    items_parser.add_argument("--source")
    items_parser.add_argument("--query")
    items_date_group = items_parser.add_mutually_exclusive_group()
    items_date_group.add_argument("--since")
    items_date_group.add_argument("--after")
    items_parser.add_argument("--verbose", action="store_true")
    items_parser.add_argument("--json", action="store_true")
    items_parser.set_defaults(func=cmd_items)

    source_parser = subparsers.add_parser("source")
    source_sub = source_parser.add_subparsers(dest="subcommand", required=True)
    source_list = source_sub.add_parser("list")
    source_list.add_argument("--type", choices=["content", "index", "all"], default="all")
    source_list.set_defaults(func=cmd_source)
    source_add = source_sub.add_parser("add")
    source_add.add_argument("slug")
    source_add.add_argument("name")
    source_add.add_argument("homepage_url")
    source_add.add_argument("--policy")
    source_add.add_argument("--config")
    source_add.set_defaults(func=cmd_source)
    source_show = source_sub.add_parser("show")
    source_show.add_argument("slug")
    source_show.set_defaults(func=cmd_source)
    source_enable = source_sub.add_parser("enable")
    source_enable.add_argument("slug")
    source_enable.set_defaults(func=cmd_source)
    source_disable = source_sub.add_parser("disable")
    source_disable.add_argument("slug")
    source_disable.set_defaults(func=cmd_source)

    runs_parser = subparsers.add_parser("runs")
    runs_parser.set_defaults(func=cmd_runs)

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--source")
    import_parser.set_defaults(func=cmd_import)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args(_inject_item_default(sys.argv[1:]))
    store = Store(root=args.data_root)
    args.func(store, args)


if __name__ == "__main__":
    main()
