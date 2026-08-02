"""Orchestration for the `load` subcommand: bootstrap -> guards -> ordered
ingest through the standard pipeline with a ClickHouseSink.

Guards run for ALL planned entities before the first row is written, so a
mid-run abort can't leave a half-guarded state.
"""

import sys
from typing import Any, Callable, Dict, Optional

from . import bootstrap, detect
from .config import Config
from .pipeline import IngestionPipeline
from .sinks.clickhouse_sink import ClickHouseSink
from .sinks.dead_letter import DeadLetterSink
from .sources.file_source import FileSource


def run_load(
    path: str,
    db: str,
    truncate: bool,
    force: bool,
    out_dir: str,
    ddl_dir: str,
    cfg: Config,
    client_factory: Callable[..., Any],
    live_db: Optional[str],
) -> Dict[str, dict]:
    if live_db and db == live_db and not force:
        raise bootstrap.LoadAbort(
            f"--db {db!r} is the engine's live database (CLICKHOUSE_DATABASE). "
            f"Dimension files with reused IDs would silently relabel all "
            f"historical facts. Pass --force if you really mean it."
        )

    plan = detect.plan_path(path)

    admin = client_factory(database=None)
    admin.command(f"CREATE DATABASE IF NOT EXISTS `{db}`")
    client = client_factory(database=db)

    if bootstrap.ensure_schema(client, ddl_dir):
        print(f"bootstrapped schema + dictionaries + rollups in '{db}'")

    for entity, _ in plan:
        bootstrap.ensure_empty(client, entity, truncate)

    planned_entities = {entity for entity, _ in plan}
    stats: Dict[str, dict] = {}
    for entity, fpath in plan:  # plan is already dimensions-first
        if entity == "ad_events":
            bootstrap.reload_dictionaries(client)
            if planned_entities == {"ad_events"} and bootstrap.dimensions_empty(client):
                print(
                    "WARNING: dimension tables are empty -- ad_events rows will "
                    "enrich to '' labels in every hourly_by_* rollup",
                    file=sys.stderr,
                )
        pipeline = IngestionPipeline(
            source=FileSource(fpath, chunk_size=cfg.FILE_CHUNK_SIZE),
            valid_sink=ClickHouseSink(client),
            dead_letter_sink=DeadLetterSink(out_dir),
            entity=entity,
            cfg=cfg,
        )
        stats[entity] = pipeline.run()
    return stats
