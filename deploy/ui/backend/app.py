"""Investigation upload API and sequential agent runner."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import clickhouse_connect
import httpx
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, ContentSettings, generate_blob_sas
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
# The investigation workflow is executed by one persisted LibreChat agent.  The
# linked analytics/context agents and every tool call run within LibreChat; the
# UI process only accepts uploads, issues short-lived input URLs, and records
# the resulting hand-off.
AGENTS = ("instrumentation-agent", "analytics-agent", "context-agent", "finalizer-agent")
running_investigations: set[str] = set()


@dataclass(frozen=True)
class Settings:
    azure_connection_string: str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    azure_account_url: str = os.environ.get("AZURE_STORAGE_ACCOUNT_URL", "")
    azure_account_key: str = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY", "")
    azure_container: str = os.environ["AZURE_STORAGE_CONTAINER"]
    clickhouse_host: str = os.environ.get("CLICKHOUSE_HOST", "localhost")
    clickhouse_dsn: str = os.environ.get("CLICKHOUSE_DSN", "")
    clickhouse_port: int = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
    clickhouse_username: str = os.environ.get("CLICKHOUSE_USERNAME", "default")
    clickhouse_password: str = os.environ.get("CLICKHOUSE_PASSWORD", "")
    clickhouse_database: str = os.environ.get("CLICKHOUSE_DATABASE", "default")
    librechat_native_url: str = os.environ.get("LIBRECHAT_NATIVE_URL", "https://clickathon26librechat.nannan.in")
    librechat_native_email: str = os.environ["LIBRECHAT_NATIVE_EMAIL"]
    librechat_native_password: str = os.environ["LIBRECHAT_NATIVE_PASSWORD"]
    librechat_workflow_agent_id: str = os.environ["LIBRECHAT_WORKFLOW_AGENT_ID"]
    investigation_runtime_token: str = os.environ["INVESTIGATION_RUNTIME_TOKEN"]
    agent_context_dir: str = os.environ.get("AGENT_CONTEXT_DIR", str(ROOT.parent / "librechat" / "agents"))
    runtime_context_dir: str = os.environ.get("RUNTIME_CONTEXT_DIR", str(ROOT / "runtime-context"))
    max_upload_bytes: int = int(os.environ.get("MAX_UPLOAD_BYTES", str(256 * 1024 * 1024)))
    sas_ttl_minutes: int = int(os.environ.get("SAS_TTL_MINUTES", "30"))
    poll_interval_seconds: int = int(os.environ.get("POLL_INTERVAL_SECONDS", "2"))
    # The web process only accepts uploads and serves status. A dedicated
    # worker owns the long-running LibreChat request so a web restart cannot
    # cancel an active workflow task.
    workflow_worker_enabled: bool = os.environ.get("WORKFLOW_WORKER_ENABLED", "true").lower() == "true"


settings = Settings()
app = FastAPI(title="ClickHouse Investigations")
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets", check_dir=False), name="assets")


def now() -> datetime:
    return datetime.now(timezone.utc)


def ch():
    if settings.clickhouse_dsn:
        parsed = urlparse(settings.clickhouse_dsn if "://" in settings.clickhouse_dsn else f"https://{settings.clickhouse_dsn}")
        return clickhouse_connect.get_client(
            host=parsed.hostname,
            port=parsed.port or (8443 if parsed.scheme == "https" else 8123),
            username=settings.clickhouse_username,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
            secure=parsed.scheme == "https",
        )
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_username,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
    )


def init_schema() -> None:
    for statement in (ROOT / "schema.sql").read_text().split(";\n\n"):
        if statement.strip():
            ch().command(statement)


def ensure_container() -> None:
    try:
        blob_client().create_container(settings.azure_container)
    except ResourceExistsError:
        pass


def latest_investigation(investigation_id: str) -> dict[str, Any] | None:
    query = """
        SELECT argMax(status, revision), argMax(current_agent, revision),
               argMax(progress, revision), argMax(final_result, revision),
               argMax(error_message, revision), max(revision), max(updated_at)
        FROM agent.investigations WHERE investigation_id = {id:UUID}
    """
    row = ch().query(query, parameters={"id": investigation_id}).result_rows[0]
    if not row[5]:
        return None
    return dict(zip(("status", "current_agent", "progress", "final_result", "error_message", "revision", "updated_at"), row))


def agent_states(investigation_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT agent_name, argMax(status, revision), argMax(progress, revision),
               argMax(error_message, revision), max(updated_at)
        FROM agent.investigation_agent_status WHERE investigation_id = {id:UUID}
        GROUP BY agent_name ORDER BY indexOf({agents:Array(String)}, agent_name)
    """
    rows = ch().query(query, parameters={"id": investigation_id, "agents": list(AGENTS)}).result_rows
    return [dict(zip(("agent", "status", "progress", "error_message", "updated_at"), row)) for row in rows]


def insert_investigation(record: dict[str, Any]) -> None:
    ch().insert("agent.investigations", [list(record.values())], column_names=list(record))


def insert_agent_status(record: dict[str, Any]) -> None:
    ch().insert("agent.investigation_agent_status", [list(record.values())], column_names=list(record))


