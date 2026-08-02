#!/usr/bin/env python3
"""Environment-only analytics runner for LibreChat Code Interpreter.

The only per-call input is ATLYS_REQUEST_B64. The script never writes local files;
substantive artifacts are appended to ClickHouse and stdout contains one bounded JSON
response.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

ARTIFACT_TABLE = "atlys_agent.artifacts"
BUSINESS_CONTEXT_TABLE = "agent.business_logic_embeddings_v1"
MAX_REQUEST_BYTES = 1_000_000
MAX_RESULT_ROWS = 500
MAX_CONTEXT_BYTES = 5_000_000
MAX_PREVIEW_ROWS = 20
MAX_TEXT_CHUNK = 50_000
MAX_ARTIFACT_BYTES = 5_000_000

QUERY_SETTINGS: dict[str, Any] = {
    "readonly": 1,
    "max_execution_time": 30,
    "max_rows_to_read": 100_000_000,
    "max_bytes_to_read": 10_000_000_000,
    "max_result_rows": MAX_RESULT_ROWS,
    "result_overflow_mode": "throw",
}

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_QUALIFIED_TABLE = re.compile(
    r"^(?P<database>[A-Za-z_][A-Za-z0-9_]*)\."
    r"(?P<table>[A-Za-z_][A-Za-z0-9_]*)$"
)
_SAFE_AGGREGATE = re.compile(
    r"\b(?:count(?:if)?|uniq[a-z0-9_]*|sum(?:if)?|avg(?:if)?|"
    r"min|max|quantile[a-z0-9_]*|median[a-z0-9_]*|"
    r"var[a-z0-9_]*|stddev[a-z0-9_]*|covar[a-z0-9_]*|corr)\s*\(",
    re.IGNORECASE,
)
_UNSAFE_AGGREGATE = re.compile(
    r"\b(?:any(?:last|heavy)?|argmin|argmax|grouparray|"
    r"groupuniqarray|groupconcat|topk)\s*\(",
    re.IGNORECASE,
)
_FORBIDDEN_SQL = re.compile(
    r"\b(?:insert|update|delete|drop|alter|create|truncate|attach|detach|"
    r"optimize|rename|grant|revoke|kill|system)\b",
    re.IGNORECASE,
)
_DEFAULT_BOUNDARY_COLUMNS = (
    "run_id",
    "event_time",
    "timestamp",
    "event_date",
    "created_at",
    "day",
    "date",
)


class RunnerError(Exception):
    """Expected, safe-to-report runner failure."""

    def __init__(self, code: str, message: str, *, status: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def _require_string(
    payload: dict[str, Any], key: str, *, allow_empty: bool = False
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise RunnerError("invalid_request", f"{key} must be a non-empty string")
    return value


def _require_uuid(payload: dict[str, Any], key: str) -> str:
    value = _require_string(payload, key)
    try:
        return str(UUID(value))
    except ValueError as error:
        raise RunnerError("invalid_request", f"{key} must be a UUID") from error


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date, UUID, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, dict):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(child) for child in value]
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"))


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def decode_request(encoded: str | None = None) -> dict[str, Any]:
    raw = encoded if encoded is not None else os.environ.get("ATLYS_REQUEST_B64")
    if not raw:
        raise RunnerError("missing_request", "ATLYS_REQUEST_B64 is required")
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as error:
        raise RunnerError(
            "invalid_request", "ATLYS_REQUEST_B64 is not valid base64"
        ) from error
    if len(decoded) > MAX_REQUEST_BYTES:
        raise RunnerError(
            "request_too_large", "decoded request exceeds 1,000,000 bytes"
        )
    try:
        payload = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunnerError(
            "invalid_request", "decoded request is not valid UTF-8 JSON"
        ) from error
    if not isinstance(payload, dict):
        raise RunnerError("invalid_request", "request must decode to one JSON object")
    return payload


def load_business_context(client: Any) -> tuple[str, dict[str, Any]]:
    """Load one current, published business-context version from ClickHouse."""

    try:
        selected = client.query(
            "SELECT toString(context_id) AS context_id, version_number, "
            "count() AS chunk_count, max(valid_from) AS latest_valid_from "
            f"FROM {BUSINESS_CONTEXT_TABLE} "
            "WHERE status = 'published' AND valid_to IS NULL "
            "GROUP BY context_id, version_number "
            "ORDER BY latest_valid_from DESC, version_number DESC, context_id DESC LIMIT 1",
            settings=QUERY_SETTINGS,
        )
    except Exception as error:
        raise RunnerError(
            "missing_context",
            f"business context lookup failed ({type(error).__name__})",
            status="missing_context",
        ) from error
    if not selected.result_rows:
        raise RunnerError(
            "missing_context",
            f"{BUSINESS_CONTEXT_TABLE} has no current published context",
            status="missing_context",
        )

    context_id, version_number, chunk_count, _ = selected.result_rows[0]
    if not 1 <= int(chunk_count) <= MAX_RESULT_ROWS:
        raise RunnerError(
            "missing_context",
            f"selected business context must contain 1 to {MAX_RESULT_ROWS} chunks",
            status="missing_context",
        )
    try:
        chunks = client.query(
            "SELECT toString(chunk_id) AS chunk_id, chunk_ordinal, section_type, "
            "entity_type, entity_id, confidence, "
            "toString(content_sha256) AS content_sha256, chunk_text, "
            "metadata_json "
            f"FROM {BUSINESS_CONTEXT_TABLE} "
            "WHERE context_id = {context_id:UUID} "
            "AND version_number = {version_number:UInt64} "
            "AND status = 'published' AND valid_to IS NULL "
            f"ORDER BY chunk_ordinal, chunk_id LIMIT {MAX_RESULT_ROWS}",
            parameters={
                "context_id": str(context_id),
                "version_number": int(version_number),
            },
            settings=QUERY_SETTINGS,
        )
    except Exception as error:
        raise RunnerError(
            "missing_context",
            f"business context read failed ({type(error).__name__})",
            status="missing_context",
        ) from error
    if not chunks.result_rows:
        raise RunnerError(
            "missing_context",
            "selected business context contains no readable chunks",
            status="missing_context",
        )
    if len(chunks.result_rows) != int(chunk_count):
        raise RunnerError(
            "missing_context",
            "selected business context chunk count changed during snapshot read",
            status="missing_context",
        )

    rows = _named_rows(chunks)
    ordinals = [row["chunk_ordinal"] for row in rows]
    if len(ordinals) != len(set(ordinals)):
        raise RunnerError(
            "missing_context",
            "selected business context has duplicate chunk ordinals",
            status="missing_context",
        )
    content = "\n\n".join(str(row["chunk_text"]) for row in rows).strip()
    if not content:
        raise RunnerError(
            "missing_context",
            "selected business context contains no non-empty text",
            status="missing_context",
        )
    if len(content.encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise RunnerError(
            "missing_context",
            "selected business context exceeds 5,000,000 bytes",
            status="missing_context",
        )
    provenance = {
        "source_table": BUSINESS_CONTEXT_TABLE,
        "context_id": str(context_id),
        "version_number": int(version_number),
        "chunk_count": len(rows),
        "chunk_ids": [row["chunk_id"] for row in rows],
        "chunk_content_sha256": [row["content_sha256"] for row in rows],
    }
    return content, provenance


def _connection_config() -> dict[str, Any]:
    required = ("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RunnerError(
            "connection_unavailable", "ClickHouse credentials are not configured"
        )

    host_value = os.environ["CLICKHOUSE_HOST"].strip()
    secure = os.environ.get("CLICKHOUSE_SECURE", "true").casefold() in {
        "1",
        "true",
        "yes",
    }
    port_value = os.environ.get("CLICKHOUSE_PORT", "8443")
    if "://" in host_value:
        parsed = urlsplit(host_value)
        if not parsed.hostname:
            raise RunnerError("connection_unavailable", "CLICKHOUSE_HOST is invalid")
        host_value = parsed.hostname
        if parsed.port:
            port_value = str(parsed.port)
        secure = parsed.scheme.casefold() == "https"
    try:
        port = int(port_value)
    except ValueError as error:
        raise RunnerError(
            "connection_unavailable", "CLICKHOUSE_PORT must be an integer"
        ) from error

    return {
        "host": host_value,
        "port": port,
        "username": os.environ["CLICKHOUSE_USER"],
        "password": os.environ["CLICKHOUSE_PASSWORD"],
        "secure": secure,
        "verify": os.environ.get("CLICKHOUSE_VERIFY", "true").casefold()
        in {"1", "true", "yes"},
        "connect_timeout": 10,
        "send_receive_timeout": 30,
    }


def create_client() -> Any:
    try:
        import clickhouse_connect
    except ImportError as error:
        raise RunnerError(
            "dependency_unavailable",
            "clickhouse-connect must be preinstalled in the Code Interpreter image",
        ) from error
    try:
        return clickhouse_connect.get_client(**_connection_config())
    except RunnerError:
        raise
    except Exception as error:
        raise RunnerError(
            "connection_unavailable",
            f"ClickHouse connection failed ({type(error).__name__})",
        ) from error


def _insert_artifact(
    client: Any,
    *,
    run_id: str,
    feature_slug: str,
    question_id: str = "",
    artifact_type: str,
    source_scope: str = "none",
    content_format: str,
    content: str,
    row_count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> str:
    encoded_size = len(content.encode("utf-8"))
    if encoded_size > MAX_ARTIFACT_BYTES:
        raise RunnerError("artifact_too_large", "artifact exceeds 5,000,000 bytes")
    artifact_id = str(uuid4())
    row = [
        artifact_id,
        run_id,
        feature_slug,
        question_id,
        artifact_type,
        source_scope,
        content_format,
        row_count,
        content,
        _canonical_json(metadata or {}),
        _content_hash(content),
    ]
    try:
        client.insert(
            ARTIFACT_TABLE,
            [row],
            column_names=[
                "artifact_id",
                "run_id",
                "feature_slug",
                "question_id",
                "artifact_type",
                "source_scope",
                "content_format",
                "row_count",
                "content",
                "metadata_json",
                "content_hash",
            ],
        )
    except Exception as error:
        raise RunnerError(
            "artifact_write_failed",
            f"ClickHouse artifact insert failed ({type(error).__name__})",
        ) from error
    return artifact_id


def _question_ids(coverage_ledger: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for index, question in enumerate(coverage_ledger):
        value = question.get("question_id") or question.get("id")
        result.append(str(value) if value else f"question_{index + 1}")
    return result


def _qualified_name(value: Any, field: str) -> tuple[str, str]:
    if not isinstance(value, str):
        raise RunnerError("invalid_request", f"{field} must be database.table")
    match = _QUALIFIED_TABLE.fullmatch(value)
    if match is None:
        raise RunnerError("invalid_request", f"{field} must be database.table")
    return match.group("database"), match.group("table")


def _validate_instrumentation_handoff(value: Any) -> dict[str, Any]:
    """Validate the name-based Instrumentation Agent handoff."""

    if not isinstance(value, dict):
        raise RunnerError("invalid_request", "instrumentation_handoff must be an object")
    if value.get("status") != "completed":
        raise RunnerError(
            "invalid_request", "instrumentation_handoff.status must be completed"
        )
    _require_string(value, "spec_md")
    event_tables = value.get("event_tables")
    tables = value.get("tables")
    if not isinstance(event_tables, dict) or not event_tables:
        raise RunnerError(
            "invalid_request", "instrumentation_handoff.event_tables must be non-empty"
        )
    if not isinstance(tables, list) or not tables:
        raise RunnerError(
            "invalid_request", "instrumentation_handoff.tables must be non-empty"
        )
    for key in ("materialized_views", "aggregations", "decision_trace", "warnings"):
        if key in value and not isinstance(value[key], list):
            raise RunnerError(
                "invalid_request", f"instrumentation_handoff.{key} must be a list"
            )

    declared_tables: list[str] = []
    for index, entry in enumerate(tables):
        if not isinstance(entry, dict):
            raise RunnerError(
                "invalid_request", "instrumentation_handoff.tables entries must be objects"
            )
        database, table = _qualified_name(entry.get("name"), f"tables[{index}].name")
        declared_tables.append(f"{database}.{table}")
    if len(declared_tables) != len(set(declared_tables)):
        raise RunnerError("invalid_request", "instrumentation_handoff.tables has duplicates")

    raw_event_tables: list[str] = []
    for event_name, table_name in event_tables.items():
        if not isinstance(event_name, str) or not event_name.strip():
            raise RunnerError(
                "invalid_request", "instrumentation_handoff.event_tables has an invalid event"
            )
        database, table = _qualified_name(table_name, f"event_tables[{event_name!r}]")
        raw_event_tables.append(f"{database}.{table}")
    raw_event_tables = list(dict.fromkeys(raw_event_tables))
    outside = sorted(set(raw_event_tables) - set(declared_tables))
    if outside:
        raise RunnerError(
            "invalid_request",
            f"event_tables references tables absent from tables: {outside}",
        )

    declared_views: list[str] = []
    for index, entry in enumerate(value.get("materialized_views", [])):
        if not isinstance(entry, dict):
            raise RunnerError(
                "invalid_request",
                "instrumentation_handoff.materialized_views entries must be objects",
            )
        database, table = _qualified_name(
            entry.get("name"), f"materialized_views[{index}].name"
        )
        declared_views.append(f"{database}.{table}")
        if "target_table" in entry:
            target_database, target_table = _qualified_name(
                entry.get("target_table"), f"materialized_views[{index}].target_table"
            )
            target = f"{target_database}.{target_table}"
            if target not in declared_tables:
                raise RunnerError(
                    "invalid_request",
                    f"materialized view target is absent from tables: {target}",
                )
    if len(declared_views) != len(set(declared_views)):
        raise RunnerError(
            "invalid_request", "instrumentation_handoff.materialized_views has duplicates"
        )
    overlap = sorted(set(declared_tables) & set(declared_views))
    if overlap:
        raise RunnerError(
            "invalid_request", f"objects cannot be both tables and materialized views: {overlap}"
        )

    return {
        "handoff": value,
        "declared_tables": declared_tables,
        "raw_event_tables": raw_event_tables,
        "declared_views": declared_views,
    }


def _resolve_handoff_catalog(
    client: Any,
    declared_tables: list[str],
    raw_event_tables: list[str],
    declared_views: list[str],
) -> list[dict[str, Any]]:
    names = declared_tables + declared_views
    predicate = " OR ".join(
        f"(database = '{database}' AND name = '{table}')"
        for database, table in (_qualified_name(name, "declared object") for name in names)
    )
    try:
        result = client.query(
            "SELECT database, name, engine, total_rows, create_table_query "
            f"FROM system.tables WHERE ({predicate}) ORDER BY database, name LIMIT 200",
            settings=QUERY_SETTINGS,
        )
    except Exception as error:
        raise RunnerError(
            "preflight_failed",
            f"declared-object lookup failed ({type(error).__name__})",
        ) from error
    rows = _named_rows(result)
    by_name = {f"{row['database']}.{row['name']}": row for row in rows}
    missing = sorted(set(names) - set(by_name))
    if missing:
        raise RunnerError("preflight_failed", f"declared objects were not found: {missing}")
    wrong_views = sorted(
        name for name in declared_views if by_name[name].get("engine") != "MaterializedView"
    )
    wrong_tables = sorted(
        name for name in declared_tables if by_name[name].get("engine") == "MaterializedView"
    )
    if wrong_views or wrong_tables:
        raise RunnerError(
            "preflight_failed",
            "declared object kinds do not match live engines; "
            f"views={wrong_views}, tables={wrong_tables}",
        )
    empty_raw = sorted(
        name for name in raw_event_tables if int(by_name[name].get("total_rows") or 0) < 1
    )
    if empty_raw:
        raise RunnerError(
            "preflight_failed", f"declared raw event tables contain no data: {empty_raw}"
        )
    missing_ddl = sorted(name for name in names if not by_name[name].get("create_table_query"))
    if missing_ddl:
        raise RunnerError(
            "preflight_failed", f"ClickHouse returned no live DDL for: {missing_ddl}"
        )
    return rows


def action_bootstrap(client: Any, request: dict[str, Any]) -> dict[str, Any]:
    run_id = _require_uuid(request, "run_id")
    feature_slug = _require_string(request, "feature_slug")
    validated_handoff = _validate_instrumentation_handoff(
        request.get("instrumentation_handoff")
    )
    handoff = validated_handoff["handoff"]
    feature_spec = handoff["spec_md"]
    coverage_ledger = request.get("coverage_ledger", [])
    if not isinstance(coverage_ledger, list) or not all(
        isinstance(entry, dict) for entry in coverage_ledger
    ):
        raise RunnerError(
            "invalid_request", "coverage_ledger must be a list of objects"
        )

    catalog = _resolve_handoff_catalog(
        client,
        validated_handoff["declared_tables"],
        validated_handoff["raw_event_tables"],
        validated_handoff["declared_views"],
    )
    context, context_provenance = load_business_context(client)
    context_hash = _content_hash(context)
    spec_id = _insert_artifact(
        client,
        run_id=run_id,
        feature_slug=feature_slug,
        artifact_type="feature_spec",
        content_format="markdown",
        content=feature_spec,
    )
    handoff_id = _insert_artifact(
        client,
        run_id=run_id,
        feature_slug=feature_slug,
        artifact_type="instrumentation_handoff",
        content_format="json",
        content=_canonical_json(handoff),
    )
    ddl_artifact_ids = []
    for row in catalog:
        ddl_artifact_ids.append(
            _insert_artifact(
                client,
                run_id=run_id,
                feature_slug=feature_slug,
                artifact_type="instrumentation_ddl",
                source_scope="feature",
                content_format="sql",
                content=str(row["create_table_query"]),
                metadata={
                    "database": row["database"],
                    "table": row["name"],
                    "engine": row["engine"],
                    "source": "live_system_tables",
                },
            )
        )
    context_id = _insert_artifact(
        client,
        run_id=run_id,
        feature_slug=feature_slug,
        artifact_type="context_snapshot",
        content_format="markdown",
        content=context,
        metadata={**context_provenance, "context_hash": context_hash},
    )
    manifest = {
        "run_id": run_id,
        "feature_slug": feature_slug,
        "context_hash": context_hash,
        "question_ids": _question_ids(coverage_ledger),
        "coverage_ledger": coverage_ledger,
        "feature_tables": validated_handoff["declared_tables"],
        "raw_event_tables": validated_handoff["raw_event_tables"],
        "materialized_views": validated_handoff["declared_views"],
        "event_tables": handoff["event_tables"],
        "handoff_warnings": handoff.get("warnings", []),
        "context_source": context_provenance,
        "artifact_ids": {
            "feature_spec": spec_id,
            "instrumentation_handoff": handoff_id,
            "instrumentation_ddl": ddl_artifact_ids,
            "context_snapshot": context_id,
        },
        "raw_rows_to_llm": 0,
    }
    manifest_id = _insert_artifact(
        client,
        run_id=run_id,
        feature_slug=feature_slug,
        artifact_type="manifest",
        content_format="json",
        content=_canonical_json(manifest),
    )
    context_inline = len(context) <= MAX_TEXT_CHUNK
    return {
        "ok": True,
        "run_id": run_id,
        "feature_slug": feature_slug,
        "feature_spec": feature_spec,
        "feature_tables": manifest["feature_tables"],
        "raw_event_tables": manifest["raw_event_tables"],
        "materialized_views": manifest["materialized_views"],
        "event_tables": manifest["event_tables"],
        "handoff_warnings": manifest["handoff_warnings"],
        "context_hash": context_hash,
        "context_source": context_provenance,
        "context": context if context_inline else None,
        "context_length": len(context),
        "context_requires_pagination": not context_inline,
        "artifact_ids": {
            **manifest["artifact_ids"],
            "manifest": manifest_id,
        },
        "raw_rows_to_llm": 0,
    }


def _validated_tables(
    request: dict[str, Any], key: str = "tables"
) -> list[tuple[str, str]]:
    values = request.get(key)
    if not isinstance(values, list) or not values:
        raise RunnerError("invalid_request", f"{key} must be a non-empty list")
    result: list[tuple[str, str]] = []
    for value in values:
        if isinstance(value, dict):
            database = value.get("database")
            table = value.get("table")
        elif isinstance(value, str):
            match = _QUALIFIED_TABLE.fullmatch(value)
            database = match.group("database") if match else None
            table = match.group("table") if match else None
        else:
            database = table = None
        if not isinstance(database, str) or not isinstance(table, str):
            raise RunnerError(
                "invalid_request", f"{key} entries must identify database.table"
            )
        if not _IDENTIFIER.fullmatch(database) or not _IDENTIFIER.fullmatch(table):
            raise RunnerError("invalid_request", f"{key} contains an unsafe identifier")
        result.append((database, table))
    return list(dict.fromkeys(result))


def _named_rows(result: Any) -> list[dict[str, Any]]:
    columns = [str(name) for name in result.column_names]
    return [
        {column: _json_safe(value) for column, value in zip(columns, row, strict=True)}
        for row in result.result_rows
    ]


def action_discover(client: Any, request: dict[str, Any]) -> dict[str, Any]:
    run_id = _require_uuid(request, "run_id")
    feature_slug = _require_string(request, "feature_slug")
    tables = _validated_tables(request)
    predicate = " OR ".join(
        f"(database = '{database}' AND name = '{table}')" for database, table in tables
    )
    column_predicate = " OR ".join(
        f"(database = '{database}' AND table = '{table}')" for database, table in tables
    )
    try:
        table_result = client.query(
            "SELECT database, name, engine, sorting_key, primary_key, partition_key, "
            "sampling_key, total_rows, total_bytes, comment, create_table_query "
            "FROM system.tables WHERE "
            f"({predicate}) ORDER BY database, name LIMIT 500",
            settings=QUERY_SETTINGS,
        )
        column_result = client.query(
            "SELECT database, table, name, type, comment, position, default_kind, "
            "default_expression, compression_codec AS codec_expression, "
            "'' AS ttl_expression "
            "FROM system.columns WHERE "
            f"({column_predicate}) ORDER BY database, table, position LIMIT 500",
            settings=QUERY_SETTINGS,
        )
        index_result = client.query(
            "SELECT database, table, name, type_full, expr, granularity "
            "FROM system.data_skipping_indices WHERE "
            f"({column_predicate}) ORDER BY database, table, name LIMIT 500",
            settings=QUERY_SETTINGS,
        )
    except Exception as error:
        raise RunnerError(
            "discovery_failed",
            f"ClickHouse schema discovery failed ({type(error).__name__})",
        ) from error
    table_rows = _named_rows(table_result)
    column_rows = _named_rows(column_result)
    index_rows = _named_rows(index_result)
    found = {(row["database"], row["name"]) for row in table_rows}
    missing = [
        f"{database}.{table}"
        for database, table in tables
        if (database, table) not in found
    ]
    if missing:
        raise RunnerError(
            "discovery_failed", f"declared tables were not found: {missing}"
        )
    schema = {
        "tables": table_rows,
        "columns": column_rows,
        "skipping_indices": index_rows,
    }
    artifact_id = _insert_artifact(
        client,
        run_id=run_id,
        feature_slug=feature_slug,
        artifact_type="schema",
        content_format="json",
        content=_canonical_json(schema),
        row_count=len(column_rows),
        metadata={
            "declared_tables": [f"{database}.{table}" for database, table in tables]
        },
    )
    return {
        "ok": True,
        "artifact_ids": [artifact_id],
        "table_count": len(table_rows),
        "column_count": len(column_rows),
        "skipping_index_count": len(index_rows),
        "schema": schema,
        "raw_rows_to_llm": 0,
    }


def _mask_literals_and_comments(sql: str) -> str:
    output: list[str] = []
    index = 0
    state = "normal"
    while index < len(sql):
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < len(sql) else ""
        if state == "normal":
            if char == "'":
                state = "single"
                output.append(" ")
            elif char == "-" and nxt == "-":
                state = "line_comment"
                output.extend("  ")
                index += 1
            elif char == "/" and nxt == "*":
                state = "block_comment"
                output.extend("  ")
                index += 1
            else:
                output.append(char)
        elif state == "single":
            output.append("\n" if char == "\n" else " ")
            if char == "'":
                if nxt == "'":
                    output.append(" ")
                    index += 1
                else:
                    state = "normal"
        elif state == "line_comment":
            output.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "normal"
        else:
            output.append(" ")
            if char == "*" and nxt == "/":
                output.append(" ")
                index += 1
                state = "normal"
        index += 1
    if state in {"single", "block_comment"}:
        raise RunnerError(
            "unsafe_query", "SQL contains an unterminated literal or comment"
        )
    return "".join(output)


def _sql_tables(masked_sql: str) -> tuple[set[str], list[str]]:
    cte_names = {
        match.group(1).casefold()
        for match in re.finditer(
            r"(?:\bwith\b|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+as\s*\(",
            masked_sql,
            flags=re.IGNORECASE,
        )
    }
    physical: set[str] = set()
    invalid: list[str] = []
    for match in re.finditer(r"\b(?:from|join)\b", masked_sql, flags=re.IGNORECASE):
        remainder = masked_sql[match.end() :].lstrip()
        if remainder.startswith("("):
            continue
        token_match = re.match(r"([`\"A-Za-z_][`\"A-Za-z0-9_.]*)", remainder)
        if token_match is None:
            invalid.append("<computed-source>")
            continue
        token = token_match.group(1).replace("`", "").replace('"', "")
        if "." not in token:
            if token.casefold() not in cte_names:
                invalid.append(token)
            continue
        if _QUALIFIED_TABLE.fullmatch(token) is None:
            invalid.append(token)
            continue
        physical.add(token.casefold())
    return physical, invalid


def validate_aggregate_sql(sql: str, request: dict[str, Any]) -> set[str]:
    if not isinstance(sql, str) or not sql.strip():
        raise RunnerError("unsafe_query", "sql must be a non-empty string")
    masked = _mask_literals_and_comments(sql)
    stripped = masked.strip()
    if not re.match(r"^(?:select|with)\b", stripped, flags=re.IGNORECASE):
        raise RunnerError("unsafe_query", "only SELECT or WITH ... SELECT is allowed")
    semicolons = [index for index, char in enumerate(masked) if char == ";"]
    if semicolons and (len(semicolons) > 1 or masked[semicolons[0] + 1 :].strip()):
        raise RunnerError("unsafe_query", "exactly one SQL statement is allowed")
    if _FORBIDDEN_SQL.search(masked):
        raise RunnerError("unsafe_query", "mutating or administrative SQL is forbidden")
    if re.search(
        r"\bselect\s+(?:distinct\s+)?(?:[A-Za-z_][A-Za-z0-9_]*\.)?\*",
        masked,
        flags=re.IGNORECASE,
    ) or re.search(r",\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)?\*", masked):
        raise RunnerError("unsafe_query", "SELECT * and table.* are forbidden")
    if _UNSAFE_AGGREGATE.search(masked):
        raise RunnerError(
            "unsafe_query", "row-sampling or array-producing aggregates are forbidden"
        )
    if _SAFE_AGGREGATE.search(masked) is None:
        raise RunnerError(
            "unsafe_query", "analytical SQL must return aggregate evidence"
        )

    physical_tables, invalid_sources = _sql_tables(masked)
    if invalid_sources or not physical_tables:
        raise RunnerError(
            "unsafe_query", "all physical tables must be database-qualified"
        )
    allowed_tables = {
        f"{database}.{table}".casefold()
        for database, table in _validated_tables(request, "allowed_tables")
    }
    outside = sorted(physical_tables - allowed_tables)
    if outside:
        raise RunnerError(
            "unsafe_query", f"query references tables outside the allowlist: {outside}"
        )
    table_scopes = request.get("table_scopes")
    if not isinstance(table_scopes, dict):
        raise RunnerError(
            "invalid_request",
            "table_scopes must map every allowed database.table to its source scope",
        )
    normalized_scopes = {
        str(table).casefold(): scope for table, scope in table_scopes.items()
    }
    missing_scopes = sorted(physical_tables - set(normalized_scopes))
    if missing_scopes:
        raise RunnerError(
            "invalid_request", f"table_scopes lacks queried tables: {missing_scopes}"
        )
    source_scope = _require_string(request, "source_scope")
    mismatched = sorted(
        table
        for table in physical_tables
        if normalized_scopes.get(table) not in {"feature", "legacy"}
        or normalized_scopes.get(table) != source_scope
    )
    if mismatched:
        raise RunnerError(
            "unsafe_query",
            "feature and legacy sources must be queried separately; source scope mismatch for "
            f"{mismatched}",
        )

    if not re.search(r"\b(?:where|prewhere)\b", masked, flags=re.IGNORECASE):
        raise RunnerError(
            "unsafe_query", "analytical SQL requires a WHERE or PREWHERE boundary"
        )
    boundary_values = request.get("boundary_columns", list(_DEFAULT_BOUNDARY_COLUMNS))
    if not isinstance(boundary_values, list) or not all(
        isinstance(value, str) and _IDENTIFIER.fullmatch(value)
        for value in boundary_values
    ):
        raise RunnerError(
            "invalid_request", "boundary_columns must be a list of identifiers"
        )
    boundary_clause = re.compile(
        r"\b(?:where|prewhere)\b"
        r"(?:(?!\b(?:group\s+by|order\s+by|having|limit|settings|format|union)\b).)*?"
        rf"\b(?:{'|'.join(map(re.escape, boundary_values))})\b",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if boundary_clause.search(masked) is None:
        raise RunnerError("unsafe_query", "query lacks a declared run or time boundary")
    if request.get("require_canonical_run"):
        canonical_run = _require_string(request, "canonical_run_id")
        if canonical_run.casefold() not in sql.casefold():
            raise RunnerError("unsafe_query", "query does not use the canonical run ID")

    limits = [
        int(value) for value in re.findall(r"\blimit\s+(\d+)\b", masked, re.IGNORECASE)
    ]
    maximum = request.get("max_result_rows", MAX_RESULT_ROWS)
    if not isinstance(maximum, int) or not 1 <= maximum <= MAX_RESULT_ROWS:
        raise RunnerError(
            "invalid_request", "max_result_rows must be between 1 and 500"
        )
    if not limits or limits[-1] < 1 or limits[-1] > maximum:
        raise RunnerError(
            "unsafe_query", f"final LIMIT must be between 1 and {maximum}"
        )
    return physical_tables


def _assert_discovered(client: Any, run_id: str, physical_tables: set[str]) -> None:
    try:
        result = client.query(
            "SELECT content FROM atlys_agent.artifacts "
            "WHERE run_id = {run_id:UUID} AND artifact_type = 'schema' "
            "ORDER BY created_at DESC, artifact_id DESC LIMIT 100",
            parameters={"run_id": UUID(run_id)},
            settings={**QUERY_SETTINGS, "max_result_rows": 100},
        )
    except Exception as error:
        raise RunnerError(
            "discovery_failed",
            f"schema artifact verification failed ({type(error).__name__})",
        ) from error
    discovered: set[str] = set()
    for row in result.result_rows:
        try:
            schema = json.loads(str(row[0]))
        except (json.JSONDecodeError, TypeError, IndexError):
            continue
        tables = schema.get("tables", []) if isinstance(schema, dict) else []
        for table in tables:
            if (
                isinstance(table, dict)
                and isinstance(table.get("database"), str)
                and isinstance(table.get("name"), str)
            ):
                discovered.add(f"{table['database']}.{table['name']}".casefold())
    missing = sorted(physical_tables - discovered)
    if missing:
        raise RunnerError(
            "discovery_required",
            f"discover must precede query for these tables: {missing}",
        )


def _result_to_csv(columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows([[_json_safe(value) for value in row] for row in rows])
    return stream.getvalue()


def action_query(client: Any, request: dict[str, Any]) -> dict[str, Any]:
    run_id = _require_uuid(request, "run_id")
    feature_slug = _require_string(request, "feature_slug")
    question_id = _require_string(request, "question_id")
    source_scope = _require_string(request, "source_scope")
    if source_scope not in {"feature", "legacy"}:
        raise RunnerError("invalid_request", "source_scope must be feature or legacy")
    sql = _require_string(request, "sql")
    physical_tables = validate_aggregate_sql(sql, request)
    _assert_discovered(client, run_id, physical_tables)
    try:
        result = client.query(
            sql.rstrip().removesuffix(";").rstrip(), settings=QUERY_SETTINGS
        )
    except Exception as error:
        raise RunnerError(
            "query_failed",
            f"ClickHouse aggregate query failed ({type(error).__name__})",
            status="query_failure",
        ) from error
    columns = [str(name) for name in result.column_names]
    rows = [tuple(row) for row in result.result_rows]
    if len(rows) > request.get("max_result_rows", MAX_RESULT_ROWS):
        raise RunnerError("unsafe_result", "ClickHouse returned more rows than allowed")
    if len(columns) != len(set(columns)) or any(
        len(row) != len(columns) for row in rows
    ):
        raise RunnerError("unsafe_result", "ClickHouse returned a malformed result")
    protected_values = request.get("protected_columns", [])
    if not isinstance(protected_values, list) or not all(
        isinstance(value, str) for value in protected_values
    ):
        raise RunnerError(
            "invalid_request", "protected_columns must be a list of strings"
        )
    normalize = lambda value: value.replace("_", "").casefold()
    protected = {normalize(value) for value in protected_values}
    exposed = sorted(column for column in columns if normalize(column) in protected)
    if exposed:
        raise RunnerError(
            "unsafe_result", f"result exposes protected columns: {exposed}"
        )
    expected = request.get("expected_columns", [])
    if expected:
        if not isinstance(expected, list) or not all(
            isinstance(value, str) for value in expected
        ):
            raise RunnerError(
                "invalid_request", "expected_columns must be a list of strings"
            )
        if columns != expected:
            raise RunnerError(
                "unsafe_result", "result columns do not match expected_columns"
            )

    csv_content = _result_to_csv(columns, rows)
    sql_id = _insert_artifact(
        client,
        run_id=run_id,
        feature_slug=feature_slug,
        question_id=question_id,
        artifact_type="sql",
        source_scope=source_scope,
        content_format="sql",
        content=sql,
        metadata={"tables": sorted(physical_tables)},
    )
    aggregate_id = _insert_artifact(
        client,
        run_id=run_id,
        feature_slug=feature_slug,
        question_id=question_id,
        artifact_type="aggregate",
        source_scope=source_scope,
        content_format="csv",
        content=csv_content,
        row_count=len(rows),
        metadata={"columns": columns, "sql_artifact_id": sql_id},
    )
    preview = [
        {column: _json_safe(value) for column, value in zip(columns, row, strict=True)}
        for row in rows[:MAX_PREVIEW_ROWS]
    ]
    return {
        "ok": True,
        "artifact_ids": {"sql": sql_id, "aggregate": aggregate_id},
        "columns": columns,
        "row_count": len(rows),
        "preview_rows": preview,
        "preview_truncated": len(rows) > MAX_PREVIEW_ROWS,
        "raw_rows_to_llm": 0,
    }


def _load_aggregate_frames(
    client: Any, run_id: str, artifact_ids: list[str]
) -> list[Any]:
    if not artifact_ids or len(artifact_ids) > 20:
        raise RunnerError(
            "invalid_request", "input_artifact_ids must contain 1 to 20 UUIDs"
        )
    normalized: list[str] = []
    for value in artifact_ids:
        try:
            normalized.append(str(UUID(value)))
        except (TypeError, ValueError) as error:
            raise RunnerError(
                "invalid_request", "input_artifact_ids contains a non-UUID"
            ) from error
    try:
        result = client.query(
            "SELECT toString(artifact_id) AS artifact_id, content "
            f"FROM {ARTIFACT_TABLE} WHERE run_id = {{run_id:UUID}} "
            "AND artifact_type = 'aggregate' "
            "AND artifact_id IN {artifact_ids:Array(UUID)} "
            "ORDER BY created_at, artifact_id LIMIT 20",
            parameters={
                "run_id": UUID(run_id),
                "artifact_ids": [UUID(value) for value in normalized],
            },
            settings=QUERY_SETTINGS,
        )
    except Exception as error:
        raise RunnerError(
            "artifact_read_failed",
            f"aggregate artifact read failed ({type(error).__name__})",
        ) from error
    found = {str(row[0]): str(row[1]) for row in result.result_rows}
    if set(found) != set(normalized):
        raise RunnerError(
            "artifact_read_failed", "one or more aggregate artifacts were not found"
        )
    try:
        import pandas as pd
    except ImportError as error:
        raise RunnerError(
            "dependency_unavailable",
            "pandas must be preinstalled in the Code Interpreter image",
        ) from error
    return [pd.read_csv(io.StringIO(found[artifact_id])) for artifact_id in normalized]


def _stats_modules() -> tuple[Any, Any]:
    try:
        from scipy import stats
        from statsmodels.stats.multitest import multipletests
    except ImportError as error:
        raise RunnerError(
            "dependency_unavailable",
            "scipy and statsmodels must be preinstalled in the Code Interpreter image",
        ) from error
    return stats, multipletests


def _numeric(frame: Any, column: str) -> Any:
    if column not in frame.columns:
        raise RunnerError(
            "invalid_stats_request", f"CSV lacks required column {column!r}"
        )
    try:
        import pandas as pd
    except ImportError as error:
        raise RunnerError("dependency_unavailable", "pandas is unavailable") from error
    return pd.to_numeric(frame[column], errors="coerce")


def _wilson(successes: float, total: float, confidence: float = 0.95) -> dict[str, Any]:
    if total <= 0 or successes < 0 or successes > total:
        return {"status": "insufficient_data", "value": None}
    stats, _ = _stats_modules()
    z = float(stats.norm.ppf(1 - (1 - confidence) / 2))
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
        / denominator
    )
    return {
        "status": "answered",
        "value": proportion,
        "lower_bound": max(0.0, center - margin),
        "upper_bound": min(1.0, center + margin),
        "numerator": successes,
        "denominator": total,
        "confidence_level": confidence,
    }


def _group_rows(
    frame: Any, group_columns: list[str]
) -> list[tuple[dict[str, Any], Any]]:
    if not group_columns:
        return [({}, frame)]
    missing = [column for column in group_columns if column not in frame.columns]
    if missing:
        raise RunnerError(
            "invalid_stats_request", f"CSV lacks group columns: {missing}"
        )
    result: list[tuple[dict[str, Any], Any]] = []
    grouping: Any = group_columns[0] if len(group_columns) == 1 else group_columns
    for key, group in frame.groupby(grouping, dropna=False, sort=True):
        values = key if isinstance(key, tuple) else (key,)
        result.append(
            (dict(zip(group_columns, map(_json_safe, values), strict=True)), group)
        )
    return result


def run_stats(frames: list[Any], mode: str, options: dict[str, Any]) -> dict[str, Any]:
    if not frames:
        raise RunnerError(
            "invalid_stats_request", "at least one aggregate CSV is required"
        )
    stats, multipletests = _stats_modules()
    try:
        import pandas as pd
    except ImportError as error:
        raise RunnerError("dependency_unavailable", "pandas is unavailable") from error
    frame = pd.concat(frames, ignore_index=True, sort=False)
    if mode == "rate":
        numerator = _require_string(options, "numerator_column")
        denominator = _require_string(options, "denominator_column")
        groups = options.get("group_columns", [])
        if not isinstance(groups, list) or not all(
            isinstance(value, str) for value in groups
        ):
            raise RunnerError("invalid_stats_request", "group_columns must be a list")
        results = []
        for dimensions, subset in _group_rows(frame, groups):
            item = _wilson(
                float(_numeric(subset, numerator).sum()),
                float(_numeric(subset, denominator).sum()),
            )
            results.append({"dimensions": dimensions, **item})
        return {"mode": mode, "results": results}

    if mode == "rate_compare":
        numerator = _require_string(options, "numerator_column")
        denominator = _require_string(options, "denominator_column")
        group_column = _require_string(options, "group_column")
        group_a = options.get("group_a")
        group_b = options.get("group_b")
        if group_column not in frame.columns:
            raise RunnerError("invalid_stats_request", f"CSV lacks {group_column!r}")

        def totals(group_value: Any) -> tuple[float, float]:
            subset = frame[frame[group_column].astype(str) == str(group_value)]
            return (
                float(_numeric(subset, numerator).sum()),
                float(_numeric(subset, denominator).sum()),
            )

        success_a, total_a = totals(group_a)
        success_b, total_b = totals(group_b)
        if min(total_a, total_b) <= 0:
            return {"mode": mode, "status": "insufficient_data"}
        rate_a, rate_b = success_a / total_a, success_b / total_b
        pooled = (success_a + success_b) / (total_a + total_b)
        standard_error = math.sqrt(pooled * (1 - pooled) * (1 / total_a + 1 / total_b))
        z_score = (rate_a - rate_b) / standard_error if standard_error else 0.0
        p_value = float(2 * stats.norm.sf(abs(z_score)))
        return {
            "mode": mode,
            "status": "answered",
            "group_a": _json_safe(group_a),
            "group_b": _json_safe(group_b),
            "rate_a": rate_a,
            "rate_b": rate_b,
            "risk_difference": rate_a - rate_b,
            "relative_difference": None if rate_b == 0 else rate_a / rate_b - 1,
            "z_score": z_score,
            "p_value": p_value,
        }

    if mode == "mean_compare":
        group_column = _require_string(options, "group_column")
        group_a, group_b = options.get("group_a"), options.get("group_b")
        columns = {
            name: _require_string(options, f"{name}_column")
            for name in ("count", "mean", "variance")
        }

        def summary(group_value: Any) -> tuple[float, float, float]:
            subset = frame[frame[group_column].astype(str) == str(group_value)]
            if len(subset) != 1:
                raise RunnerError(
                    "invalid_stats_request",
                    "mean_compare requires one row per comparison group",
                )
            row = subset.iloc[0]
            return (
                float(row[columns["mean"]]),
                float(row[columns["variance"]]),
                float(row[columns["count"]]),
            )

        mean_a, variance_a, count_a = summary(group_a)
        mean_b, variance_b, count_b = summary(group_b)
        if min(count_a, count_b) < 2:
            return {"mode": mode, "status": "insufficient_data"}
        test = stats.ttest_ind_from_stats(
            mean_a,
            math.sqrt(max(variance_a, 0)),
            count_a,
            mean_b,
            math.sqrt(max(variance_b, 0)),
            count_b,
            equal_var=False,
        )
        return {
            "mode": mode,
            "status": "answered",
            "mean_a": mean_a,
            "mean_b": mean_b,
            "mean_difference": mean_a - mean_b,
            "statistic": float(test.statistic),
            "p_value": float(test.pvalue),
        }

    if mode == "trend":
        x_column = _require_string(options, "x_column")
        y_column = _require_string(options, "y_column")
        x = (
            pd.to_numeric(frame[x_column], errors="coerce")
            if x_column in frame
            else None
        )
        if x is None or x.isna().all():
            if x_column not in frame:
                raise RunnerError("invalid_stats_request", f"CSV lacks {x_column!r}")
            parsed = pd.to_datetime(frame[x_column], errors="coerce", utc=True)
            x = parsed.map(
                lambda value: value.timestamp() if pd.notna(value) else float("nan")
            )
        y = _numeric(frame, y_column)
        valid = x.notna() & y.notna()
        data = frame.loc[valid].copy()
        x_values = x[valid].astype(float)
        y_values = y[valid].astype(float)
        if len(data) < 3:
            return {"mode": mode, "status": "insufficient_data"}
        order = x_values.argsort()
        x_sorted = x_values.iloc[order]
        y_sorted = y_values.iloc[order]
        regression = stats.linregress(x_sorted, y_sorted)
        first, last = float(y_sorted.iloc[0]), float(y_sorted.iloc[-1])
        return {
            "mode": mode,
            "status": "answered",
            "bucket_count": len(y_sorted),
            "first": first,
            "last": last,
            "absolute_change": last - first,
            "relative_change": None if first == 0 else last / first - 1,
            "slope": float(regression.slope),
            "p_value": float(regression.pvalue),
        }

    if mode == "anomaly":
        value_column = _require_string(options, "value_column")
        label_column = options.get("label_column")
        values = _numeric(frame, value_column)
        valid = values.notna()
        values = values[valid].astype(float)
        if len(values) < 7:
            return {
                "mode": mode,
                "status": "insufficient_data",
                "bucket_count": len(values),
            }
        median = float(values.median())
        mad = float((values - median).abs().median())
        scores = (
            [0.0] * len(values)
            if mad == 0
            else [0.6745 * (v - median) / mad for v in values]
        )
        labels = (
            frame.loc[valid, label_column].tolist()
            if isinstance(label_column, str) and label_column in frame.columns
            else list(map(int, values.index))
        )
        anomalies = [
            {
                "label": _json_safe(label),
                "value": float(value),
                "modified_z": float(score),
            }
            for label, value, score in zip(labels, values.tolist(), scores, strict=True)
            if abs(score) >= 3.5
        ]
        return {
            "mode": mode,
            "status": "answered",
            "bucket_count": len(values),
            "median": median,
            "mad": mad,
            "anomalies": anomalies,
        }

    if mode == "correlation":
        x = _numeric(frame, _require_string(options, "x_column"))
        y = _numeric(frame, _require_string(options, "y_column"))
        valid = x.notna() & y.notna()
        if int(valid.sum()) < 8:
            return {
                "mode": mode,
                "status": "insufficient_data",
                "bucket_count": int(valid.sum()),
            }
        correlation = stats.spearmanr(x[valid].astype(float), y[valid].astype(float))
        return {
            "mode": mode,
            "status": "answered",
            "bucket_count": int(valid.sum()),
            "spearman_rho": float(correlation.statistic),
            "p_value": float(correlation.pvalue),
            "caveat": "Aggregate-bucket correlation is ecological and noncausal.",
        }

    if mode == "adjust_pvalues":
        pvalue_column = _require_string(options, "pvalue_column")
        id_column = _require_string(options, "id_column")
        if id_column not in frame.columns:
            raise RunnerError("invalid_stats_request", f"CSV lacks {id_column!r}")
        pvalues = _numeric(frame, pvalue_column)
        valid = pvalues.notna()
        if not valid.any():
            return {"mode": mode, "status": "insufficient_data"}
        rejected, adjusted, _, _ = multipletests(
            pvalues[valid].astype(float).tolist(), method="fdr_bh"
        )
        results = [
            {
                "id": _json_safe(identifier),
                "p_value": float(pvalue),
                "adjusted_p_value": float(adjusted_value),
                "rejected": bool(is_rejected),
            }
            for identifier, pvalue, adjusted_value, is_rejected in zip(
                frame.loc[valid, id_column].tolist(),
                pvalues[valid].tolist(),
                adjusted,
                rejected,
                strict=True,
            )
        ]
        return {"mode": mode, "status": "answered", "results": results}

    raise RunnerError("invalid_stats_request", f"unsupported stats mode {mode!r}")


def _bounded_stats_summary(result: dict[str, Any]) -> dict[str, Any]:
    bounded = _json_safe(result)
    if isinstance(bounded, dict):
        for key in ("results", "anomalies"):
            value = bounded.get(key)
            if isinstance(value, list) and len(value) > MAX_PREVIEW_ROWS:
                bounded[key] = value[:MAX_PREVIEW_ROWS]
                bounded[f"{key}_truncated"] = True
    return bounded


def action_stats(client: Any, request: dict[str, Any]) -> dict[str, Any]:
    run_id = _require_uuid(request, "run_id")
    feature_slug = _require_string(request, "feature_slug")
    question_id = _require_string(request, "question_id")
    mode = _require_string(request, "mode")
    artifact_ids = request.get("input_artifact_ids")
    if not isinstance(artifact_ids, list):
        raise RunnerError("invalid_request", "input_artifact_ids must be a list")
    options = request.get("options", {})
    if not isinstance(options, dict):
        raise RunnerError("invalid_request", "options must be an object")
    frames = _load_aggregate_frames(client, run_id, artifact_ids)
    result = run_stats(frames, mode, options)
    artifact_id = _insert_artifact(
        client,
        run_id=run_id,
        feature_slug=feature_slug,
        question_id=question_id,
        artifact_type="stats",
        content_format="json",
        content=_canonical_json(result),
        metadata={"mode": mode, "input_artifact_ids": artifact_ids},
    )
    return {
        "ok": True,
        "artifact_ids": [artifact_id],
        "result": _bounded_stats_summary(result),
        "raw_rows_to_llm": 0,
    }


def action_put_artifact(client: Any, request: dict[str, Any]) -> dict[str, Any]:
    run_id = _require_uuid(request, "run_id")
    feature_slug = _require_string(request, "feature_slug")
    question_id = request.get("question_id", "")
    if not isinstance(question_id, str):
        raise RunnerError("invalid_request", "question_id must be a string")
    artifact_type = _require_string(request, "artifact_type")
    if artifact_type not in {"review", "report", "context_gap"}:
        raise RunnerError(
            "invalid_request", "artifact_type is not writable through put_artifact"
        )
    content_format = _require_string(request, "content_format")
    if content_format not in {"json", "markdown"}:
        raise RunnerError(
            "invalid_request", "put_artifact accepts json or markdown content"
        )
    content = _require_string(request, "content")
    if content_format == "json":
        try:
            json.loads(content)
        except json.JSONDecodeError as error:
            raise RunnerError("invalid_request", "json artifact content is invalid") from error
    metadata = request.get("metadata", {})
    if not isinstance(metadata, dict):
        raise RunnerError("invalid_request", "metadata must be an object")
    artifact_id = _insert_artifact(
        client,
        run_id=run_id,
        feature_slug=feature_slug,
        question_id=question_id,
        artifact_type=artifact_type,
        content_format=content_format,
        content=content,
        metadata=metadata,
    )
    return {"ok": True, "artifact_ids": [artifact_id], "raw_rows_to_llm": 0}


_ARTIFACT_COLUMNS = (
    "artifact_id",
    "run_id",
    "feature_slug",
    "question_id",
    "artifact_type",
    "source_scope",
    "content_format",
    "row_count",
    "content",
    "metadata_json",
    "content_hash",
    "created_at",
)


def action_get_artifact(client: Any, request: dict[str, Any]) -> dict[str, Any]:
    run_id = _require_uuid(request, "run_id")
    artifact_id = _require_uuid(request, "artifact_id")
    try:
        result = client.query(
            "SELECT toString(artifact_id), toString(run_id), feature_slug, question_id, "
            "artifact_type, source_scope, content_format, row_count, content, metadata_json, "
            f"content_hash, created_at FROM {ARTIFACT_TABLE} "
            "WHERE run_id = {run_id:UUID} AND artifact_id = {artifact_id:UUID} LIMIT 1",
            parameters={"run_id": run_id, "artifact_id": artifact_id},
            settings=QUERY_SETTINGS,
        )
    except Exception as error:
        raise RunnerError(
            "artifact_read_failed", f"artifact read failed ({type(error).__name__})"
        ) from error
    if not result.result_rows:
        raise RunnerError("artifact_read_failed", "artifact was not found")
    artifact = dict(zip(_ARTIFACT_COLUMNS, result.result_rows[0], strict=True))
    content = str(artifact.pop("content"))
    artifact = _json_safe(artifact)
    if artifact["content_format"] in {"csv", "json"}:
        maximum = request.get("max_records", MAX_PREVIEW_ROWS)
        if not isinstance(maximum, int) or not 1 <= maximum <= MAX_PREVIEW_ROWS:
            raise RunnerError("invalid_request", "max_records must be between 1 and 20")
    if artifact["content_format"] == "csv":
        reader = csv.DictReader(io.StringIO(content))
        records = [row for _, row in zip(range(maximum), reader, strict=False)]
        return {
            "ok": True,
            "artifact": artifact,
            "records": records,
            "records_truncated": int(artifact["row_count"]) > len(records),
            "raw_rows_to_llm": 0,
        }
    if artifact["content_format"] == "json":
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise RunnerError(
                "artifact_read_failed", "stored JSON artifact is invalid"
            ) from error

        truncated = False

        def bound_lists(value: Any) -> Any:
            nonlocal truncated
            if isinstance(value, list):
                if len(value) > maximum:
                    truncated = True
                return [bound_lists(item) for item in value[:maximum]]
            if isinstance(value, dict):
                return {str(key): bound_lists(item) for key, item in value.items()}
            return _json_safe(value)

        return {
            "ok": True,
            "artifact": artifact,
            "json_content": bound_lists(parsed),
            "records_truncated": truncated,
            "raw_rows_to_llm": 0,
        }
    offset = request.get("offset", 0)
    max_chars = request.get("max_chars", MAX_TEXT_CHUNK)
    if not isinstance(offset, int) or offset < 0:
        raise RunnerError("invalid_request", "offset must be a non-negative integer")
    if not isinstance(max_chars, int) or not 1 <= max_chars <= MAX_TEXT_CHUNK:
        raise RunnerError("invalid_request", "max_chars must be between 1 and 50,000")
    chunk = content[offset : offset + max_chars]
    return {
        "ok": True,
        "artifact": artifact,
        "content_chunk": chunk,
        "offset": offset,
        "next_offset": offset + len(chunk),
        "eof": offset + len(chunk) >= len(content),
        "raw_rows_to_llm": 0,
    }


def action_list_run(client: Any, request: dict[str, Any]) -> dict[str, Any]:
    run_id = _require_uuid(request, "run_id")
    try:
        result = client.query(
            "SELECT toString(artifact_id) AS artifact_id, question_id, artifact_type, "
            "source_scope, content_format, row_count, content_hash, created_at "
            f"FROM {ARTIFACT_TABLE} WHERE run_id = {{run_id:UUID}} "
            "ORDER BY created_at, artifact_id LIMIT 1000",
            parameters={"run_id": run_id},
            settings={**QUERY_SETTINGS, "max_result_rows": 1000},
        )
    except Exception as error:
        raise RunnerError(
            "artifact_read_failed",
            f"run artifact listing failed ({type(error).__name__})",
        ) from error
    return {
        "ok": True,
        "run_id": run_id,
        "artifacts": _named_rows(result),
        "raw_rows_to_llm": 0,
    }


_ACTIONS = {
    "bootstrap": action_bootstrap,
    "discover": action_discover,
    "query": action_query,
    "stats": action_stats,
    "put_artifact": action_put_artifact,
    "get_artifact": action_get_artifact,
    "list_run": action_list_run,
}


def _assert_bootstrapped(client: Any, request: dict[str, Any]) -> None:
    run_id = _require_uuid(request, "run_id")
    try:
        result = client.query(
            f"SELECT count() FROM {ARTIFACT_TABLE} "
            "WHERE run_id = {run_id:UUID} AND artifact_type = 'context_snapshot' LIMIT 1",
            parameters={"run_id": UUID(run_id)},
            settings=QUERY_SETTINGS,
        )
    except Exception as error:
        raise RunnerError(
            "artifact_read_failed",
            f"bootstrap verification failed ({type(error).__name__})",
        ) from error
    if not result.result_rows or int(result.result_rows[0][0]) < 1:
        raise RunnerError(
            "missing_context",
            "bootstrap must complete before any other action",
            status="missing_context",
        )


def dispatch(client: Any, request: dict[str, Any]) -> dict[str, Any]:
    action = _require_string(request, "action")
    handler = _ACTIONS.get(action)
    if handler is None:
        raise RunnerError("invalid_request", f"unsupported action {action!r}")
    if action != "bootstrap":
        _assert_bootstrapped(client, request)
    return handler(client, request)


def main() -> int:
    response: dict[str, Any]
    try:
        request = decode_request()
        client = create_client()
        response = dispatch(client, request)
    except RunnerError as error:
        response = {
            "ok": False,
            "error": {"code": error.code, "message": str(error)},
            "status": error.status,
            "raw_rows_to_llm": 0,
        }
    except Exception as error:  # noqa: BLE001 - stdout must remain machine-readable.
        response = {
            "ok": False,
            "error": {
                "code": "internal_error",
                "message": f"analytics runner failed ({type(error).__name__})",
            },
            "status": None,
            "raw_rows_to_llm": 0,
        }
    sys.stdout.write(
        json.dumps(_json_safe(response), sort_keys=True, separators=(",", ":"))
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
