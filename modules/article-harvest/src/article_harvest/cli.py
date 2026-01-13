from __future__ import annotations

import argparse
import json
import pydoc
import sys

from .ingest import ingest_all, ingest_source
from .queries import query_by_archive_date, query_by_keyword, query_by_source
from .sources.registry import get_source, list_sources
from .sqlite_index import rebuild_sqlite_index
from .storage import Storage


def main() -> int:
    parser = argparse.ArgumentParser(prog="article-harvest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Run ingest")
    ingest_parser.add_argument("--source", help="Source id to ingest")

    sources_parser = subparsers.add_parser("sources", help="List sources")
    sources_parser.add_argument("--json", action="store_true", help="JSON output")

    read_parser = subparsers.add_parser("read", help="Read stored blog content")
    read_parser.add_argument("source_id")
    read_parser.add_argument("item_id")
    read_parser.add_argument("--pager", action="store_true", help="Display with pager")

    sqlite_parser = subparsers.add_parser("sqlite", help="Manage SQLite index")
    sqlite_subparsers = sqlite_parser.add_subparsers(dest="sqlite_command", required=True)
    sqlite_rebuild = sqlite_subparsers.add_parser(
        "rebuild",
        help="Rebuild SQLite index from stored files",
    )
    sqlite_rebuild.add_argument("--json", action="store_true", help="JSON output")

    query_parser = subparsers.add_parser("query", help="Query stored records")
    query_subparsers = query_parser.add_subparsers(dest="query_command", required=True)

    query_source = query_subparsers.add_parser("source", help="Query by source")
    query_source.add_argument("source_id")
    query_source.add_argument("--limit", type=int)
    query_source.add_argument("--json", action="store_true", help="JSON output")

    query_keyword = query_subparsers.add_parser("keyword", help="Query by keyword")
    query_keyword.add_argument("keyword")
    query_keyword.add_argument("--source")
    query_keyword.add_argument("--limit", type=int)
    query_keyword.add_argument("--json", action="store_true", help="JSON output")

    query_archive = query_subparsers.add_parser("archive", help="Query by archive date")
    query_archive.add_argument("--on")
    query_archive.add_argument("--from", dest="start")
    query_archive.add_argument("--to", dest="end")
    query_archive.add_argument("--source")
    query_archive.add_argument("--limit", type=int)
    query_archive.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    if args.command == "ingest":
        report = ingest_source(args.source) if args.source else ingest_all()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    storage = Storage()

    if args.command == "sources":
        sources = list_sources()
        if args.json:
            payload = [
                {
                    "id": source.id,
                    "name": source.name,
                    "kind": source.kind,
                    "method": source.method,
                    "enabled": source.enabled,
                }
                for source in sources
            ]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for source in sources:
                suffix = "" if source.enabled else " [disabled]"
                print(f"- {source.id} ({source.kind}, {source.method}){suffix}")
        return 0

    if args.command == "read":
        source = get_source(args.source_id)
        if source.kind != "blog":
            print("read is only supported for blog sources", file=sys.stderr)
            return 2
        content_path = storage.content_path(args.source_id, args.item_id)
        if not content_path.exists():
            print(f"content not found: {content_path}", file=sys.stderr)
            return 2
        content = content_path.read_text(encoding="utf-8")
        if args.pager:
            pydoc.pager(content)
        else:
            sys.stdout.write(content)
        return 0

    if args.command == "sqlite":
        report = rebuild_sqlite_index(storage, list_sources(include_disabled=False))
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"SQLite index rebuilt at {report['path']} with {report['records']} records")
        return 0

    if args.command == "query":
        if args.query_command == "source":
            source = get_source(args.source_id)
            records = query_by_source(storage, source, limit=args.limit)
            _print_records(storage, records, args.json)
            return 0
        if args.query_command == "keyword":
            records = query_by_keyword(
                storage,
                list_sources(),
                args.keyword,
                source_id=args.source,
                limit=args.limit,
            )
            _print_records(storage, records, args.json)
            return 0
        if args.query_command == "archive":
            records = query_by_archive_date(
                storage,
                list_sources(),
                on=args.on,
                start=args.start,
                end=args.end,
                source_id=args.source,
                limit=args.limit,
            )
            _print_records(storage, records, args.json)
            return 0

    return 1


def _print_records(storage: Storage, records, as_json: bool) -> None:
    if as_json:
        payload = []
        for record in records:
            data = record.to_dict()
            data["has_content"] = _has_content(storage, record)
            payload.append(data)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for record in records:
        marker = "* " if _has_content(storage, record) else "  "
        print(f"{marker}{record.archived_at} | {record.source_id} | {record.title}")
        print(f"  {record.url}")


def _has_content(storage: Storage, record) -> bool:
    if not record.content_path:
        return False
    return (storage.data_root / record.content_path).exists()


if __name__ == "__main__":
    sys.exit(main())