def persist_finalizer_result(investigation_id: str, revision: int, envelope: dict[str, Any]) -> str:
    """Append a canonical Finalizer envelope and its indexed display sections."""
    result_id, created_at = str(uuid.uuid4()), now()
    encoded = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    run_id = envelope.get("run_id")
    try:
        run_uuid = str(uuid.UUID(run_id)) if run_id else None
    except (TypeError, ValueError):
        run_uuid = None
    ch().insert("agent.finalizer_results", [[result_id, investigation_id, revision, run_uuid,
        str(envelope.get("status", "partial")), created_at, hashlib.sha256(encoded.encode()).hexdigest(), encoded, created_at]],
        column_names=["result_id", "investigation_id", "revision", "run_id", "status", "generated_at", "envelope_sha256", "envelope_json", "created_at"])
    section_values = {
        "executive_summary": envelope.get("executive_summary", []), "insight": envelope.get("insights", []),
        "dashboard": envelope.get("dashboards", []), "limitation": envelope.get("limitations", []), "error": envelope.get("errors", []),
        "lineage": [envelope.get("lineage")] if isinstance(envelope.get("lineage"), dict) else [],
        "data_quality": [envelope.get("data_quality")] if isinstance(envelope.get("data_quality"), dict) else [],
        "context": [envelope.get("context")] if isinstance(envelope.get("context"), dict) else [],
        "schema": [envelope.get("schema")] if isinstance(envelope.get("schema"), dict) else [],
    }
    actions = envelope.get("actions", {})
    if isinstance(actions, dict): section_values.update({f"action_{key}": value for key, value in actions.items()})
    rows = []
    for category, values in section_values.items():
        if not isinstance(values, list): continue
        for ordinal, value in enumerate(values[:200]):
            item = value if isinstance(value, dict) else {"text": str(value)}
            title = str(item.get("title") or item.get("finding") or item.get("action") or item.get("text") or category)
            rows.append([result_id, investigation_id, revision, category, ordinal, str(item.get("id") or ordinal), title,
                         json.dumps(item, ensure_ascii=False, separators=(",", ":")), created_at])
    if rows:
        ch().insert("agent.finalizer_result_items", rows, column_names=["result_id", "investigation_id", "revision", "category", "ordinal", "item_id", "title", "payload_json", "created_at"])
    return result_id


def append_investigation(investigation_id: str, status: str, current_agent: str, progress: str,
                         final_result: str = "", error_message: str = "") -> None:
    current = latest_investigation(investigation_id)
    if not current:
        raise RuntimeError(f"Unknown investigation {investigation_id}")
    source = ch().query("""
        SELECT feature_key, events_blob_uri, events_filename, events_bytes, events_sha256,
               spec_blob_uri, spec_filename, spec_bytes, spec_sha256, created_at
        FROM agent.investigations WHERE investigation_id = {id:UUID} ORDER BY revision DESC LIMIT 1
    """, parameters={"id": investigation_id}).result_rows[0]
    keys = ("feature_key", "events_blob_uri", "events_filename", "events_bytes", "events_sha256", "spec_blob_uri", "spec_filename", "spec_bytes", "spec_sha256", "created_at")
    record = dict(zip(keys, source))
    record.update({"investigation_id": investigation_id, "revision": current["revision"] + 1,
                   "updated_at": now(), "status": status, "current_agent": current_agent,
                   "progress": progress, "final_result": final_result, "error_message": error_message})
    insert_investigation(record)


def append_agent_status(investigation_id: str, agent: str, status: str, progress: str,
                        result: str = "", error_message: str = "") -> None:
    existing = [state for state in agent_states(investigation_id) if state["agent"] == agent]
    revision = 1 if not existing else int(ch().query("""
        SELECT max(revision) FROM agent.investigation_agent_status
        WHERE investigation_id = {id:UUID} AND agent_name = {agent:String}
    """, parameters={"id": investigation_id, "agent": agent}).result_rows[0][0]) + 1
    insert_agent_status({"investigation_id": investigation_id, "agent_name": agent, "revision": revision,
                         "status": status, "progress": progress, "result": result,
                         "error_message": error_message, "updated_at": now()})


def blob_client():
    if settings.azure_connection_string:
        return BlobServiceClient.from_connection_string(settings.azure_connection_string)
    if not settings.azure_account_url or not settings.azure_account_key:
        raise RuntimeError("Set AZURE_STORAGE_CONNECTION_STRING or Azure account URL and key")
    return BlobServiceClient(account_url=settings.azure_account_url, credential=settings.azure_account_key)


def storage_credentials() -> tuple[str, str]:
    if settings.azure_connection_string:
        values = dict(part.split("=", 1) for part in settings.azure_connection_string.split(";") if "=" in part)
        return values["AccountName"], values["AccountKey"]
    account_name = settings.azure_account_url.rstrip("/").split("//", 1)[1].split(".", 1)[0]
    return account_name, settings.azure_account_key


async def save_upload(investigation_id: str, uploaded: UploadFile, label: str) -> dict[str, Any]:
    blob_name = f"{investigation_id}/{label}"
    digest = hashlib.sha256()
    total = 0
    # Spill to disk after 8 MiB so a large artifact never becomes a large Python
    # allocation before it is streamed to Azure.
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as spool:
        while data := await uploaded.read(1024 * 1024):
            total += len(data)
            if total > settings.max_upload_bytes:
                raise HTTPException(413, f"{label} exceeds the upload limit")
            digest.update(data)
            spool.write(data)
        if not total:
            raise HTTPException(422, f"{label} is empty")
        spool.seek(0)
        await asyncio.to_thread(
            blob_client().get_blob_client(settings.azure_container, blob_name).upload_blob,
            spool,
            overwrite=False,
            content_settings=ContentSettings(content_type="application/x-ndjson" if label == "events.ndjson" else "text/markdown"),
        )
    return {"uri": blob_client().get_blob_client(settings.azure_container, blob_name).url,
            "filename": uploaded.filename, "bytes": total, "sha256": digest.hexdigest(), "blob_name": blob_name}


