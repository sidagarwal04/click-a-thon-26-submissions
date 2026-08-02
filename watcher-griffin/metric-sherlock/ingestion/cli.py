"""Runnable entrypoint for the ingestion module.

    python -m ingestion.cli batch  --entity ad_events --path ../Data/ad_events.parquet --out-dir ./ingestion/_out
    python -m ingestion.cli stream --entity apps --watch-dir ./ingestion/_incoming --out-dir ./ingestion/_out
    python -m ingestion.cli load --db unseen_v2 Unseen-data/
"""

import argparse
import os
import sys
from typing import List, Optional

from . import schemas
from .bootstrap import LoadAbort
from .config import load_config
from .detect import EntityDetectionError
from .loader import run_load
from .pipeline import IngestionPipeline
from .sinks.dead_letter import DeadLetterSink
from .sinks.jsonl_sink import JsonlSink
from .sources.file_source import FileSource
from .sources.live_tail_source import LiveTailSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ingestion.cli")
    sub = parser.add_subparsers(dest="mode", required=True)

    batch_p = sub.add_parser("batch", help="ingest a single file, then exit")
    batch_p.add_argument("--entity", required=True, choices=schemas.ENTITIES)
    batch_p.add_argument("--path", required=True)
    batch_p.add_argument("--out-dir", default="./ingestion/_out")

    stream_p = sub.add_parser("stream", help="tail a watch directory forever (Ctrl+C to stop)")
    stream_p.add_argument("--entity", required=True, choices=schemas.ENTITIES)
    stream_p.add_argument("--watch-dir", default="./ingestion/_incoming")
    stream_p.add_argument("--out-dir", default="./ingestion/_out")
    stream_p.add_argument("--poll-interval-seconds", type=float, default=None)

    load_p = sub.add_parser("load", help="validate a file or directory and insert into ClickHouse")
    load_p.add_argument("path", help="data file or directory (entities auto-detected)")
    load_p.add_argument("--db", required=True, help="target ClickHouse database (always explicit)")
    load_p.add_argument("--truncate", action="store_true", help="empty target tables before inserting")
    load_p.add_argument("--force", action="store_true", help="allow --db to equal the live CLICKHOUSE_DATABASE")
    load_p.add_argument("--out-dir", default="./ingestion/_out", help="dead-letter destination")
    load_p.add_argument("--ddl-dir", default=None, help="directory holding schema.sql/dictionaries.sql/rollups.sql (default: <repo>/clickhouse)")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config()

    if args.mode == "load":
        from dotenv import load_dotenv

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(repo_root, "utils", ".env"))
        ddl_dir = args.ddl_dir or os.path.join(repo_root, "clickhouse")

        def client_factory(database=None):
            import clickhouse_connect

            return clickhouse_connect.get_client(
                host=os.environ["CLICKHOUSE_HOST"],
                port=int(os.environ["CLICKHOUSE_PORT"]),
                username=os.environ["CLICKHOUSE_USER"],
                password=os.environ["CLICKHOUSE_PASSWORD"],
                secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
                **({"database": database} if database else {}),
            )

        try:
            stats = run_load(
                path=args.path,
                db=args.db,
                truncate=args.truncate,
                force=args.force,
                out_dir=args.out_dir,
                ddl_dir=ddl_dir,
                cfg=cfg,
                client_factory=client_factory,
                live_db=os.environ.get("CLICKHOUSE_DATABASE"),
            )
        except (LoadAbort, EntityDetectionError) as exc:
            print(f"aborted: {exc}", file=sys.stderr)
            return 2
        for entity, s in stats.items():
            line = f"{entity}: accepted={s['accepted']} rejected={s['rejected']} skipped={s['skipped']}"
            if s["extra_fields_seen"]:
                line += f" extra_fields={s['extra_fields_seen']}"
            print(line)
        return 0

    if args.mode == "batch":
        source = FileSource(args.path, chunk_size=cfg.FILE_CHUNK_SIZE)
    else:
        interval = args.poll_interval_seconds or cfg.POLL_INTERVAL_SECONDS
        source = LiveTailSource(args.watch_dir, poll_interval_seconds=interval)

    valid_sink = JsonlSink(args.out_dir, suffix="valid")
    dead_sink = DeadLetterSink(args.out_dir)

    pipeline = IngestionPipeline(source, valid_sink, dead_sink, args.entity, cfg)
    stats = pipeline.run()
    line = f"accepted={stats['accepted']} rejected={stats['rejected']} skipped={stats['skipped']}"
    if stats["extra_fields_seen"]:
        line += f" extra_fields={stats['extra_fields_seen']}"
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
