#!/usr/bin/env python3
"""Run the checked-in solution against the official CSVs with embedded ClickHouse.

This verifier is intentionally not the production processor. It loads the exact
DDL, executes the ClickHouse interval oracle, publishes initial signed boundaries,
builds the global minute cache, and runs publication gates. It writes only to a
temporary directory and prints a JSON evidence record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import tempfile
import time
from typing import Any

from chdb.session import Session


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED_RAW_SHA256 = "15ce6df78e7239820fb9951f2a5c68de2abb47a0950068947e1a0344a0283a96"
EXPECTED_CONTENT_SHA256 = "e013c4958e9b6396f9cc6cd2681bb6944bb65dc810b7f0925f78254ed9c7ddd4"
POLICY_VERSION = "sonyliv-active-v1"
BATCH_ID = "00000000-0000-0000-0000-000000000001"
CORRECTION_BATCH_ID = "00000000-0000-0000-0000-000000000002"
CORRECTION_ORACLE_ID = "00000000-0000-0000-0000-000000000102"
FULL_REBUILD_ORACLE_ID = "00000000-0000-0000-0000-000000000103"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sql_tree_sha256(sql_dir: pathlib.Path) -> str:
    """Hash every SQL artifact with length-delimited relative names and bytes."""
    digest = hashlib.sha256()
    for path in sorted(sql_dir.glob("*.sql")):
        relative_name = path.relative_to(sql_dir).as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative_name).to_bytes(4, "big"))
        digest.update(relative_name)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def substitute(sql: str, values: dict[str, str]) -> str:
    for placeholder, expression in values.items():
        sql = sql.replace(placeholder, expression)
    unresolved = [fragment for fragment in sql.split() if fragment.startswith("{")]
    if unresolved:
        raise ValueError(f"Unresolved query parameters: {unresolved[:5]}")
    return sql


def rows(session: Session, sql: str) -> list[dict[str, Any]]:
    raw = str(session.query(sql, "JSONEachRow")).strip()
    return [json.loads(line) for line in raw.splitlines()] if raw else []


def elapsed(session: Session, sql: str) -> float:
    started = time.perf_counter()
    session.query(sql)
    return time.perf_counter() - started


def expect_failure(session: Session, sql: str, expected_text: str) -> bool:
    try:
        session.query(sql)
    except RuntimeError as error:
        if expected_text not in str(error):
            raise
        return True
    raise RuntimeError(f"query unexpectedly succeeded; expected: {expected_text}")


def stable_json_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True, type=pathlib.Path)
    parser.add_argument("--content", required=True, type=pathlib.Path)
    parser.add_argument("--heartbeat-timeout-ms", default=120_000, type=int)
    parser.add_argument(
        "--evaluation-as-of",
        default="2026-07-26 11:32:04.847",
        help="UTC watermark used for reproducible clipping of open intervals",
    )
    args = parser.parse_args()

    raw_sha = sha256(args.raw)
    content_sha = sha256(args.content)
    if raw_sha != EXPECTED_RAW_SHA256 or content_sha != EXPECTED_CONTENT_SHA256:
        raise SystemExit(
            "Source hash mismatch; refusing to label results as official-package evidence"
        )

    evidence: dict[str, Any] = {
        "raw_sha256": raw_sha,
        "content_sha256": content_sha,
        "heartbeat_timeout_ms": args.heartbeat_timeout_ms,
        "evaluation_as_of_utc": args.evaluation_as_of,
        "policy_version": POLICY_VERSION,
        "code_identity": {
            "policy_yaml_sha256": sha256(ROOT / "policy.yaml"),
            "verifier_sha256": sha256(pathlib.Path(__file__).resolve()),
            "sql_tree_sha256": sql_tree_sha256(ROOT / "sql"),
            "sql_files": len(list((ROOT / "sql").glob("*.sql"))),
        },
    }

    with tempfile.TemporaryDirectory(prefix="sonyliv-chdb-", dir="/private/tmp") as db_path:
        session = Session(db_path)

        schema_sql = (ROOT / "sql/00_schema.sql").read_text()
        evidence["schema_seconds"] = round(elapsed(session, schema_sql), 3)

        content_path = sql_string(str(args.content.resolve()))
        content_load = f"""
        INSERT INTO sonyliv.content_dim
        SELECT
            toInt32(content_id),
            title,
            if(empty(trim(video_type)), '__unknown__', lower(trim(video_type))),
            if(empty(trim(category)), '__unknown__', trim(category)),
            toUInt64(1),
            now64(3, 'UTC')
        FROM file(
            {content_path},
            CSVWithNames,
            'content_id Int64, title String, video_type String, category String'
        )
        """
        evidence["content_load_seconds"] = round(elapsed(session, content_load), 3)
        session.query("SYSTEM RELOAD DICTIONARY sonyliv.content_dictionary")

        raw_path = sql_string(str(args.raw.resolve()))
        raw_load = f"""
        INSERT INTO sonyliv.raw_events
        (
            ingest_batch_id, ingest_version, ingested_at, source_row_hash,
            video_session_id, user_id, content_id, event_type, event,
            event_time, session_start_time, platform, app_version, country,
            audio_language, subtitle_language, player_version
        )
        SELECT
            toUUID('{BATCH_ID}'),
            rowNumberInAllBlocks(),
            now64(3, 'UTC'),
            reinterpretAsUInt128(sipHash128(
                content_id, video_session_id, user_id, event_type, event,
                event_timestamp, platform, app_version, country, audio_language,
                subtitle_language, player_version, session_start_epoch
            )),
            video_session_id,
            user_id,
            toInt32(content_id),
            event_type,
            event,
            fromUnixTimestamp64Milli(event_timestamp, 'UTC'),
            fromUnixTimestamp64Milli(session_start_epoch, 'UTC'),
            platform,
            app_version,
            country,
            audio_language,
            subtitle_language,
            player_version
        FROM file(
            {raw_path},
            CSVWithNames,
            'content_id Int64, video_session_id String, user_id String,
             event_type String, event String, event_timestamp Int64,
             platform String, app_version String, country String,
             audio_language String, subtitle_language String,
             player_version String, session_start_epoch Int64'
        )
        SETTINGS max_threads = 1, input_format_parallel_parsing = 0
        """
        evidence["raw_load_seconds"] = round(elapsed(session, raw_load), 3)
        evidence["loaded"] = rows(
            session,
            """
            SELECT count() AS rows, uniqExact(video_session_id) AS sessions,
                   uniqExact(user_id) AS event_users, uniqExact(content_id) AS content_ids
            FROM sonyliv.raw_events
            """,
        )[0]
        evidence["time_contract"] = rows(
            session,
            f"""
            WITH source AS
            (
                SELECT
                    event_timestamp,
                    session_start_epoch,
                    video_session_id,
                    event_type,
                    fromUnixTimestamp64Milli(event_timestamp, 'UTC') AS event_time
                FROM file(
                    {raw_path},
                    CSVWithNames,
                    'content_id Int64, video_session_id String, user_id String,
                     event_type String, event String, event_timestamp Int64,
                     platform String, app_version String, country String,
                     audio_language String, subtitle_language String,
                     player_version String, session_start_epoch Int64'
                )
            )
            SELECT
                min(length(toString(event_timestamp))) AS min_event_epoch_digits,
                max(length(toString(event_timestamp))) AS max_event_epoch_digits,
                min(length(toString(session_start_epoch))) AS min_start_epoch_digits,
                max(length(toString(session_start_epoch))) AS max_start_epoch_digits,
                countIf(event_timestamp % 1000 != 0) AS event_values_with_milliseconds,
                countIf(session_start_epoch % 1000 != 0) AS start_values_with_milliseconds,
                min(event_time) AS min_event_time_utc,
                max(event_time) AS max_event_time_utc,
                countIf(
                    toDate(event_time, 'UTC') != toDate(event_time, 'Asia/Kolkata')
                ) AS event_rows_with_different_ist_date,
                uniqExactIf(
                    video_session_id,
                    toDate(event_time, 'UTC') != toDate(event_time, 'Asia/Kolkata')
                ) AS sessions_with_different_ist_event_date,
                countIf(
                    event_type = 'VideoSessionStart'
                    AND toDate(event_time, 'UTC') != toDate(event_time, 'Asia/Kolkata')
                ) AS session_starts_with_different_ist_date,
                countIf(toDate(event_time, 'UTC') = toDate('2026-07-26'))
                    AS july_26_utc_event_rows,
                countIf(toDate(event_time, 'Asia/Kolkata') = toDate('2026-07-26'))
                    AS july_26_ist_event_rows
            FROM source
            """,
        )[0]

        seed_sql = substitute(
            (ROOT / "sql/09_initialize_pipeline_lineage.sql").read_text(),
            {
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{source_snapshot_hash:String}": sql_string(EXPECTED_RAW_SHA256),
                "{seed_membership_dedup_token:String}": "'verify-seed-members-v1'",
                "{seed_header_dedup_token:String}": "'verify-seed-header-v1'",
            },
        )
        evidence["pipeline_seed"] = rows(session, seed_sql)

        workset_sql = substitute(
            (ROOT / "sql/11_select_touched_workset.sql").read_text(),
            {
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{adjustment_batch_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{max_touched_sessions:UInt64}": "toUInt64(20000)",
                "{lease_owner:String}": "'verify-compactor'",
                "{lease_epoch:UInt64}": "toUInt64(1)",
                "{claim_lease_ms:UInt64}": "toUInt64(600000)",
                "{workset_dedup_token:String}": "'verify-workset-v1'",
            },
        )
        evidence["workset"] = rows(session, workset_sql)

        interval_sql = substitute(
            (ROOT / "sql/10_reference_intervals.sql").read_text(),
            {
                "{heartbeat_timeout_ms:UInt64}": f"toUInt64({args.heartbeat_timeout_ms})",
                "{evaluation_as_of:String}": sql_string(args.evaluation_as_of),
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{oracle_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{full_scan:UInt8}": "toUInt8(1)",
                "{workset_batch_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{oracle_insert_dedup_token:String}": "'verify-oracle-v1'",
                "{source_snapshot_hash:String}": sql_string(EXPECTED_RAW_SHA256),
                "{oracle_manifest_dedup_token:String}": "'verify-oracle-manifest-v1'",
            },
        )
        evidence["interval_build_seconds"] = round(elapsed(session, interval_sql), 3)
        evidence["intervals"] = rows(
            session,
            """
            SELECT
                count() AS intervals,
                uniqExact(video_session_id) AS active_sessions,
                round(sum(dateDiff('millisecond', start_time, end_time)) / 3600000.0, 6)
                    AS active_session_hours,
                countIf(
                    toDate(start_time, 'UTC')
                    != toDate(end_time - toIntervalMillisecond(1), 'UTC')
                )
                    AS cross_day_intervals
            FROM sonyliv.active_intervals_reference
            """,
        )[0]

        evidence["oracle_manifest"] = rows(
            session,
            f"""
            SELECT * EXCEPT sealed_at
            FROM sonyliv.oracle_run_manifests
            WHERE oracle_run_id = toUUID('{BATCH_ID}')
              AND pipeline_run_id = toUUID('{BATCH_ID}')
              AND policy_version = '{POLICY_VERSION}'
            """,
        )

        candidate_sql = substitute(
            (ROOT / "sql/12_stage_session_candidates.sql").read_text(),
            {
                "{adjustment_batch_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{state_revision:UInt64}": "toUInt64(1)",
                "{oracle_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{evaluation_as_of:String}": sql_string(args.evaluation_as_of),
                "{candidate_dedup_token:String}": "'verify-candidates-v1'",
            },
        )
        evidence["candidates"] = rows(session, candidate_sql)

        state_diff_tokens = {
            "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
            "{adjustment_batch_id:UUID}": f"toUUID('{BATCH_ID}')",
            "{state_revision:UInt64}": "toUInt64(1)",
            "{policy_version:String}": sql_string(POLICY_VERSION),
            "{affected_users_dedup_token:String}": "'verify-affected-users-v1'",
            "{old_session_changes_dedup_token:String}": "'verify-old-session-changes-v1'",
            "{new_session_changes_dedup_token:String}": "'verify-new-session-changes-v1'",
            "{old_user_changes_dedup_token:String}": "'verify-old-user-changes-v1'",
            "{session_tombstones_dedup_token:String}": "'verify-session-tombstones-v1'",
            "{session_state_maps_dedup_token:String}": "'verify-session-state-maps-v1'",
            "{session_state_versions_dedup_token:String}": "'verify-session-state-versions-v1'",
            "{user_candidates_dedup_token:String}": "'verify-user-candidates-v1'",
            "{new_user_changes_dedup_token:String}": "'verify-new-user-changes-v1'",
            "{user_tombstones_dedup_token:String}": "'verify-user-tombstones-v1'",
            "{user_state_maps_dedup_token:String}": "'verify-user-state-maps-v1'",
        }
        state_diff_sql = substitute(
            (ROOT / "sql/13_apply_state_differences.sql").read_text(),
            state_diff_tokens,
        )
        evidence["state_difference_seconds"] = round(elapsed(session, state_diff_sql), 3)

        boundary_sql = substitute(
            (ROOT / "sql/20_publish_boundaries.sql").read_text(),
            {
                "{adjustment_batch_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{state_revision:UInt64}": "toUInt64(1)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{lease_owner:String}": "'verify-compactor'",
                "{lease_epoch:UInt64}": "toUInt64(1)",
                "{source_snapshot_hash:String}": sql_string(EXPECTED_RAW_SHA256),
                "{boundary_adjustments_dedup_token:String}": "'verify-boundaries-v1'",
                "{adjustment_ledger_dedup_token:String}": "'verify-adjustment-ledger-v1'",
            },
        )
        evidence["boundary_publish_seconds"] = round(elapsed(session, boundary_sql), 3)
        evidence["boundaries"] = rows(
            session,
            """
            SELECT
                count() AS adjustment_rows,
                countIf(entity = 'session') AS session_adjustments,
                countIf(entity = 'user') AS user_adjustments,
                uniqExact(tuple(entity, rollup_mask, service_date, boundary_time,
                                platform, country, video_type, content_id)) AS unique_point_keys
            FROM sonyliv.boundary_adjustments
            """,
        )[0]

        checkpoint_sql = substitute(
            (ROOT / "sql/14_checkpoint_touched_batch.sql").read_text(),
            {
                "{adjustment_batch_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{state_revision:UInt64}": "toUInt64(1)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{lease_epoch:UInt64}": "toUInt64(1)",
                "{input_manifest_hash:String}": sql_string(EXPECTED_RAW_SHA256),
                "{dirty_checkpoint_dedup_token:String}": "'verify-dirty-checkpoint-v1'",
                "{processing_checkpoint_dedup_token:String}": "'verify-processing-checkpoint-v1'",
            },
        )
        evidence["checkpoint"] = rows(session, checkpoint_sql)

        snapshot_sql = substitute(
            (ROOT / "sql/25_seal_delta_snapshot.sql").read_text(),
            {
                "{source_delta_snapshot:UInt128}": "toUInt128(1)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{snapshot_membership_dedup_token:String}": "'verify-snapshot-members-v1'",
                "{snapshot_points_dedup_token:String}": "'verify-snapshot-points-v1'",
                "{delta_snapshot_dedup_token:String}": "'verify-delta-snapshot-v1'",
            },
        )
        evidence["delta_snapshot_seconds"] = round(elapsed(session, snapshot_sql), 3)

        cache_sql = substitute(
            (ROOT / "sql/31_refresh_minute_cache.sql").read_text(),
            {
                "{service_date:Date}": "toDate('2026-07-26')",
                "{entity:String}": "'session'",
                "{rollup_mask:UInt16}": "toUInt16(0)",
                "{generation:UInt64}": "toUInt64(1)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(1)",
                "{generation_dedup_token:String}": "'verify-minute-generation-v1'",
            },
        )
        evidence["minute_cache_seconds"] = round(elapsed(session, cache_sql), 3)
        evidence["hot_hour"] = rows(
            session,
            """
            SELECT
                max(minute_peak) AS peak,
                round(sum(active_entity_ms) / 3600000.0, 6) AS time_weighted_average,
                count() AS nonzero_minute_rows
            FROM sonyliv.concurrency_minute_versions
            WHERE generation = 1
              AND entity = 'session'
              AND rollup_mask = 0
              AND minute_start >= toDateTime64('2026-07-26 10:00:00', 3, 'UTC')
              AND minute_start < toDateTime64('2026-07-26 11:00:00', 3, 'UTC')
            """,
        )[0]

        exact_sql = substitute(
            (ROOT / "sql/30_exact_metrics.sql").read_text(),
            {
                "{range_start:String}": "'2026-07-26 10:00:00.000'",
                "{range_end:String}": "'2026-07-26 11:00:00.000'",
                "{bucket_ms:UInt64}": "toUInt64(60000)",
                "{entity:String}": "'session'",
                "{rollup_mask:UInt16}": "toUInt16(0)",
                "{platform_filter:String}": "'*'",
                "{country_filter:String}": "'*'",
                "{video_type_filter:String}": "'*'",
                "{content_id_filter:Int64}": "toInt64(-2147483648)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(1)",
            },
        )
        started = time.perf_counter()
        exact_rows = rows(session, exact_sql)
        exact_metric_rows = [row for row in exact_rows if "peak_concurrency" in row]
        evidence["exact_bucket_query_seconds"] = round(time.perf_counter() - started, 3)
        evidence["exact_bucket_query"] = {
            "rows": len(exact_metric_rows),
            "peak": max((row["peak_concurrency"] for row in exact_metric_rows), default=0),
            "time_weighted_average": round(
                sum(row["active_entity_ms"] for row in exact_metric_rows) / 3_600_000.0,
                6,
            ),
        }

        baseline_sql = substitute(
            (ROOT / "sql/60_session_independent_baseline.sql").read_text(),
            {
                "{service_date:Date}": "toDate('2026-07-26')",
                "{heartbeat_timeout_ms:UInt64}": f"toUInt64({args.heartbeat_timeout_ms})",
                "{generation:UInt64}": "toUInt64(1)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(1)",
            },
        )
        started = time.perf_counter()
        baseline_rows = rows(session, baseline_sql)
        evidence["session_independent_baseline_seconds"] = round(
            time.perf_counter() - started, 3
        )
        hot_baseline = [
            row
            for row in baseline_rows
            if "2026-07-26 10:00:00" <= row["minute_start"] < "2026-07-26 11:00:00"
        ]
        evidence["session_independent_hot_hour"] = {
            "minute_boundary_rows": len(hot_baseline),
            "exact_boundary_sample_peak": max(
                (row["exact_sessions"] for row in hot_baseline), default=0
            ),
            "heartbeat_lease_sample_peak": max(
                (row["heartbeat_lease_sessions"] for row in hot_baseline), default=0
            ),
            "mean_overcount": round(
                sum(row["overcount"] for row in hot_baseline) / max(len(hot_baseline), 1),
                6,
            ),
            "maximum_overcount": max(
                (row["overcount"] for row in hot_baseline), default=0
            ),
        }

        candidate_validation_sql = substitute(
            (ROOT / "sql/34_validate_candidate_generation.sql").read_text(),
            {
                "{service_date:Date}": "toDate('2026-07-26')",
                "{entity:String}": "'session'",
                "{rollup_mask:UInt16}": "toUInt16(0)",
                "{generation:UInt64}": "toUInt64(1)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(1)",
                "{sealed_attestation_dedup_token:String}": "'verify-sealed-attestation-v1'",
            },
        )
        evidence["candidate_generation_validation"] = rows(
            session, candidate_validation_sql
        )

        validation_sql = substitute(
            (ROOT / "sql/40_validation.sql").read_text(),
            {
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{service_date:Date}": "toDate('2026-07-26')",
                "{generation:UInt64}": "toUInt64(1)",
                "{oracle_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(1)",
            },
        )
        started = time.perf_counter()
        evidence["validation_last_result"] = rows(session, validation_sql)
        evidence["validation_seconds"] = round(time.perf_counter() - started, 3)

        raw_oracle_validation_sql = substitute(
            (ROOT / "sql/33_validate_raw_oracle_generation.sql").read_text(),
            {
                "{service_date:Date}": "toDate('2026-07-26')",
                "{entity:String}": "'session'",
                "{rollup_mask:UInt16}": "toUInt16(0)",
                "{generation:UInt64}": "toUInt64(1)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(1)",
                "{oracle_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{oracle_attestation_dedup_token:String}": "'verify-oracle-attestation-v1'",
            },
        )
        evidence["raw_oracle_generation_validation"] = rows(
            session, raw_oracle_validation_sql
        )

        publish_sql = substitute(
            (ROOT / "sql/35_publish_generation.sql").read_text(),
            {
                "{service_date:Date}": "toDate('2026-07-26')",
                "{entity:String}": "'session'",
                "{rollup_mask:UInt16}": "toUInt16(0)",
                "{generation:UInt64}": "toUInt64(1)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(1)",
                "{oracle_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{generation_manifest_dedup_token:String}": "'verify-generation-manifest-v1'",
            },
        )
        evidence["published_generation"] = rows(session, publish_sql)

        generation1_dashboard_values = {
            "{service_date:Date}": "toDate('2026-07-26')",
            "{entity:String}": "'session'",
            "{rollup_mask:UInt16}": "toUInt16(0)",
            "{generation:UInt64}": "toUInt64(1)",
            "{policy_version:String}": sql_string(POLICY_VERSION),
            "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
            "{source_delta_snapshot:UInt128}": "toUInt128(1)",
            "{range_start:String}": "'2026-07-26 10:00:00.000'",
            "{range_end:String}": "'2026-07-26 11:00:00.000'",
            "{platform_filter:String}": "'*'",
            "{country_filter:String}": "'*'",
            "{video_type_filter:String}": "'*'",
            "{content_id_filter:Int64}": "toInt64(-2147483648)",
        }
        generation1_dashboard_sql = substitute(
            (ROOT / "sql/32_dashboard_queries.sql").read_text(),
            generation1_dashboard_values,
        )
        generation1_before = {
            "exact_query_hash": stable_json_hash(rows(session, exact_sql)),
            "dashboard_query_hash": stable_json_hash(
                rows(session, generation1_dashboard_sql)
            ),
            "snapshot": rows(
                session,
                f"""
                SELECT
                    adjustment_batches,
                    adjustment_rows,
                    adjustment_ledger_hash,
                    point_rows,
                    point_hash
                FROM sonyliv.delta_snapshots
                WHERE source_delta_snapshot = 1
                  AND pipeline_run_id = toUUID('{BATCH_ID}')
                  AND policy_version = '{POLICY_VERSION}'
                """,
            )[0],
            "manifest_answer_hash": evidence["published_generation"][-1]["answer_hash"],
            "manifest_minute_rows": evidence["published_generation"][-1]["minute_rows"],
        }

        evidence["gates"] = rows(
            session,
            f"""
            WITH points AS
            (
                SELECT service_date, boundary_time, sum(delta) AS d
                FROM sonyliv.concurrency_delta_snapshots
                WHERE source_delta_snapshot = 1
                  AND pipeline_run_id = toUUID('{BATCH_ID}')
                  AND policy_version = '{POLICY_VERSION}'
                  AND entity = 'session' AND rollup_mask = 0
                GROUP BY service_date, boundary_time
            ), curve AS
            (
                SELECT *, sum(d) OVER
                    (PARTITION BY service_date ORDER BY boundary_time
                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS c
                FROM points
            )
            SELECT
                (SELECT count() FROM sonyliv.active_intervals_reference
                 WHERE end_time <= start_time) AS invalid_intervals,
                (SELECT count() FROM
                    (SELECT service_date, sum(delta) AS balance
                     FROM sonyliv.concurrency_delta_snapshots
                     WHERE source_delta_snapshot = 1
                       AND pipeline_run_id = toUUID('{BATCH_ID}')
                       AND policy_version = '{POLICY_VERSION}'
                       AND entity = 'session' AND rollup_mask = 0
                     GROUP BY service_date HAVING balance != 0)) AS unbalanced_days,
                countIf(c < 0) AS negative_curve_points,
                max(c) AS global_peak_all_dates
            FROM curve
            """,
        )[0]

        # ---- Late-pause correction fixture ---------------------------------
        # Insert one pause in the middle of a long active interval. This arrives
        # after the initial generation and must retract only the affected tail.
        fixture_target_sql = f"""
        SELECT
            video_session_id,
            start_time,
            end_time,
            start_time + toIntervalMillisecond(
                intDiv(dateDiff('millisecond', start_time, end_time), 2)
            ) AS inserted_pause_time
        FROM sonyliv.active_intervals_reference
        WHERE oracle_run_id = toUUID('{BATCH_ID}')
          AND toDate(start_time, 'UTC') = toDate('2026-07-26')
          AND dateDiff('second', start_time, end_time) > 300
        ORDER BY dateDiff('millisecond', start_time, end_time) DESC, video_session_id
        LIMIT 1
        """
        fixture_target = rows(session, fixture_target_sql)[0]
        evidence["late_pause_fixture_target"] = fixture_target

        late_insert_sql = f"""
        INSERT INTO sonyliv.raw_events
        (
            ingest_batch_id, ingest_version, ingested_at, source_row_hash,
            video_session_id, user_id, content_id, event_type, event,
            event_time, session_start_time, platform, app_version, country,
            audio_language, subtitle_language, player_version
        )
        WITH
            target AS ({fixture_target_sql}),
            anchor AS
            (
                SELECT
                    r.video_session_id,
                    argMinIf(r.user_id, r.event_time, r.event_type = 'VideoSessionStart') AS user_id,
                    argMinIf(r.content_id, r.event_time, r.event_type = 'VideoSessionStart') AS content_id,
                    argMinIf(r.platform, r.event_time, r.event_type = 'VideoSessionStart') AS platform,
                    argMinIf(r.app_version, r.event_time, r.event_type = 'VideoSessionStart') AS app_version,
                    argMinIf(r.country, r.event_time, r.event_type = 'VideoSessionStart') AS country,
                    argMinIf(r.audio_language, r.event_time, r.event_type = 'VideoSessionStart') AS audio_language,
                    argMinIf(r.subtitle_language, r.event_time, r.event_type = 'VideoSessionStart') AS subtitle_language,
                    argMinIf(r.player_version, r.event_time, r.event_type = 'VideoSessionStart') AS player_version,
                    min(r.session_start_time) AS session_start_time
                FROM sonyliv.raw_events AS r
                INNER JOIN target AS t USING (video_session_id)
                GROUP BY r.video_session_id
            )
        SELECT
            toUUID('{CORRECTION_BATCH_ID}'),
            toUInt64(1),
            now64(3, 'UTC'),
            reinterpretAsUInt128(
                sipHash128(t.video_session_id, t.inserted_pause_time, 'late-pause-fixture-v1')
            ),
            t.video_session_id,
            a.user_id,
            a.content_id,
            'VideoHeartbeat',
            'pause',
            t.inserted_pause_time,
            a.session_start_time,
            a.platform,
            a.app_version,
            a.country,
            a.audio_language,
            a.subtitle_language,
            a.player_version
        FROM target AS t
        INNER JOIN anchor AS a USING (video_session_id)
        SETTINGS insert_deduplication_token = 'verify-late-pause-input-v1'
        """
        evidence["late_pause_insert_seconds"] = round(elapsed(session, late_insert_sql), 3)

        correction_workset_sql = substitute(
            (ROOT / "sql/11_select_touched_workset.sql").read_text(),
            {
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{adjustment_batch_id:UUID}": f"toUUID('{CORRECTION_BATCH_ID}')",
                "{max_touched_sessions:UInt64}": "toUInt64(10)",
                "{lease_owner:String}": "'verify-compactor'",
                "{lease_epoch:UInt64}": "toUInt64(2)",
                "{claim_lease_ms:UInt64}": "toUInt64(600000)",
                "{workset_dedup_token:String}": "'verify-workset-v2'",
            },
        )
        evidence["late_correction_workset"] = rows(session, correction_workset_sql)

        correction_oracle_sql = substitute(
            (ROOT / "sql/10_reference_intervals.sql").read_text(),
            {
                "{heartbeat_timeout_ms:UInt64}": f"toUInt64({args.heartbeat_timeout_ms})",
                "{evaluation_as_of:String}": sql_string(args.evaluation_as_of),
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{oracle_run_id:UUID}": f"toUUID('{CORRECTION_ORACLE_ID}')",
                "{full_scan:UInt8}": "toUInt8(0)",
                "{workset_batch_id:UUID}": f"toUUID('{CORRECTION_BATCH_ID}')",
                "{oracle_insert_dedup_token:String}": "'verify-oracle-v2'",
                "{source_snapshot_hash:String}": sql_string(EXPECTED_RAW_SHA256),
                "{oracle_manifest_dedup_token:String}": "'verify-unused-scoped-oracle-manifest-v2'",
            },
        )
        elapsed(session, correction_oracle_sql)

        correction_candidate_sql = substitute(
            (ROOT / "sql/12_stage_session_candidates.sql").read_text(),
            {
                "{adjustment_batch_id:UUID}": f"toUUID('{CORRECTION_BATCH_ID}')",
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{state_revision:UInt64}": "toUInt64(2)",
                "{oracle_run_id:UUID}": f"toUUID('{CORRECTION_ORACLE_ID}')",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{evaluation_as_of:String}": sql_string(args.evaluation_as_of),
                "{candidate_dedup_token:String}": "'verify-candidates-v2'",
            },
        )
        evidence["late_correction_candidates"] = rows(session, correction_candidate_sql)

        correction_state_tokens = {
            "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
            "{adjustment_batch_id:UUID}": f"toUUID('{CORRECTION_BATCH_ID}')",
            "{state_revision:UInt64}": "toUInt64(2)",
            "{policy_version:String}": sql_string(POLICY_VERSION),
            "{affected_users_dedup_token:String}": "'verify-affected-users-v2'",
            "{old_session_changes_dedup_token:String}": "'verify-old-session-changes-v2'",
            "{new_session_changes_dedup_token:String}": "'verify-new-session-changes-v2'",
            "{old_user_changes_dedup_token:String}": "'verify-old-user-changes-v2'",
            "{session_tombstones_dedup_token:String}": "'verify-session-tombstones-v2'",
            "{session_state_maps_dedup_token:String}": "'verify-session-state-maps-v2'",
            "{session_state_versions_dedup_token:String}": "'verify-session-state-versions-v2'",
            "{user_candidates_dedup_token:String}": "'verify-user-candidates-v2'",
            "{new_user_changes_dedup_token:String}": "'verify-new-user-changes-v2'",
            "{user_tombstones_dedup_token:String}": "'verify-user-tombstones-v2'",
            "{user_state_maps_dedup_token:String}": "'verify-user-state-maps-v2'",
        }
        elapsed(
            session,
            substitute(
                (ROOT / "sql/13_apply_state_differences.sql").read_text(),
                correction_state_tokens,
            ),
        )

        fixture_manifest_hash = hashlib.sha256(
            (EXPECTED_RAW_SHA256 + "|late-pause-fixture-v1").encode()
        ).hexdigest()
        correction_boundary_sql = substitute(
            (ROOT / "sql/20_publish_boundaries.sql").read_text(),
            {
                "{adjustment_batch_id:UUID}": f"toUUID('{CORRECTION_BATCH_ID}')",
                "{state_revision:UInt64}": "toUInt64(2)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{lease_owner:String}": "'verify-compactor'",
                "{lease_epoch:UInt64}": "toUInt64(2)",
                "{source_snapshot_hash:String}": sql_string(fixture_manifest_hash),
                "{boundary_adjustments_dedup_token:String}": "'verify-boundaries-v2'",
                "{adjustment_ledger_dedup_token:String}": "'verify-adjustment-ledger-v2'",
            },
        )
        elapsed(session, correction_boundary_sql)

        correction_checkpoint_sql = substitute(
            (ROOT / "sql/14_checkpoint_touched_batch.sql").read_text(),
            {
                "{adjustment_batch_id:UUID}": f"toUUID('{CORRECTION_BATCH_ID}')",
                "{state_revision:UInt64}": "toUInt64(2)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{lease_epoch:UInt64}": "toUInt64(2)",
                "{input_manifest_hash:String}": sql_string(fixture_manifest_hash),
                "{dirty_checkpoint_dedup_token:String}": "'verify-dirty-checkpoint-v2'",
                "{processing_checkpoint_dedup_token:String}": "'verify-processing-checkpoint-v2'",
            },
        )
        evidence["late_correction_checkpoint"] = rows(session, correction_checkpoint_sql)

        evidence["late_correction_adjustments"] = rows(
            session,
            f"""
            SELECT
                count() AS rows,
                countIf(entity = 'session') AS session_rows,
                countIf(entity = 'user') AS user_rows,
                sum(delta) AS signed_row_sum,
                uniqExact(adjustment_operation_id) AS unique_operations
            FROM sonyliv.boundary_adjustments
            WHERE adjustment_batch_id = toUUID('{CORRECTION_BATCH_ID}')
            """,
        )[0]

        # Independent whole-source rebuild after the late event.
        full_rebuild_sql = substitute(
            (ROOT / "sql/10_reference_intervals.sql").read_text(),
            {
                "{heartbeat_timeout_ms:UInt64}": f"toUInt64({args.heartbeat_timeout_ms})",
                "{evaluation_as_of:String}": sql_string(args.evaluation_as_of),
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{oracle_run_id:UUID}": f"toUUID('{FULL_REBUILD_ORACLE_ID}')",
                "{full_scan:UInt8}": "toUInt8(1)",
                "{workset_batch_id:UUID}": f"toUUID('{CORRECTION_BATCH_ID}')",
                "{oracle_insert_dedup_token:String}": "'verify-full-rebuild-after-correction-v1'",
                "{source_snapshot_hash:String}": sql_string(fixture_manifest_hash),
                "{oracle_manifest_dedup_token:String}": "'verify-oracle-manifest-v2'",
            },
        )
        elapsed(session, full_rebuild_sql)

        evidence["late_full_oracle_manifest"] = rows(
            session,
            f"""
            SELECT * EXCEPT sealed_at
            FROM sonyliv.oracle_run_manifests
            WHERE oracle_run_id = toUUID('{FULL_REBUILD_ORACLE_ID}')
              AND pipeline_run_id = toUUID('{BATCH_ID}')
              AND policy_version = '{POLICY_VERSION}'
            """,
        )

        convergence = rows(
            session,
            f"""
            WITH
            full_oracle AS
            (
                SELECT sum(dateDiff('millisecond', start_time, end_time)) AS active_ms
                FROM sonyliv.active_intervals_reference
                WHERE oracle_run_id = toUUID('{FULL_REBUILD_ORACLE_ID}')
            ),
            current_states AS
            (
                SELECT
                    s.video_session_id,
                    argMax(s.intervals, s.state_revision) AS intervals
                FROM sonyliv.session_state_versions AS s
                INNER JOIN sonyliv.published_adjustment_batches AS p
                    USING (adjustment_batch_id)
                WHERE s.pipeline_run_id = toUUID('{BATCH_ID}')
                  AND s.policy_version = '{POLICY_VERSION}'
                  AND p.pipeline_run_id = toUUID('{BATCH_ID}')
                  AND p.policy_version = '{POLICY_VERSION}'
                GROUP BY s.video_session_id
            ),
            current_state_total AS
            (
                SELECT sum(
                    arraySum(
                        arrayMap(
                            interval -> dateDiff('millisecond', interval.1, interval.2),
                            intervals
                        )
                    )
                ) AS active_ms
                FROM current_states
            ),
            points AS
            (
                SELECT service_date, boundary_time, sum(delta) AS d
                FROM sonyliv.boundary_adjustments AS a
                INNER JOIN
                (
                    SELECT adjustment_batch_id
                    FROM sonyliv.published_adjustment_batches
                    WHERE pipeline_run_id = toUUID('{BATCH_ID}')
                      AND policy_version = '{POLICY_VERSION}'
                ) AS p USING (adjustment_batch_id)
                WHERE entity = 'session' AND rollup_mask = 0
                GROUP BY service_date, boundary_time
                HAVING d != 0
            ),
            curve AS
            (
                SELECT
                    *,
                    sum(d) OVER
                    (
                        PARTITION BY service_date ORDER BY boundary_time
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS concurrency,
                    leadInFrame(
                        boundary_time,
                        1,
                        toDateTime64(addDays(service_date, 1), 3, 'UTC')
                    ) OVER
                    (
                        PARTITION BY service_date ORDER BY boundary_time
                        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                    ) AS next_time
                FROM points
            ),
            serving_total AS
            (
                SELECT sum(
                    concurrency * dateDiff('millisecond', boundary_time, next_time)
                ) AS active_ms
                FROM curve
                WHERE next_time > boundary_time
            )
            SELECT
                full_oracle.active_ms AS full_oracle_active_ms,
                current_state_total.active_ms AS current_state_active_ms,
                serving_total.active_ms AS serving_active_ms,
                full_oracle.active_ms = current_state_total.active_ms
                    AND full_oracle.active_ms = serving_total.active_ms AS converged
            FROM full_oracle
            CROSS JOIN current_state_total
            CROSS JOIN serving_total
            """,
        )[0]
        if not convergence["converged"]:
            raise RuntimeError(f"late correction did not converge: {convergence}")
        evidence["late_correction_convergence"] = convergence

        snapshot2_sql = substitute(
            (ROOT / "sql/25_seal_delta_snapshot.sql").read_text(),
            {
                "{source_delta_snapshot:UInt128}": "toUInt128(2)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{snapshot_membership_dedup_token:String}": "'verify-snapshot-members-v2'",
                "{snapshot_points_dedup_token:String}": "'verify-snapshot-points-v2'",
                "{delta_snapshot_dedup_token:String}": "'verify-delta-snapshot-v2'",
            },
        )
        elapsed(session, snapshot2_sql)

        cache2_sql = substitute(
            (ROOT / "sql/31_refresh_minute_cache.sql").read_text(),
            {
                "{service_date:Date}": "toDate('2026-07-26')",
                "{entity:String}": "'session'",
                "{rollup_mask:UInt16}": "toUInt16(0)",
                "{generation:UInt64}": "toUInt64(2)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(2)",
                "{generation_dedup_token:String}": "'verify-minute-generation-v2'",
            },
        )
        elapsed(session, cache2_sql)

        validation2_sql = substitute(
            (ROOT / "sql/34_validate_candidate_generation.sql").read_text(),
            {
                "{service_date:Date}": "toDate('2026-07-26')",
                "{entity:String}": "'session'",
                "{rollup_mask:UInt16}": "toUInt16(0)",
                "{generation:UInt64}": "toUInt64(2)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(2)",
                "{sealed_attestation_dedup_token:String}": "'verify-sealed-attestation-v2'",
            },
        )
        evidence["late_generation_parity"] = rows(session, validation2_sql)

        full_validation2_sql = substitute(
            (ROOT / "sql/40_validation.sql").read_text(),
            {
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{service_date:Date}": "toDate('2026-07-26')",
                "{generation:UInt64}": "toUInt64(2)",
                "{oracle_run_id:UUID}": f"toUUID('{FULL_REBUILD_ORACLE_ID}')",
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(2)",
            },
        )
        evidence["late_generation_full_validation"] = rows(
            session, full_validation2_sql
        )

        raw_oracle_validation2_sql = substitute(
            (ROOT / "sql/33_validate_raw_oracle_generation.sql").read_text(),
            {
                "{service_date:Date}": "toDate('2026-07-26')",
                "{entity:String}": "'session'",
                "{rollup_mask:UInt16}": "toUInt16(0)",
                "{generation:UInt64}": "toUInt64(2)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(2)",
                "{oracle_run_id:UUID}": f"toUUID('{FULL_REBUILD_ORACLE_ID}')",
                "{oracle_attestation_dedup_token:String}": "'verify-oracle-attestation-v2'",
            },
        )
        evidence["late_raw_oracle_generation_validation"] = rows(
            session, raw_oracle_validation2_sql
        )

        # Byte-identical attestation retries are one logical attestation. Keep
        # the duplicate physical rows through publication as a positive control.
        session.query(
            f"""
            INSERT INTO sonyliv.generation_validation_attestations
            SELECT *
            FROM sonyliv.generation_validation_attestations
            WHERE service_date = toDate('2026-07-26')
              AND entity = 'session'
              AND rollup_mask = 0
              AND generation = 2
              AND policy_version = '{POLICY_VERSION}'
              AND pipeline_run_id = toUUID('{BATCH_ID}')
              AND source_delta_snapshot = 2
            """
        )
        identical_retry_state = rows(
            session,
            f"""
            SELECT
                validation_source,
                count() AS physical_rows,
                uniqExact(attestation_id) AS logical_attestations
            FROM sonyliv.generation_validation_attestations
            WHERE service_date = toDate('2026-07-26')
              AND entity = 'session'
              AND rollup_mask = 0
              AND generation = 2
              AND policy_version = '{POLICY_VERSION}'
              AND pipeline_run_id = toUUID('{BATCH_ID}')
              AND source_delta_snapshot = 2
            GROUP BY validation_source
            ORDER BY validation_source
            """,
        )
        if len(identical_retry_state) != 2 or any(
            row["physical_rows"] != 2 or row["logical_attestations"] != 1
            for row in identical_retry_state
        ):
            raise RuntimeError(
                f"identical attestation retry was not logically idempotent: {identical_retry_state}"
            )
        evidence["identical_attestation_retry_state"] = identical_retry_state

        publish2_sql = substitute(
            (ROOT / "sql/35_publish_generation.sql").read_text(),
            {
                "{service_date:Date}": "toDate('2026-07-26')",
                "{entity:String}": "'session'",
                "{rollup_mask:UInt16}": "toUInt16(0)",
                "{generation:UInt64}": "toUInt64(2)",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                "{source_delta_snapshot:UInt128}": "toUInt128(2)",
                "{oracle_run_id:UUID}": f"toUUID('{FULL_REBUILD_ORACLE_ID}')",
                "{generation_manifest_dedup_token:String}": "'verify-generation-manifest-v2'",
            },
        )
        evidence["late_published_generation"] = rows(session, publish2_sql)
        evidence["late_generation_hot_hour"] = rows(
            session,
            """
            SELECT
                max(minute_peak) AS peak,
                round(sum(active_entity_ms) / 3600000.0, 6) AS time_weighted_average
            FROM sonyliv.concurrency_minute_versions
            WHERE generation = 2
              AND source_delta_snapshot = 2
              AND entity = 'session'
              AND rollup_mask = 0
              AND minute_start >= toDateTime64('2026-07-26 10:00:00', 3, 'UTC')
              AND minute_start < toDateTime64('2026-07-26 11:00:00', 3, 'UTC')
            """,
        )[0]

        generation1_after = {
            "exact_query_hash": stable_json_hash(rows(session, exact_sql)),
            "dashboard_query_hash": stable_json_hash(
                rows(session, generation1_dashboard_sql)
            ),
            "snapshot": rows(
                session,
                f"""
                SELECT
                    adjustment_batches,
                    adjustment_rows,
                    adjustment_ledger_hash,
                    point_rows,
                    point_hash
                FROM sonyliv.delta_snapshots
                WHERE source_delta_snapshot = 1
                  AND pipeline_run_id = toUUID('{BATCH_ID}')
                  AND policy_version = '{POLICY_VERSION}'
                """,
            )[0],
            "manifest_answer_hash": evidence["published_generation"][-1]["answer_hash"],
            "manifest_minute_rows": evidence["published_generation"][-1]["minute_rows"],
        }
        if generation1_after != generation1_before:
            raise RuntimeError(
                "generation 1 changed after generation 2 correction: "
                f"before={generation1_before}, after={generation1_after}"
            )
        if (
            generation1_after["manifest_answer_hash"]
            == evidence["late_published_generation"][-1]["answer_hash"]
        ):
            raise RuntimeError("late-pause correction did not change the answer hash")
        evidence["generation_1_immutable_after_generation_2"] = {
            "passed": True,
            **generation1_after,
        }

        def clone_and_attest_generation(generation: int) -> None:
            session.query(
                f"""
                INSERT INTO sonyliv.concurrency_minute_versions
                (
                    generation, policy_version, pipeline_run_id,
                    source_delta_snapshot, entity, rollup_mask, service_date,
                    minute_start, platform, country, video_type, content_id,
                    minute_peak, active_entity_ms, ending_concurrency,
                    source_boundary_points
                )
                SELECT
                    toUInt64({generation}), policy_version, pipeline_run_id,
                    source_delta_snapshot, entity, rollup_mask, service_date,
                    minute_start, platform, country, video_type, content_id,
                    minute_peak, active_entity_ms, ending_concurrency,
                    source_boundary_points
                FROM sonyliv.concurrency_minute_versions
                WHERE generation = 2
                  AND source_delta_snapshot = 2
                  AND service_date = toDate('2026-07-26')
                  AND entity = 'session'
                  AND rollup_mask = 0
                """
            )
            sealed_sql = substitute(
                (ROOT / "sql/34_validate_candidate_generation.sql").read_text(),
                {
                    "{service_date:Date}": "toDate('2026-07-26')",
                    "{entity:String}": "'session'",
                    "{rollup_mask:UInt16}": "toUInt16(0)",
                    "{generation:UInt64}": f"toUInt64({generation})",
                    "{policy_version:String}": sql_string(POLICY_VERSION),
                    "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                    "{source_delta_snapshot:UInt128}": "toUInt128(2)",
                    "{sealed_attestation_dedup_token:String}": (
                        f"'verify-adversarial-sealed-{generation}'"
                    ),
                },
            )
            rows(session, sealed_sql)
            raw_sql = substitute(
                (ROOT / "sql/33_validate_raw_oracle_generation.sql").read_text(),
                {
                    "{service_date:Date}": "toDate('2026-07-26')",
                    "{entity:String}": "'session'",
                    "{rollup_mask:UInt16}": "toUInt16(0)",
                    "{generation:UInt64}": f"toUInt64({generation})",
                    "{policy_version:String}": sql_string(POLICY_VERSION),
                    "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                    "{source_delta_snapshot:UInt128}": "toUInt128(2)",
                    "{oracle_run_id:UUID}": f"toUUID('{FULL_REBUILD_ORACLE_ID}')",
                    "{oracle_attestation_dedup_token:String}": (
                        f"'verify-adversarial-oracle-{generation}'"
                    ),
                },
            )
            rows(session, raw_sql)

        def adversarial_publish_sql(generation: int, suffix: str) -> str:
            return substitute(
                (ROOT / "sql/35_publish_generation.sql").read_text(),
                {
                    "{service_date:Date}": "toDate('2026-07-26')",
                    "{entity:String}": "'session'",
                    "{rollup_mask:UInt16}": "toUInt16(0)",
                    "{generation:UInt64}": f"toUInt64({generation})",
                    "{policy_version:String}": sql_string(POLICY_VERSION),
                    "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
                    "{source_delta_snapshot:UInt128}": "toUInt128(2)",
                    "{oracle_run_id:UUID}": f"toUUID('{FULL_REBUILD_ORACLE_ID}')",
                    "{generation_manifest_dedup_token:String}": (
                        f"'verify-adversarial-manifest-{generation}-{suffix}'"
                    ),
                },
            )

        # A second self-consistent sealed attestation is a conflict, even if its
        # own hash is valid. Publication must reject two logical truth claims.
        clone_and_attest_generation(98)
        session.query(
            f"""
            INSERT INTO sonyliv.generation_validation_attestations
            (
                service_date, entity, rollup_mask, generation, policy_version,
                pipeline_run_id, source_delta_snapshot, validation_source,
                oracle_run_id, snapshot_ledger_hash, candidate_answer_hash,
                candidate_minute_rows, expected_answer_hash,
                expected_minute_rows, parent_attestation_id, validator_version,
                attestation_id, validated_at
            )
            SELECT
                service_date, entity, rollup_mask, generation, policy_version,
                pipeline_run_id, source_delta_snapshot, validation_source,
                oracle_run_id, snapshot_ledger_hash, repeat('F', 64),
                candidate_minute_rows, repeat('F', 64), expected_minute_rows,
                parent_attestation_id, validator_version,
                hex(SHA256(concat(
                    toString(service_date), ';', toString(entity), ';',
                    toString(rollup_mask), ';', toString(generation), ';',
                    toString(length(toString(policy_version))), ':',
                    toString(policy_version), toString(pipeline_run_id), ';',
                    toString(source_delta_snapshot), ';', 'sealed_points;',
                    toString(oracle_run_id), ';', snapshot_ledger_hash,
                    repeat('F', 64), ';', toString(candidate_minute_rows), ';',
                    repeat('F', 64), ';', toString(expected_minute_rows), ';',
                    parent_attestation_id, toString(validator_version)
                ))),
                now64(3, 'UTC')
            FROM sonyliv.generation_validation_attestations
            WHERE service_date = toDate('2026-07-26')
              AND entity = 'session'
              AND rollup_mask = 0
              AND generation = 98
              AND policy_version = '{POLICY_VERSION}'
              AND pipeline_run_id = toUUID('{BATCH_ID}')
              AND source_delta_snapshot = 2
              AND validation_source = 'sealed_points'
            LIMIT 1
            """
        )
        conflicting_attestation_rejected = expect_failure(
            session,
            adversarial_publish_sql(98, "conflict"),
            "generation publication integrity gate failed",
        )
        conflict_manifest_rows = rows(
            session,
            """
            SELECT count() AS rows
            FROM sonyliv.serving_generation_manifest
            WHERE generation = 98
            """,
        )[0]["rows"]
        if conflict_manifest_rows != 0:
            raise RuntimeError("conflicting attestation fixture published a manifest")
        evidence["conflicting_attestation_rejected"] = (
            conflicting_attestation_rejected
        )

        # Append a new logical candidate key after both attestations. The
        # authoritative manifest INSERT rehashes current rows and must reject it.
        clone_and_attest_generation(99)
        sentinel_rows = rows(
            session,
            """
            SELECT count() AS rows
            FROM sonyliv.concurrency_minute_versions
            WHERE generation = 99
              AND source_delta_snapshot = 2
              AND content_id = -2147483647
            """,
        )[0]["rows"]
        if sentinel_rows != 0:
            raise RuntimeError("adversarial content sentinel already exists")
        session.query(
            """
            INSERT INTO sonyliv.concurrency_minute_versions
            (
                generation, policy_version, pipeline_run_id,
                source_delta_snapshot, entity, rollup_mask, service_date,
                minute_start, platform, country, video_type, content_id,
                minute_peak, active_entity_ms, ending_concurrency,
                source_boundary_points
            )
            SELECT
                generation, policy_version, pipeline_run_id,
                source_delta_snapshot, entity, rollup_mask, service_date,
                minute_start, platform, country, video_type,
                toInt32(-2147483647), minute_peak + 1, active_entity_ms,
                ending_concurrency, source_boundary_points
            FROM sonyliv.concurrency_minute_versions
            WHERE generation = 99
              AND source_delta_snapshot = 2
              AND service_date = toDate('2026-07-26')
              AND entity = 'session'
              AND rollup_mask = 0
            ORDER BY minute_start
            LIMIT 1
            """
        )
        post_attestation_mutation_rejected = expect_failure(
            session,
            adversarial_publish_sql(99, "post-attestation-mutation"),
            "generation publication integrity gate failed",
        )
        mutation_manifest_rows = rows(
            session,
            """
            SELECT count() AS rows
            FROM sonyliv.serving_generation_manifest
            WHERE generation = 99
            """,
        )[0]["rows"]
        if mutation_manifest_rows != 0:
            raise RuntimeError("post-attestation mutation fixture published a manifest")
        evidence["post_attestation_candidate_mutation_rejected"] = (
            post_attestation_mutation_rejected
        )

        evidence["retry_guards"] = {
            "published_adjustment_batch_rejected": expect_failure(
                session,
                correction_boundary_sql,
                "adjustment_batch_id is already published",
            ),
            "existing_minute_generation_rejected": expect_failure(
                session,
                cache2_sql,
                "generation already has minute rows",
            ),
        }

        dashboard_values = {
            "{service_date:Date}": "toDate('2026-07-26')",
            "{entity:String}": "'session'",
            "{rollup_mask:UInt16}": "toUInt16(0)",
            "{generation:UInt64}": "toUInt64(2)",
            "{policy_version:String}": sql_string(POLICY_VERSION),
            "{pipeline_run_id:UUID}": f"toUUID('{BATCH_ID}')",
            "{source_delta_snapshot:UInt128}": "toUInt128(2)",
            "{range_start:String}": "'2026-07-26 10:00:00.000'",
            "{range_end:String}": "'2026-07-26 11:00:00.000'",
            "{platform_filter:String}": "'*'",
            "{country_filter:String}": "'*'",
            "{video_type_filter:String}": "'*'",
            "{content_id_filter:Int64}": "toInt64(-2147483648)",
        }
        dashboard_sql = substitute(
            (ROOT / "sql/32_dashboard_queries.sql").read_text(), dashboard_values
        )
        dashboard_rows = rows(session, dashboard_sql)
        evidence["dashboard_aligned_range"] = [
            row for row in dashboard_rows if "peak_concurrency" in row
        ][-1]
        partial_values = dict(dashboard_values)
        partial_values["{range_end:String}"] = "'2026-07-26 10:00:30.000'"
        partial_dashboard_sql = substitute(
            (ROOT / "sql/32_dashboard_queries.sql").read_text(), partial_values
        )
        evidence["dashboard_partial_range_routed_to_exact"] = expect_failure(
            session,
            partial_dashboard_sql,
            "minute cache requires a positive minute-aligned range",
        )

    session.close()

    # A replacement interval can start exactly where the prior interval ended.
    # Both correction contributions then have the same final delta (+2 at the
    # shared point), but they must retain distinct operation identities. Exercise
    # the actual publisher in an isolated database so this edge case cannot be
    # masked by the main late-pause fixture.
    with tempfile.TemporaryDirectory(
        prefix="sonyliv-boundary-identity-", dir="/private/tmp"
    ) as fixture_db_path:
        fixture = Session(fixture_db_path)
        fixture.query((ROOT / "sql/00_schema.sql").read_text())
        fixture_pipeline_id = "00000000-0000-0000-0000-000000000201"
        fixture_batch_id = "00000000-0000-0000-0000-000000000202"
        fixture_entity_id = "B" * 64
        fixture.query(
            f"""
            INSERT INTO sonyliv.compaction_worksets
            (
                pipeline_run_id, policy_version, adjustment_batch_id,
                video_session_id, dirty_operation_ids, selected_at,
                lease_owner, lease_epoch, lease_expires_at
            )
            VALUES
            (
                toUUID('{fixture_pipeline_id}'), '{POLICY_VERSION}',
                toUUID('{fixture_batch_id}'), '{fixture_entity_id}', [],
                now64(3, 'UTC'), 'verify-boundary-identity', 1,
                now64(3, 'UTC') + INTERVAL 10 MINUTE
            );

            INSERT INTO sonyliv.entity_interval_changes
            (
                adjustment_batch_id, state_revision, entity, source_entity_id,
                rollup_mask, platform, country, video_type, content_id,
                change_sign, intervals
            )
            VALUES
            (
                toUUID('{fixture_batch_id}'), 1, 'session', '{fixture_entity_id}',
                0, '__all__', '__all__', '__all__', 0, -1,
                [(toDateTime64('2026-07-26 10:00:00', 3, 'UTC'),
                  toDateTime64('2026-07-26 10:30:00', 3, 'UTC'))]
            ),
            (
                toUUID('{fixture_batch_id}'), 1, 'session', '{fixture_entity_id}',
                0, '__all__', '__all__', '__all__', 0, 1,
                [(toDateTime64('2026-07-26 10:30:00', 3, 'UTC'),
                  toDateTime64('2026-07-26 11:00:00', 3, 'UTC'))]
            );
            """
        )
        boundary_identity_sql = substitute(
            (ROOT / "sql/20_publish_boundaries.sql").read_text(),
            {
                "{adjustment_batch_id:UUID}": f"toUUID('{fixture_batch_id}')",
                "{lease_owner:String}": "'verify-boundary-identity'",
                "{lease_epoch:UInt64}": "toUInt64(1)",
                "{state_revision:UInt64}": "toUInt64(1)",
                "{pipeline_run_id:UUID}": f"toUUID('{fixture_pipeline_id}')",
                "{policy_version:String}": sql_string(POLICY_VERSION),
                "{boundary_adjustments_dedup_token:String}": "'verify-boundary-identity-points'",
                "{source_snapshot_hash:String}": sql_string(EXPECTED_RAW_SHA256),
                "{adjustment_ledger_dedup_token:String}": "'verify-boundary-identity-ledger'",
            },
        )
        fixture.query(boundary_identity_sql)
        boundary_identity = rows(
            fixture,
            f"""
            SELECT
                count() AS adjustment_rows,
                uniqExact(adjustment_operation_id) AS unique_operation_ids,
                sum(delta) AS signed_row_sum,
                countIf(
                    boundary_time = toDateTime64(
                        '2026-07-26 10:30:00', 3, 'UTC'
                    )
                ) AS shared_boundary_rows,
                sumIf(
                    delta,
                    boundary_time = toDateTime64(
                        '2026-07-26 10:30:00', 3, 'UTC'
                    )
                ) AS shared_boundary_delta,
                (
                    SELECT count()
                    FROM sonyliv.published_adjustment_batches
                    WHERE adjustment_batch_id = toUUID('{fixture_batch_id}')
                ) AS published_ledger_rows
            FROM sonyliv.boundary_adjustments
            WHERE adjustment_batch_id = toUUID('{fixture_batch_id}')
            """,
        )[0]
        expected_boundary_identity = {
            "adjustment_rows": 4,
            "unique_operation_ids": 4,
            "signed_row_sum": 0,
            "shared_boundary_rows": 2,
            "shared_boundary_delta": 2,
            "published_ledger_rows": 1,
        }
        if boundary_identity != expected_boundary_identity:
            raise RuntimeError(
                "boundary operation identity fixture failed: "
                f"actual={boundary_identity}, expected={expected_boundary_identity}"
            )
        evidence["boundary_operation_identity"] = boundary_identity

    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