def sas_url(blob_uri: str) -> str:
    blob_name = blob_uri.rsplit(f"/{settings.azure_container}/", 1)[1]
    account_name, account_key = storage_credentials()
    token = generate_blob_sas(account_name=account_name, container_name=settings.azure_container,
                              blob_name=blob_name, account_key=account_key,
                              permission=BlobSasPermissions(read=True),
                              expiry=now() + timedelta(minutes=settings.sas_ttl_minutes))
    return f"{blob_uri}?{token}"


def delete_blob(blob_uri: str) -> None:
    blob_name = blob_uri.rsplit(f"/{settings.azure_container}/", 1)[1]
    blob_client().get_blob_client(settings.azure_container, blob_name).delete_blob()


def source_record(investigation_id: str) -> dict[str, Any]:
    row = ch().query("""
        SELECT feature_key, events_blob_uri, events_filename, events_bytes, events_sha256,
               spec_blob_uri, spec_filename, spec_bytes, spec_sha256
        FROM agent.investigations WHERE investigation_id = {id:UUID}
        ORDER BY revision DESC LIMIT 1
    """, parameters={"id": investigation_id}).result_rows[0]
    keys = ("feature_key", "events_blob_uri", "events_filename", "events_bytes", "events_sha256",
            "spec_blob_uri", "spec_filename", "spec_bytes", "spec_sha256")
    return dict(zip(keys, row))


def source_blob(blob_uri: str):
    prefix = f"/{settings.azure_container}/"
    if prefix not in blob_uri:
        raise RuntimeError("Source blob is outside the configured container")
    return blob_client().get_blob_client(settings.azure_container, blob_uri.split(prefix, 1)[1])


def blob_lines(blob_uri: str):
    """Yield NDJSON lines while retaining only an incomplete trailing line."""
    trailing = b""
    for chunk in source_blob(blob_uri).download_blob().chunks():
        trailing += chunk
        *complete, trailing = trailing.split(b"\n")
        yield from complete
    if trailing.strip():
        yield trailing


def profile_ndjson_blob(blob_uri: str, requested_fields: list[str] | None = None) -> dict[str, Any]:
    rows = invalid_rows = 0
    event_counts: Counter[str] = Counter()
    field_stats: dict[str, dict[str, Any]] = {}
    fields_requested = requested_fields or []
    for raw_line in blob_lines(blob_uri):
        if not raw_line.strip():
            continue
        rows += 1
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            invalid_rows += 1
            continue
        if not isinstance(row, dict):
            invalid_rows += 1
            continue
        event = row.get("event_name", row.get("event", row.get("name")))
        event_counts[str(event) if event is not None else "<missing>"] += 1
        for field in fields_requested or list(row.keys()):
            if field not in row:
                continue
            if field not in field_stats and len(field_stats) >= 100 and not fields_requested:
                continue
            stat = field_stats.setdefault(field, {"present": 0, "nulls": 0, "types": Counter(), "distinct": set(), "distinct_overflow": False})
            value = row[field]
            stat["present"] += 1
            stat["nulls"] += value is None
            stat["types"][value_type(value)] += 1
            if isinstance(value, str) and not stat["distinct_overflow"]:
                stat["distinct"].add(value)
                if len(stat["distinct"]) > 10_000:
                    stat["distinct"].clear()
                    stat["distinct_overflow"] = True
    fields = {name: {"present": stat["present"], "missing": rows - invalid_rows - stat["present"],
                      "nulls": stat["nulls"], "types": dict(stat["types"]),
                      "distinct_strings": ">10000" if stat["distinct_overflow"] else len(stat["distinct"])}
              for name, stat in field_stats.items()}
    return {"source_rows": rows, "profiled_rows": rows - invalid_rows, "invalid_rows": invalid_rows,
            "event_counts": dict(event_counts.most_common(100)), "fields": fields,
            "auto_field_cap_reached": not fields_requested and len(field_stats) >= 100}


def peek_ndjson_blob(blob_uri: str, event_values: set[str], contains_fields: set[str], limit: int) -> dict[str, Any]:
    if not event_values and not contains_fields:
        raise ValueError("A filtered peek requires event_values or contains_fields")
    rows: list[Any] = []
    matched = 0
    for raw_line in blob_lines(blob_uri):
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        event = str(row.get("event_name", row.get("event", row.get("name", ""))))
        if event_values and event not in event_values:
            continue
        if contains_fields and not contains_fields.issubset(row):
            continue
        matched += 1
        if len(rows) < limit:
            rows.append(redact_preview(row))
    return {"matched_rows": matched, "returned_rows": len(rows), "rows": rows}


def context_for(agent: str) -> str:
    path = Path(settings.agent_context_dir) / agent / "context.md"
    return path.read_text() if path.exists() else f"You are {agent}."


def businesslogic_path() -> Path:
    return Path(settings.runtime_context_dir) / "businesslogic.md"


def ensure_runtime_context() -> None:
    path = businesslogic_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        seed = Path(settings.agent_context_dir) / "businesslogic.md"
        if seed.exists():
            shutil.copyfile(seed, path)
        else:
            path.write_text("# Business Logic Metadata\n\n- Context version: `base-1`\n- Status: `seed`\n")


def require_artifact(arguments: dict[str, Any], artifacts: dict[str, Path], allowed: set[str]) -> tuple[str, Path]:
    artifact = arguments.get("artifact")
    if artifact not in allowed or artifact not in artifacts or not artifacts[artifact].is_file():
        raise RuntimeError(f"Downloaded artifact required: one of {sorted(allowed)}")
    return artifact, artifacts[artifact]


