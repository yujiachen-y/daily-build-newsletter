from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

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


def cmd_ingest(store: Store, args: argparse.Namespace) -> None:
    ingestor = Ingestor(store)
    run_id = ingestor.run(source_slugs=args.source)
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
    if args.subcommand == "show":
        item = store.get_item(args.item_id)
        if item is None:
            print("item not found")
            return
        print(dict(item))
        versions = store.get_item_versions(args.item_id)
        print(f"versions: {len(versions)}")
        for version in versions:
            print(f"- version_id={version['id']} extracted_at={version['extracted_at']}")
    elif args.subcommand == "content":
        try:
            markdown, _ = store.read_content(args.item_id, args.version_id)
        except ValueError as exc:
            print(str(exc))
            return
        print(markdown)
    elif args.subcommand == "comments":
        try:
            markdown, _ = store.read_sidecar(args.item_id, args.version_id, "comments.md")
        except ValueError as exc:
            print(str(exc))
            return
        print(markdown)


def cmd_items(store: Store, args: argparse.Namespace) -> None:
    source_id = None
    source_slug = None
    if args.source:
        source = store.get_source_by_slug(args.source)
        if source is None:
            print("source not found")
            return
        source_id = int(source["id"])
        source_slug = source["slug"]

    sources = {int(row["id"]): row["slug"] for row in store.list_sources()}
    rows = store.list_items(source_id=source_id)
    for row in rows:
        slug = source_slug or sources.get(int(row["source_id"]), "unknown")
        title = row["title"] or ""
        canonical = row["canonical_url"] or ""
        print(f"- item_id={row['id']} source={slug} title={title} url={canonical}")


def cmd_source(store: Store, args: argparse.Namespace) -> None:
    if args.subcommand == "list":
        sources = store.list_sources()
        for row in sources:
            policy = json.loads(row["policy_json"] or "{}")
            mode = policy.get("mode", "html")
            print(f"- {row['slug']} enabled={bool(row['enabled'])} mode={mode}")
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
    ingest_parser.set_defaults(func=cmd_ingest)

    updates_parser = subparsers.add_parser("updates")
    updates_parser.add_argument("--run-id", type=int)
    updates_parser.set_defaults(func=cmd_updates)

    item_parser = subparsers.add_parser("item")
    item_sub = item_parser.add_subparsers(dest="subcommand", required=True)
    item_show = item_sub.add_parser("show")
    item_show.add_argument("item_id", type=int)
    item_show.set_defaults(func=cmd_item)
    item_content = item_sub.add_parser("content")
    item_content.add_argument("item_id", type=int)
    item_content.add_argument("--version-id", type=int)
    item_content.set_defaults(func=cmd_item)
    item_comments = item_sub.add_parser("comments")
    item_comments.add_argument("item_id", type=int)
    item_comments.add_argument("--version-id", type=int)
    item_comments.set_defaults(func=cmd_item)

    items_parser = subparsers.add_parser("items")
    items_parser.add_argument("--source")
    items_parser.set_defaults(func=cmd_items)

    source_parser = subparsers.add_parser("source")
    source_sub = source_parser.add_subparsers(dest="subcommand", required=True)
    source_list = source_sub.add_parser("list")
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
    args = parser.parse_args()
    store = Store(root=args.data_root)
    args.func(store, args)


if __name__ == "__main__":
    main()
