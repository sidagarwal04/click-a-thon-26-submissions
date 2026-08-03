"""Load real ``events.ndjson`` into ClickHouse event tables and check activity MVs.

Reads ``SPECS_ROOT/{feature_id}/events.ndjson``, flattens nested fields, and
inserts iteratively into the per-event tables created by instrumentation.

Usage:
  uv run python -m instrumentation_agent.verify_activity_mvs --feature-id 01_express_checkout
  uv run python -m instrumentation_agent.verify_activity_mvs --all --batch-size 200
  uv run python -m instrumentation_agent.verify_activity_mvs --feature-id 01_express_checkout --limit 50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from instrumentation_agent.db.meta_events import MetaEventsCRUD
from instrumentation_agent.settings import get_settings
from instrumentation_agent.utils.clickhouse import (
    ACTIVITY_EVENTS_TABLE,
    describe_table_columns,
    get_client,
)
from instrumentation_agent.utils.profiler import flatten_record
from instrumentation_agent.utils.paths import feature_paths


def _coerce_value(value: Any, ch_type: str) -> Any:
    """Coerce NDJSON values to the physical ClickHouse column type."""
    base = ch_type.split("(")[0]
    if value is None:
        if base.startswith("DateTime"):
            return "1970-01-01 00:00:00.000"
        if base == "Bool":
            return False
        if base.startswith("Int") or base.startswith("UInt"):
            return 0
        if base.startswith("Float") or base == "Decimal":
            return 0.0
        return ""

    if base.startswith("DateTime") and isinstance(value, str):
        return value.replace("Z", "").replace("T", " ")

    # Provisional meta tables are often all-String — stringify scalars.
    if base == "String" or base == "LowCardinality" or "String" in ch_type:
        if isinstance(value, bool):
            return "1" if value else "0"
        return str(value)

    if base == "Bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).lower() in {"1", "true", "yes"}

    if base.startswith("Int") or base.startswith("UInt"):
        return int(value)

    if base.startswith("Float") or base == "Decimal":
        return float(value)

    return value


def _iter_ndjson_batches(
    path: Path,
    *,
    batch_size: int,
    limit: int | None,
) -> Any:
    """Yield (batch_index, {event_name: [flattened_rows...]})."""
    batch_idx = 0
    seen = 0
    bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    batch_rows = 0

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            event_name = raw.get("event")
            if not event_name:
                continue
            flat = flatten_record(raw)
            flat.pop("event", None)
            bucket[str(event_name)].append(flat)
            batch_rows += 1
            seen += 1

            if batch_rows >= batch_size:
                batch_idx += 1
                yield batch_idx, dict(bucket)
                bucket = defaultdict(list)
                batch_rows = 0

            if limit is not None and seen >= limit:
                break

    if batch_rows:
        batch_idx += 1
        yield batch_idx, dict(bucket)


def _insert_batch(
    client: Any,
    *,
    database: str,
    event_to_table: dict[str, str],
    table_columns: dict[str, dict[str, str]],
    batch: dict[str, list[dict[str, Any]]],
) -> int:
    inserted = 0
    for event_name, rows in batch.items():
        ch_table = event_to_table.get(event_name)
        if not ch_table:
            print(f"  skip unknown event (no meta/table): {event_name}")
            continue
        columns = table_columns.get(ch_table)
        if not columns:
            print(f"  skip missing ClickHouse table: {database}.{ch_table}")
            continue

        col_names = list(columns.keys())
        data = [
            [_coerce_value(row.get(col), columns[col]) for col in col_names]
            for row in rows
        ]
        if not data:
            continue
        client.insert(
            ch_table,
            data,
            column_names=col_names,
            database=database,
        )
        inserted += len(data)
        print(f"  inserted {len(data)} row(s) -> {database}.{ch_table}")
    return inserted


def _count_table(client: Any, database: str, table: str) -> int:
    result = client.query(f"SELECT count() FROM `{database}`.`{table}`")
    return int(result.result_rows[0][0])


def _count_activity_for_events(
    client: Any,
    database: str,
    event_names: list[str],
) -> int:
    if not event_names:
        return 0
    result = client.query(
        f"""
        SELECT count()
        FROM `{database}`.`{ACTIVITY_EVENTS_TABLE}`
        WHERE event_name IN {{names:Array(String)}}
        """,
        parameters={"names": event_names},
    )
    return int(result.result_rows[0][0])


def _resolve_feature_ids(feature_id: str | None, *, all_features: bool) -> list[str]:
    settings = get_settings()
    root = Path(settings.specs_root).expanduser().resolve()
    if all_features:
        ids = sorted(
            p.name
            for p in root.iterdir()
            if p.is_dir() and (p / "events.ndjson").is_file() and (p / "spec.md").is_file()
        )
        if not ids:
            raise SystemExit(f"No feature packs with events.ndjson under {root}")
        return ids
    if not feature_id:
        raise SystemExit("Provide --feature-id or --all")
    return [feature_id]


def _load_feature(
    feature_id: str,
    *,
    batch_size: int,
    limit: int | None,
    sleep_s: float,
    verify: bool,
) -> int:
    settings = get_settings()
    paths = feature_paths(feature_id, settings=settings)
    events_path = paths.feature_dir / "events.ndjson"
    if not events_path.is_file():
        print(f"ERROR: missing {events_path}", file=sys.stderr)
        return 1

    meta_events = MetaEventsCRUD().list_by_feature_id(feature_id)
    if not meta_events:
        print(
            f"ERROR: no meta_events for {feature_id!r}. Run instrumentation first.",
            file=sys.stderr,
        )
        return 1

    event_to_table = {
        str(e["event_name"]): str(e.get("ch_table") or e["event_name"]) for e in meta_events
    }
    event_names = list(event_to_table.keys())

    print(f"\n======== {feature_id} ========")
    print(f"ndjson={events_path}")
    print(f"database={settings.clickhouse_database}")
    print(f"mapped events={len(event_to_table)} batch_size={batch_size} limit={limit}")
    for name, table in event_to_table.items():
        print(f"  {name} -> {table}")

    client = get_client(settings)
    database = settings.clickhouse_database
    try:
        table_columns: dict[str, dict[str, str]] = {}
        for ch_table in sorted(set(event_to_table.values())):
            cols = describe_table_columns(client, database, ch_table)
            if not cols:
                print(
                    f"ERROR: ClickHouse table missing: {database}.{ch_table}. "
                    "Run instrumentation apply_clickhouse first.",
                    file=sys.stderr,
                )
                return 1
            table_columns[ch_table] = cols

        activity_before = 0
        if verify:
            try:
                activity_before = _count_activity_for_events(client, database, event_names)
            except Exception as exc:  # noqa: BLE001
                print(f"WARN: cannot read activity_events yet: {exc}")
                verify = False
            else:
                print(f"activity_events rows (these events) before: {activity_before}")

        total_inserted = 0
        for batch_idx, batch in _iter_ndjson_batches(
            events_path, batch_size=batch_size, limit=limit
        ):
            print(f"\n=== batch {batch_idx} ({sum(len(v) for v in batch.values())} rows) ===")
            total_inserted += _insert_batch(
                client,
                database=database,
                event_to_table=event_to_table,
                table_columns=table_columns,
                batch=batch,
            )
            if sleep_s > 0:
                time.sleep(sleep_s)

        print(f"\ninserted total for {feature_id}: {total_inserted}")
        for ch_table in sorted(set(event_to_table.values())):
            print(f"  {database}.{ch_table} count={_count_table(client, database, ch_table)}")

        if verify:
            time.sleep(max(sleep_s, 0.5))
            activity_after = _count_activity_for_events(client, database, event_names)
            delta = activity_after - activity_before
            print(
                f"activity_events rows (these events) after: {activity_after} "
                f"(+{delta})"
            )
            if delta < total_inserted:
                print(
                    f"FAIL: expected activity_events +>={total_inserted}, got +{delta}. "
                    "Check mv_<event>_to_activity in this database.",
                    file=sys.stderr,
                )
                return 2
            print("PASS: NDJSON inserts were forwarded into activity_events.")
        return 0
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read SPECS_ROOT/{feature}/events.ndjson and iteratively insert into "
            "ClickHouse event tables; optionally verify activity_events MVs."
        ),
    )
    parser.add_argument(
        "--feature-id",
        default=None,
        help="Single feature id under SPECS_ROOT (e.g. 01_express_checkout).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Load every feature pack under SPECS_ROOT that has events.ndjson.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="NDJSON rows per insert batch (default: 200).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max NDJSON rows to load per feature (for smoke tests).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to sleep after each batch (default: 0.2).",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip activity_events MV count check.",
    )
    args = parser.parse_args(argv)

    feature_ids = _resolve_feature_ids(args.feature_id, all_features=args.all)
    worst = 0
    for feature_id in feature_ids:
        code = _load_feature(
            feature_id,
            batch_size=args.batch_size,
            limit=args.limit,
            sleep_s=args.sleep,
            verify=not args.no_verify,
        )
        worst = max(worst, code)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