def value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def redact_preview(value: Any, key: str = "", depth: int = 0) -> Any:
    sensitive = ("email", "phone", "token", "secret", "password", "authorization", "address", "ip")
    if key.lower().endswith("id") or any(term in key.lower() for term in sensitive):
        return "[REDACTED]"
    if depth >= 3:
        return {"type": value_type(value)}
    if isinstance(value, dict):
        return {str(k): redact_preview(v, str(k), depth + 1) for k, v in list(value.items())[:30]}
    if isinstance(value, list):
        return [redact_preview(item, key, depth + 1) for item in value[:10]]
    if isinstance(value, str) and len(value) > 256:
        return f"{value[:256]}…[truncated]"
    return value


def profile_ndjson_file(path: Path, event_field: str, event_values: set[str], requested_fields: list[str]) -> dict[str, Any]:
    rows = invalid_rows = filtered_rows = 0
    event_counts: Counter[str] = Counter()
    field_stats: dict[str, dict[str, Any]] = {}
    max_auto_fields = 100

    with path.open("rb") as source:
        for raw_line in source:
            if not raw_line.strip():
                continue
            rows += 1
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError:
                invalid_rows += 1
                continue
            if not isinstance(row, dict):
                invalid_rows += 1
                continue
            event = row.get(event_field)
            if event_values and str(event) not in event_values:
                continue
            filtered_rows += 1
            event_counts[str(event) if event is not None else "<missing>"] += 1
            fields = requested_fields or list(row.keys())
            for field in fields:
                if field not in row:
                    continue
                if field not in field_stats and len(field_stats) >= max_auto_fields and not requested_fields:
                    continue
                stat = field_stats.setdefault(field, {"present": 0, "nulls": 0, "types": Counter(), "min": None, "max": None, "distinct": set(), "distinct_overflow": False})
                value = row[field]
                stat["present"] += 1
                stat["types"][value_type(value)] += 1
                if value is None:
                    stat["nulls"] += 1
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    stat["min"] = value if stat["min"] is None else min(stat["min"], value)
                    stat["max"] = value if stat["max"] is None else max(stat["max"], value)
                if isinstance(value, str) and not stat["distinct_overflow"]:
                    stat["distinct"].add(value)
                    if len(stat["distinct"]) > 10_000:
                        stat["distinct"].clear()
                        stat["distinct_overflow"] = True

    fields_result = {}
    for field, stat in field_stats.items():
        fields_result[field] = {
            "present": stat["present"],
            "missing": filtered_rows - stat["present"],
            "nulls": stat["nulls"],
            "types": dict(stat["types"]),
            "distinct_strings": ">10000" if stat["distinct_overflow"] else len(stat["distinct"]),
            "min": stat["min"],
            "max": stat["max"],
        }
    return {
        "artifact": "events",
        "source_rows": rows,
        "profiled_rows": filtered_rows,
        "invalid_rows": invalid_rows,
        "event_counts": dict(event_counts.most_common(100)),
        "fields": fields_result,
        "auto_field_cap_reached": not requested_fields and len(field_stats) >= max_auto_fields,
    }


def peek_ndjson_file(path: Path, event_field: str, event_values: set[str], contains_fields: set[str], limit: int) -> dict[str, Any]:
    if not event_values and not contains_fields:
        raise RuntimeError("peek_ndjson requires event_values or contains_fields")
    rows = []
    matched = 0
    with path.open("rb") as source:
        for raw_line in source:
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if event_values and str(row.get(event_field)) not in event_values:
                continue
            if contains_fields and not contains_fields.issubset(row):
                continue
            matched += 1
            if len(rows) < limit:
                rows.append(redact_preview(row))
    return {"artifact": "events", "matched_rows": matched, "returned_rows": len(rows), "rows": rows}


async def run_blob_tool(name: str, arguments: dict[str, Any], artifacts: dict[str, Path], client: httpx.AsyncClient) -> dict[str, Any]:
    if name == "download_blob":
        artifact = arguments.get("artifact")
        url = arguments.get("url", "")
        if artifact not in artifacts or not isinstance(url, str) or not url.startswith(blob_client().url):
            raise RuntimeError("Agent attempted to download an unauthorized blob artifact")
        digest = hashlib.sha256()
        total = 0
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with artifacts[artifact].open("wb") as target:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    total += len(chunk)
                    if total > settings.max_upload_bytes:
                        raise RuntimeError(f"{artifact} exceeds the configured artifact size limit")
                    digest.update(chunk)
                    target.write(chunk)
        return {"artifact": artifact, "stored_on_disk": True, "bytes": total, "sha256": digest.hexdigest(), "content_returned": False}
    if name == "profile_ndjson":
        _, path = require_artifact(arguments, artifacts, {"events"})
        return await asyncio.to_thread(profile_ndjson_file, path, arguments.get("event_field", "event_name"), set(arguments.get("event_values", [])), arguments.get("fields", []))
    if name == "peek_ndjson":
        _, path = require_artifact(arguments, artifacts, {"events"})
        return await asyncio.to_thread(peek_ndjson_file, path, arguments.get("event_field", "event_name"), set(arguments.get("event_values", [])), set(arguments.get("contains_fields", [])), min(int(arguments.get("limit", 10)), 20))
    if name == "peek_text":
        _, path = require_artifact(arguments, artifacts, {"spec"})
        offset = int(arguments.get("offset_bytes", 0))
        length = min(int(arguments.get("max_bytes", 16384)), 16384)
        with path.open("rb") as source:
            source.seek(offset)
            content = source.read(length).decode("utf-8", errors="replace")
        return {"artifact": "spec", "offset_bytes": offset, "returned_bytes": len(content.encode("utf-8")), "content": content}
    raise RuntimeError(f"Unsupported instrumentation tool: {name}")


async def run_legacy_local_agent(agent: str, user_prompt: str) -> str:
    """Deprecated local loop retained temporarily while callers migrate to LibreChat."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": context_for(agent)}, {"role": "user", "content": user_prompt}]
    tools = [] if agent != "instrumentation-agent" else [{"type": "function", "function": {
        "name": "download_blob",
        "description": "Stream an investigation blob to the agent's temporary disk workspace. Returns metadata and an artifact name only; never returns blob contents.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"},
            "artifact": {"type": "string", "enum": ["events", "spec"]},
        }, "required": ["url", "artifact"], "additionalProperties": False},
    }}, {"type": "function", "function": {
        "name": "profile_ndjson",
        "description": "Compute bounded aggregate schema and quality statistics by streaming the downloaded NDJSON on disk. Does not return event rows.",
        "parameters": {"type": "object", "properties": {
            "artifact": {"type": "string", "enum": ["events"]},
            "event_field": {"type": "string", "default": "event_name"},
            "event_values": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "fields": {"type": "array", "items": {"type": "string"}, "maxItems": 50},
        }, "required": ["artifact"], "additionalProperties": False},
    }}, {"type": "function", "function": {
        "name": "peek_ndjson",
        "description": "Return at most 20 filtered, redacted NDJSON rows from a downloaded event artifact. Use only after profiling and always supply an event or field filter.",
        "parameters": {"type": "object", "properties": {
            "artifact": {"type": "string", "enum": ["events"]},
            "event_field": {"type": "string", "default": "event_name"},
            "event_values": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "contains_fields": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
        }, "required": ["artifact"], "additionalProperties": False},
    }}, {"type": "function", "function": {
        "name": "peek_text",
        "description": "Read a bounded 16 KiB window from the downloaded specification artifact. Never use this for the event artifact.",
        "parameters": {"type": "object", "properties": {
            "artifact": {"type": "string", "enum": ["spec"]},
            "offset_bytes": {"type": "integer", "minimum": 0, "default": 0},
            "max_bytes": {"type": "integer", "minimum": 1, "maximum": 16384, "default": 16384},
        }, "required": ["artifact"], "additionalProperties": False},
    }}]
    raise RuntimeError("Local agent execution is disabled; configure the LibreChat Agents runtime")
    headers = {"Authorization": "disabled"}
    with tempfile.TemporaryDirectory(prefix="investigation-agent-") as workspace:
        artifacts = {"events": Path(workspace) / "events.ndjson", "spec": Path(workspace) / "spec.md"}
        async with httpx.AsyncClient(timeout=600) as client:
            for _ in range(8):
                for attempt in range(4):
                    response = await client.post("http://disabled.invalid", headers=headers, json={
                        "model": "disabled",
                        "messages": messages,
                        "tools": tools,
                        "reasoning_effort": "none",
                    })
                    if response.status_code != 429 or attempt == 3:
                        break
                    retry_after = response.headers.get("retry-after")
                    await asyncio.sleep(float(retry_after) if retry_after else 2 ** attempt)
                response.raise_for_status()
                message = response.json()["choices"][0]["message"]
                tool_calls = message.get("tool_calls", [])
                if not tool_calls:
                    return message.get("content") or ""
                messages.append(message)
                for call in tool_calls:
                    arguments = json.loads(call["function"]["arguments"])
                    result = await run_blob_tool(call["function"]["name"], arguments, artifacts, client)
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, separators=(",", ":"))})
    raise RuntimeError(f"{agent} exhausted its tool-call budget")


async def run_agent(agent_id: str, user_prompt: str) -> str:
    """Execute through LibreChat's native runtime so configured subagents load."""
    user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
    async with httpx.AsyncClient(timeout=900) as client:
        login = await client.post(
            f"{settings.librechat_native_url}/api/auth/login",
            headers={"User-Agent": user_agent},
            json={"email": settings.librechat_native_email, "password": settings.librechat_native_password},
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['token']}", "User-Agent": user_agent}
        request_payload = {
            "text": user_prompt,
            "sender": "User",
            "isCreatedByUser": True,
            "parentMessageId": "00000000-0000-0000-0000-000000000000",
            "conversationId": "new",
            "messageId": str(uuid.uuid4()),
            "error": False,
            "endpoint": "agents",
            "agent_id": agent_id,
        }
        for attempt in range(60):
            response = await client.post(
                f"{settings.librechat_native_url}/api/agents/chat", headers=headers, json=request_payload
            )
            if response.status_code != 429:
                break
            retry_after = response.headers.get("retry-after")
            await asyncio.sleep(float(retry_after) if retry_after else min(5 + attempt, 30))
        response.raise_for_status()
        stream_id = response.json().get("streamId")
        if not stream_id:
            raise RuntimeError("LibreChat native runtime returned no stream ID")
        investigation_id = user_prompt.split("Investigation ID: ", 1)[1].splitlines()[0].strip()
        for _ in range(450):
            await asyncio.sleep(2)
            status = await client.get(
                f"{settings.librechat_native_url}/api/agents/chat/status/{stream_id}", headers=headers
            )
            status.raise_for_status()
            if status.json().get("active"):
                continue
            latest = latest_investigation(investigation_id)
            if latest and latest["status"] == "completed":
                return latest.get("final_result") or ""
            raise RuntimeError(f"LibreChat native workflow ended without Finalizer publication (stream {stream_id})")
    raise RuntimeError(f"LibreChat native workflow timed out (stream {stream_id})")


def parse_agent_artifact(handoff: str) -> dict[str, Any]:
    """Parse a model handoff, tolerating only redundant closing delimiters.

    The persisted/downstream contract remains valid JSON.  A model occasionally
    emits one extra closing brace after an otherwise complete object; accepting
    only that suffix avoids throwing away a verified run while refusing prose,
    multiple objects, or any other wrapper.
    """
    try:
        parsed = json.loads(handoff)
    except json.JSONDecodeError:
        try:
            parsed, end = json.JSONDecoder().raw_decode(handoff.lstrip())
            suffix = handoff.lstrip()[end:].strip()
        except json.JSONDecodeError:
            return {}
        if suffix and not re.fullmatch(r"[}\]]+", suffix):
            return {}
    return parsed if isinstance(parsed, dict) else {}


def require_runtime_token(authorization: str | None) -> None:
    expected = f"Bearer {settings.investigation_runtime_token}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(401, "Invalid investigation runtime credentials")


def scoped_table(table: str) -> str:
    if not re.fullmatch(r"default\.[a-z][a-z0-9_]{0,62}", table):
        raise HTTPException(422, "Table must be a new, qualified table in default")
    return table


def ingest_source(investigation_id: str, table: str) -> dict[str, Any]:
    table = scoped_table(table)
    source = source_record(investigation_id)
    before = ch().query(f"SELECT count() FROM {table}").result_rows[0][0]
    if before:
        raise ValueError("Ingestion target is not empty; create a new investigation-scoped base table")
    parsed = urlparse(settings.clickhouse_dsn if "://" in settings.clickhouse_dsn else f"https://{settings.clickhouse_dsn}")
    endpoint = f"{parsed.scheme}://{parsed.netloc}/"
    sql = (f"INSERT INTO {table} SETTINGS input_format_skip_unknown_fields=1, "
           "input_format_defaults_for_omitted_fields=1 FORMAT JSONEachRow")
    # This is a server-to-server streaming request. Neither the agent nor the
    # model context receives an event body or a storage credential.
    with httpx.Client(timeout=httpx.Timeout(900.0, connect=30.0), auth=(settings.clickhouse_username, settings.clickhouse_password)) as client:
        response = client.post(endpoint, params={"query": sql}, content=blob_lines(source["events_blob_uri"]))
        response.raise_for_status()
    after = ch().query(f"SELECT count() FROM {table}").result_rows[0][0]
    return {"table": table, "source_sha256": source["events_sha256"], "source_rows": profile_ndjson_blob(source["events_blob_uri"])["source_rows"],
            "accepted_rows": after - before, "rejected_rows": 0, "format": "JSONEachRow"}


@app.post("/internal/investigations/{investigation_id}/metadata")
async def runtime_metadata(investigation_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_runtime_token(authorization)
    source = source_record(investigation_id)
    return {"investigation_id": investigation_id, "feature_key": source.get("feature_key") or None,
            "events": {key: source[f"events_{key}"] for key in ("filename", "bytes", "sha256")},
            "spec": {key: source[f"spec_{key}"] for key in ("filename", "bytes", "sha256")}}


@app.post("/internal/investigations/{investigation_id}/profile")
async def runtime_profile(investigation_id: str, payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_runtime_token(authorization)
    fields = payload.get("fields", [])
    if not isinstance(fields, list) or len(fields) > 50 or not all(isinstance(value, str) for value in fields):
        raise HTTPException(422, "fields must be at most 50 strings")
    return await asyncio.to_thread(profile_ndjson_blob, source_record(investigation_id)["events_blob_uri"], fields)


@app.post("/internal/investigations/{investigation_id}/peek")
async def runtime_peek(investigation_id: str, payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_runtime_token(authorization)
    events = payload.get("event_values", [])
    fields = payload.get("contains_fields", [])
    limit = payload.get("limit", 10)
    if not isinstance(events, list) or not isinstance(fields, list) or not isinstance(limit, int) or limit < 1 or limit > 20:
        raise HTTPException(422, "Invalid bounded peek request")
    try:
        return await asyncio.to_thread(peek_ndjson_blob, source_record(investigation_id)["events_blob_uri"], set(events), set(fields), limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/internal/investigations/{investigation_id}/spec")
async def runtime_spec(investigation_id: str, payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_runtime_token(authorization)
    offset = payload.get("offset_bytes", 0)
    length = payload.get("max_bytes", 16384)
    if not isinstance(offset, int) or offset < 0 or not isinstance(length, int) or not 1 <= length <= 16384:
        raise HTTPException(422, "Invalid bounded specification read")
    source = source_record(investigation_id)
    content = source_blob(source["spec_blob_uri"]).download_blob(offset=offset, length=length).readall().decode("utf-8", errors="replace")
    return {"offset_bytes": offset, "returned_bytes": len(content.encode()), "content": content}


@app.post("/internal/investigations/{investigation_id}/ingest")
async def runtime_ingest(investigation_id: str, payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_runtime_token(authorization)
    table = payload.get("table")
    if not isinstance(table, str):
        raise HTTPException(422, "table is required")
    try:
        return await asyncio.to_thread(ingest_source, investigation_id, table)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(422, f"ClickHouse ingestion failed: {exc.response.text[:1000]}") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/internal/investigations/{investigation_id}/state")
async def runtime_state(investigation_id: str, payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_runtime_token(authorization)
    artifact = payload.get("artifact")
    if not isinstance(artifact, dict) or len(json.dumps(artifact)) > 100_000:
        raise HTTPException(422, "A compact JSON artifact is required")
    result = json.dumps(artifact, separators=(",", ":"), ensure_ascii=False)
    append_agent_status(investigation_id, "instrumentation-agent", "completed", "Instrumentation state persisted", result=result)
    # State persistence is the durable instrumentation boundary. Keep the
    # overall investigation running until the isolated Analytics chain and
    # Finalizer have completed.
    append_agent_status(investigation_id, "analytics-agent", "queued", "Verified instrumentation handoff ready", result=result)
    append_agent_status(investigation_id, "context-agent", "queued", "Awaiting Analytics handoff")
    append_investigation(investigation_id, "running", "instrumentation-agent", "Instrumentation persisted; preparing strict Analytics input")
    return {"persisted": True, "completed": True, "next_agent": "analytics-agent", "investigation_id": investigation_id}


@app.post("/internal/investigations/{investigation_id}/finalizer")
async def persist_finalizer_envelope(investigation_id: str, payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Finalizer-only publication boundary for the UI response."""
    require_runtime_token(authorization)
    envelope = payload.get("envelope")
    if not isinstance(envelope, dict) or len(json.dumps(envelope, ensure_ascii=False)) > 500_000:
        raise HTTPException(422, "A canonical Finalizer envelope no larger than 500 KiB is required")
    latest = latest_investigation(investigation_id)
    if not latest:
        raise HTTPException(404, "Unknown investigation")
    result_id = await asyncio.to_thread(persist_finalizer_result, investigation_id, int(latest["revision"]) + 1, envelope)
    rendered = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    append_agent_status(investigation_id, "analytics-agent", "completed", "Aggregate evidence and independent review completed")
    append_agent_status(investigation_id, "context-agent", "completed", "Context stage completed before Finalizer delivery")
    append_agent_status(investigation_id, "finalizer-agent", "completed", "Finalizer response published", result=rendered)
    append_investigation(investigation_id, "completed", "finalizer-agent", f"Finalizer response {result_id} ready for the Input Page", final_result=rendered)
    return {"published": True, "result_id": result_id, "investigation_id": investigation_id}


async def process_investigation(investigation_id: str, already_claimed: bool = False) -> None:
    if investigation_id in running_investigations and not already_claimed:
        return
    investigation = latest_investigation(investigation_id)
    if not investigation or investigation["status"] != "queued":
        if already_claimed:
            running_investigations.discard(investigation_id)
        return
    running_investigations.add(investigation_id)
    try:
        for agent in AGENTS:
            append_agent_status(investigation_id, agent, "queued", "Managed by the LibreChat workflow")
        append_investigation(investigation_id, "running", "instrumentation-agent", "LibreChat workflow is running")
        append_agent_status(investigation_id, "instrumentation-agent", "running", "LibreChat runtime started")
        try:
            prompt = (
                f"Investigation ID: {investigation_id}\n"
                f"Feature key: {source_record(investigation_id).get('feature_key') or 'not supplied'}\n"
                f"Use new investigation-scoped ClickHouse object names in the `default` database beginning with `inv_{investigation_id.replace('-', '')}_`; never reuse an existing table.\n"
                "Run the complete end-to-end Supervisor workflow through Instrumentation, Analytics, Context, and Finalizer. "
                "Spawn each configured subagent sequentially and do not stop after Instrumentation. The Instrumentation child must start with the investigation-data runtime tool "
                "to retrieve source metadata, read the bounded specification, and profile/peek the NDJSON. "
                "Do not request source URLs or event-file contents in chat. Create and validate base schema "
                "with the ClickHouse tool, invoke the investigation-data ingestion tool for each base table, "
                "then create and validate justified MVs and aggregations. Persist the final compact JSON "
                "handoff using the investigation-data state tool before handing it to Analytics."
            )
            workflow_result = await run_agent(settings.librechat_workflow_agent_id, prompt)
        except Exception as exc:
            if (latest := latest_investigation(investigation_id)) and latest["status"] == "completed":
                return
            persisted = ch().query(
                "SELECT argMax(result, revision) FROM agent.investigation_agent_status "
                "WHERE investigation_id = {id:UUID} AND agent_name = 'instrumentation-agent' "
                "AND status = 'completed'",
                parameters={"id": investigation_id},
            ).result_rows
            persisted_result = str(persisted[0][0]) if persisted and persisted[0][0] else ""
            if persisted_result:
                append_agent_status(
                    investigation_id,
                    "finalizer-agent",
                    "blocked",
                    "Workflow failed after canonical instrumentation persistence",
                    result=persisted_result,
                    error_message=str(exc)[:4000],
                )
                append_investigation(
                    investigation_id,
                    "blocked",
                    "finalizer-agent",
                    "Workflow failed after instrumentation; canonical JSON preserved",
                    final_result=persisted_result,
                    error_message=str(exc)[:4000],
                )
                return
            error = str(exc)[:4000]
            append_agent_status(investigation_id, "instrumentation-agent", "failed", "LibreChat workflow failed", error_message=error)
            append_investigation(investigation_id, "failed", "instrumentation-agent", "LibreChat workflow failed", error_message=error)
            return
        if (latest := latest_investigation(investigation_id)) and latest["status"] == "completed":
            return
        persisted = ch().query(
            "SELECT argMax(result, revision) FROM agent.investigation_agent_status "
            "WHERE investigation_id = {id:UUID} AND agent_name = 'instrumentation-agent' "
            "AND status = 'completed'",
            parameters={"id": investigation_id},
        ).result_rows
        persisted_result = str(persisted[0][0]) if persisted and persisted[0][0] else ""
        canonical_result = persisted_result or workflow_result
        append_agent_status(
            investigation_id,
            "finalizer-agent",
            "blocked",
            "End-to-end workflow returned without Finalizer delivery",
            result=canonical_result,
        )
        append_investigation(
            investigation_id,
            "blocked",
            "finalizer-agent",
            "End-to-end workflow did not publish a Finalizer response",
            final_result=canonical_result,
        )
    finally:
        running_investigations.discard(investigation_id)


async def queue_watcher() -> None:
    while True:
        if not running_investigations:
            ids = await asyncio.to_thread(lambda: ch().query("""
                SELECT investigation_id FROM agent.investigations GROUP BY investigation_id
                HAVING argMax(status, revision) = 'queued'
                ORDER BY min(created_at)
                LIMIT 1
            """).result_rows)
            if ids:
                investigation_id = str(ids[0][0])
                running_investigations.add(investigation_id)
                asyncio.create_task(process_investigation(investigation_id, already_claimed=True))
        await asyncio.sleep(settings.poll_interval_seconds)


@app.on_event("startup")
async def startup() -> None:
    await asyncio.to_thread(ensure_container)
    if settings.workflow_worker_enabled:
        await asyncio.to_thread(init_schema)
        asyncio.create_task(queue_watcher())


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/demo", include_in_schema=False)
async def demo_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Liveness endpoint for the reverse-proxy deployment check."""
    return {"status": "ok"}


@app.post("/api/investigations", status_code=201)
async def create_investigation(events: UploadFile = File(...), spec: UploadFile = File(...),
                               feature_key: str | None = Form(default=None)) -> dict[str, str]:
    if feature_key is not None and not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", feature_key):
        raise HTTPException(422, "feature_key must contain lowercase letters, digits, hyphens, or underscores")
    if events.filename != "events.ndjson" or spec.filename != "spec.md":
        raise HTTPException(422, "Upload files named exactly events.ndjson and spec.md")
    investigation_id = str(uuid.uuid4())
    events_meta = await save_upload(investigation_id, events, "events.ndjson")
    try:
        spec_meta = await save_upload(investigation_id, spec, "spec.md")
    except Exception:
        await asyncio.gather(asyncio.to_thread(delete_blob, events_meta["uri"]), return_exceptions=True)
        raise
    timestamp = now()
    try:
        insert_investigation({"investigation_id": investigation_id, "feature_key": feature_key or "", "revision": 1, "created_at": timestamp, "updated_at": timestamp,
                              "events_blob_uri": events_meta["uri"], "events_filename": events_meta["filename"], "events_bytes": events_meta["bytes"], "events_sha256": events_meta["sha256"],
                              "spec_blob_uri": spec_meta["uri"], "spec_filename": spec_meta["filename"], "spec_bytes": spec_meta["bytes"], "spec_sha256": spec_meta["sha256"],
                              "status": "queued", "current_agent": "instrumentation-agent", "progress": "Waiting to start", "final_result": "", "error_message": ""})
        for agent in AGENTS:
            append_agent_status(investigation_id, agent, "queued", "Waiting for prior stage")
    except Exception:
        await asyncio.gather(*(asyncio.to_thread(delete_blob, item["uri"]) for item in (events_meta, spec_meta)), return_exceptions=True)
        raise
    # The durable workflow runner observes this append-only queued state.  Do
    # not execute LibreChat from the HTTP request/web process.
    return {"id": investigation_id, "status_url": f"/investigations/{investigation_id}"}


@app.get("/api/investigations/{investigation_id}")
async def investigation_status(investigation_id: uuid.UUID) -> dict[str, Any]:
    item = await asyncio.to_thread(latest_investigation, str(investigation_id))
    if not item:
        raise HTTPException(404, "Investigation not found")
    item["agents"] = await asyncio.to_thread(agent_states, str(investigation_id))
    return item


@app.get("/api/schema-history/{feature_key}")
async def schema_history(feature_key: str, logical_role: str | None = None, limit: int = 100) -> dict[str, Any]:
    """Bounded physical-schema history; exact DDL stays available by version ID."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", feature_key):
        raise HTTPException(422, "Invalid feature key")
    if logical_role is not None and (not logical_role or len(logical_role) > 128):
        raise HTTPException(422, "Invalid logical role")
    rows = ch().query("""
        SELECT schema_version_id, previous_schema_version_id, logical_role, object_kind,
               database_name, object_name, investigation_id, observed_at,
               verification_status, normalized_fingerprint
        FROM agent.schema_versions
        WHERE feature_key = {feature_key:String}
          AND ({logical_role:String} = '' OR logical_role = {logical_role:String})
        ORDER BY observed_at DESC LIMIT {limit:UInt16}
    """, parameters={"feature_key": feature_key, "logical_role": logical_role or "", "limit": max(1, min(limit, 200))}).named_results()
    return {"feature_key": feature_key, "versions": list(rows)}


@app.get("/api/schema-versions/{schema_version_id}/diff")
async def schema_version_diff(schema_version_id: uuid.UUID) -> dict[str, Any]:
    rows = ch().query("""
        SELECT schema_change_id, previous_schema_version_id, logical_role, operation,
               impact, before_json, after_json, investigation_id, evidence_query_ids, observed_at
        FROM agent.schema_changes WHERE schema_version_id = {id:UUID}
        ORDER BY observed_at, schema_change_id LIMIT 200
    """, parameters={"id": str(schema_version_id)}).named_results()
    return {"schema_version_id": str(schema_version_id), "changes": list(rows)}


@app.get("/api/context-versions/{version_number}/diff")
async def context_version_diff(version_number: int) -> dict[str, Any]:
    if version_number < 1:
        raise HTTPException(422, "version_number must be positive")
    rows = ch().query("""
        SELECT context_change_id, context_id, previous_context_id, domain, object_id,
               operation, before_json, after_json, reason, evidence_refs, confidence,
               review_required, schema_version_ids, created_at
        FROM agent.context_changes WHERE version_number = {version:UInt64}
        ORDER BY domain, object_id LIMIT 500
    """, parameters={"version": version_number}).named_results()
    return {"version_number": version_number, "changes": list(rows)}


@app.get("/investigations/{investigation_id}", include_in_schema=False)
async def investigation_page(investigation_id: uuid.UUID) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
