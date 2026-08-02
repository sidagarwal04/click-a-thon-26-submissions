"""Restricted MCP interface for immutable Context and schema history."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import clickhouse_connect
from fastmcp import FastMCP

MODEL = "text-embedding-3-small"
DIMENSIONS = 1536
DEFAULT_OBJECT_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
FEATURE_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
CONTEXT_DOMAINS = ("business", "features", "entities", "relationships", "tables", "events", "columns",
                   "metrics", "dimensions", "known_issues", "verified_findings", "instrumentation_limitations",
                   "contradictions", "open_questions")
mcp = FastMCP("atlys-context-store")


def client():
    endpoint = os.environ["CLICKHOUSE_ENDPOINT"]
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    return clickhouse_connect.get_client(host=parsed.hostname, port=parsed.port or 8443,
        username=os.environ["CLICKHOUSE_USER"], password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=parsed.scheme == "https", database="agent")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(compact_json(value).encode()).hexdigest()


def embed(texts: list[str]) -> list[list[float]]:
    request = Request("https://api.openai.com/v1/embeddings", method="POST",
        data=json.dumps({"model": MODEL, "input": texts, "encoding_format": "float"}).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"})
    with urlopen(request, timeout=60) as response:
        vectors = [item["embedding"] for item in json.load(response)["data"]]
    if len(vectors) != len(texts) or any(len(vector) != DIMENSIONS for vector in vectors):
        raise ValueError("Embedding response violates the 1536-dimension contract")
    return vectors


def sections(markdown: str) -> list[tuple[str, str]]:
    result = []
    for part in re.split(r"(?=^## )", markdown, flags=re.MULTILINE):
        if part.strip():
            match = re.match(r"##\s+(.+)", part)
            result.append(((match.group(1) if match else "metadata").strip(), part.strip()))
    return result


def safe_uuid(value: Any) -> str | None:
    try:
        return str(uuid.UUID(str(value))) if value else None
    except (TypeError, ValueError):
        return None


def semantic_objects(snapshot: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Canonicalize the context contract by its required stable object IDs."""
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for domain in CONTEXT_DOMAINS:
        value = snapshot.get(domain)
        if value is None:
            continue
        values = [value] if domain == "business" and isinstance(value, dict) else value
        if not isinstance(values, list):
            raise ValueError(f"Context domain {domain} must be an object or array")
        for item in values:
            if not isinstance(item, dict):
                raise ValueError(f"Context domain {domain} contains a non-object")
            object_id = "business" if domain == "business" else item.get("id")
            if not isinstance(object_id, str) or not object_id:
                raise ValueError(f"Context domain {domain} requires a stable id")
            key = (domain, object_id)
            if key in result:
                raise ValueError(f"Duplicate context object {domain}:{object_id}")
            result[key] = item
    return result


def context_diff(previous: dict[str, Any] | None, current: dict[str, Any], reasons: list[dict[str, Any]] | None,
                 schema_version_ids: list[str] | None) -> list[dict[str, Any]]:
    before, after = semantic_objects(previous or {}), semantic_objects(current)
    reason_index = {(str(item.get("domain")), str(item.get("object_id"))): item
                    for item in (reasons or []) if isinstance(item, dict)}
    changes = []
    for domain, object_id in sorted(set(before) | set(after)):
        old, new = before.get((domain, object_id)), after.get((domain, object_id))
        if old is None:
            operation = "add"
        elif new is None:
            operation = "deprecate"
        elif compact_json(old) != compact_json(new):
            operation = "supersede" if str(new.get("status", "")) == "superseded" else "modify"
        else:
            operation = "no_change"
        supplied = reason_index.get((domain, object_id), {})
        evidence = supplied.get("evidence_refs") or (new or old or {}).get("evidence_refs") or []
        if not isinstance(evidence, list):
            evidence = []
        confidence = supplied.get("confidence", (new or old or {}).get("confidence", 1.0))
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 1.0
        changes.append({"domain": domain, "object_id": object_id, "operation": operation,
                        "before": old or {}, "after": new or {}, "reason": str(supplied.get("reason", "")),
                        "evidence_refs": [str(item) for item in evidence[:100]], "confidence": max(0.0, min(confidence, 1.0)),
                        "review_required": bool(supplied.get("review_required", False)),
                        "schema_version_ids": [str(item) for item in (schema_version_ids or [])[:100]]})
    return changes


def render_change_summary(changes: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for change in changes:
        counts[change["operation"]] = counts.get(change["operation"], 0) + 1
    return "; ".join(f"{count} {operation}" for operation, count in sorted(counts.items())) or "no semantic changes"


def normalized_ddl(ddl: str, object_roles: dict[str, str]) -> str:
    # Generated object names are investigation-scoped. Replace every supplied
    # physical name with its stable logical role before fingerprinting, while
    # keeping the original DDL in schema_versions.exact_ddl for audit.
    for object_name, logical_role in sorted(object_roles.items(), key=lambda item: len(item[0]), reverse=True):
        ddl = re.sub(rf"\b{re.escape(object_name)}\b", f"<{logical_role}>", ddl)
    ddl = re.sub(r"\binv_[0-9a-f]{32}_", "inv_<investigation>_", ddl)
    return re.sub(r"\s+", " ", ddl).strip()


def optional_query(ch: Any, sql: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return list(ch.query(sql, parameters=parameters).named_results())
    except Exception:
        return []


def live_schema_snapshot(ch: Any, object_name: str, object_roles: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    table_rows = list(ch.query("""
        SELECT database, name, engine, engine_full, sorting_key, primary_key,
               partition_key, create_table_query
        FROM system.tables WHERE database = 'default' AND name = {name:String} LIMIT 1
    """, parameters={"name": object_name}).named_results())
    if not table_rows:
        raise ValueError(f"default.{object_name} was not found")
    table = table_rows[0]
    columns = list(ch.query("""
        SELECT position, name, type, default_kind, default_expression,
               compression_codec, comment
        FROM system.columns WHERE database = 'default' AND table = {name:String}
        ORDER BY position
    """, parameters={"name": object_name}).named_results())
    indexes = optional_query(ch, """
        SELECT name, type_full, expr, granularity
        FROM system.data_skipping_indices
        WHERE database = 'default' AND table = {name:String} ORDER BY name
    """, {"name": object_name})
    projections = optional_query(ch, """
        SELECT name, query FROM system.projections
        WHERE database = 'default' AND table = {name:String} ORDER BY name
    """, {"name": object_name})
    exact_ddl = str(table.get("create_table_query") or "")
    metadata = {"object": {"database": "default", "engine": table.get("engine", ""),
                "engine_full": table.get("engine_full", ""), "sorting_key": table.get("sorting_key", ""),
                "primary_key": table.get("primary_key", ""), "partition_key": table.get("partition_key", "")},
                "ddl_normalized": normalized_ddl(exact_ddl, object_roles), "columns": columns,
                "indexes": indexes, "projections": projections}
    return metadata, columns, exact_ddl


def schema_change(previous: dict[str, Any] | None, current: dict[str, Any]) -> tuple[str, str]:
    if previous is None:
        return "add", "additive"
    if compact_json(previous) == compact_json(current):
        return "no_change", "no_change"
    old_object, new_object = previous.get("object", {}), current.get("object", {})
    for key in ("engine", "engine_full", "sorting_key", "primary_key", "partition_key"):
        if old_object.get(key) != new_object.get(key):
            return "key_change" if key.endswith("key") else "engine_change", "breaking"
    if (" TTL " in previous.get("ddl_normalized", "").upper()) != (" TTL " in current.get("ddl_normalized", "").upper()):
        return "ttl_change", "breaking"
    old_columns = {str(column["name"]): column for column in previous.get("columns", [])}
    new_columns = {str(column["name"]): column for column in current.get("columns", [])}
    if set(new_columns) - set(old_columns) and not (set(old_columns) - set(new_columns)):
        return "add_column", "additive"
    if set(old_columns) - set(new_columns):
        return "remove_column", "review_required"
    if any(compact_json(old_columns[name]) != compact_json(new_columns[name]) for name in set(old_columns) & set(new_columns)):
        return "column_change", "breaking"
    if old_object.get("engine") == "MaterializedView" or new_object.get("engine") == "MaterializedView":
        return "mv_query_change", "breaking"
    return "modify", "review_required"


@mcp.tool()
def get_latest_context() -> dict:
    """Return only the newest published Context Store version and its full snapshot."""
    rows = list(client().query("""SELECT context_id, version_number, published_at, content_sha256,
        snapshot_markdown, snapshot_json, change_summary FROM business_logic_versions
        WHERE status = 'published' ORDER BY version_number DESC LIMIT 1""").named_results())
    return rows[0] if rows else {"status": "empty"}


@mcp.tool()
def search_context(query: str, limit: int = 8) -> list[dict]:
    """Find up to 12 relevant sections in the newest published context version."""
    if not query.strip():
        raise ValueError("query is required")
    limit = max(1, min(limit, 12))
    rows = list(client().query("""WITH {embedding:Array(Float32)} AS query_embedding
        SELECT chunk_id, version_number, section_type, entity_type, entity_id, chunk_text,
               confidence, cosineDistance(embedding, query_embedding) AS distance
        FROM business_logic_embeddings_v1
        WHERE context_id = (SELECT context_id FROM business_logic_versions
                            WHERE status = 'published' ORDER BY version_number DESC LIMIT 1)
        ORDER BY distance LIMIT {limit:UInt8}""",
        parameters={"embedding": embed([query])[0], "limit": limit}).named_results())
    return rows


@mcp.tool()
def refresh_schema_catalogue(feature_key: str, objects: list[dict[str, Any]], investigation_id: str | None = None,
                             evidence_query_ids: list[str] | None = None) -> dict:
    """Snapshot scoped live default-schema objects and append a deterministic physical drift record."""
    if not FEATURE_KEY.fullmatch(feature_key):
        raise ValueError("feature_key must contain lowercase letters, digits, hyphens, or underscores")
    if not 1 <= len(objects) <= 40:
        raise ValueError("objects must contain between 1 and 40 logical objects")
    investigation = safe_uuid(investigation_id)
    if investigation_id and not investigation:
        raise ValueError("investigation_id must be a UUID")
    role_by_name: dict[str, str] = {}
    for item in objects:
        if not isinstance(item, dict) or not isinstance(item.get("logical_role"), str) or not isinstance(item.get("name"), str):
            raise ValueError("Each object requires logical_role and name")
        name = item["name"]
        if not name.startswith("default.") or not DEFAULT_OBJECT_NAME.fullmatch(name.split(".", 1)[1]):
            raise ValueError("Object names must be qualified default.<safe_name>")
        role_by_name[name.split(".", 1)[1]] = item["logical_role"]
    ch, observed_at, output = client(), utcnow(), []
    for item in objects:
        if not isinstance(item, dict):
            raise ValueError("Each object must be an object")
        logical_role, name = item.get("logical_role"), item.get("name")
        object_kind = str(item.get("object_kind") or "table")
        if not isinstance(logical_role, str) or not logical_role or len(logical_role) > 128:
            raise ValueError("Each object requires a logical_role of at most 128 characters")
        if not isinstance(name, str) or not name.startswith("default.") or not DEFAULT_OBJECT_NAME.fullmatch(name.split(".", 1)[1]):
            raise ValueError("Object names must be qualified default.<safe_name>")
        physical_name = name.split(".", 1)[1]
        metadata, columns, exact_ddl = live_schema_snapshot(ch, physical_name, role_by_name)
        previous_rows = list(ch.query("""
            SELECT schema_version_id, metadata_json FROM schema_versions
            WHERE feature_key = {feature_key:String} AND logical_role = {logical_role:String}
              AND verification_status = 'verified'
            ORDER BY observed_at DESC LIMIT 1
        """, parameters={"feature_key": feature_key, "logical_role": logical_role}).named_results())
        previous_id = str(previous_rows[0]["schema_version_id"]) if previous_rows else None
        previous = json.loads(previous_rows[0]["metadata_json"]) if previous_rows else None
        operation, impact = schema_change(previous, metadata)
        version_id = str(uuid.uuid4())
        ch.insert("schema_versions", [[version_id, previous_id, feature_key, logical_role, object_kind, "default", physical_name,
                   investigation, observed_at, "verified", digest(metadata), exact_ddl, compact_json(metadata), evidence_query_ids or []]],
                  column_names=["schema_version_id", "previous_schema_version_id", "feature_key", "logical_role", "object_kind",
                                "database_name", "object_name", "investigation_id", "observed_at", "verification_status",
                                "normalized_fingerprint", "exact_ddl", "metadata_json", "evidence_query_ids"])
        column_rows = [[version_id, int(column.get("position") or 0), str(column.get("name") or ""), str(column.get("type") or ""),
                        str(column.get("default_kind") or ""), str(column.get("default_expression") or ""),
                        str(column.get("compression_codec") or ""), str(column.get("comment") or ""), digest(column)] for column in columns]
        if column_rows:
            ch.insert("schema_columns", column_rows, column_names=["schema_version_id", "position", "column_name", "column_type",
                      "default_kind", "default_expression", "codec_expression", "comment", "column_fingerprint"])
        ch.insert("schema_changes", [[str(uuid.uuid4()), version_id, previous_id, feature_key, logical_role, operation, impact,
                   compact_json(previous or {}), compact_json(metadata), investigation, evidence_query_ids or [], observed_at]],
                  column_names=["schema_change_id", "schema_version_id", "previous_schema_version_id", "feature_key", "logical_role",
                                "operation", "impact", "before_json", "after_json", "investigation_id", "evidence_query_ids", "observed_at"])
        output.append({"logical_role": logical_role, "name": name, "schema_version_id": version_id,
                       "previous_schema_version_id": previous_id, "operation": operation, "impact": impact,
                       "normalized_fingerprint": digest(metadata)})
    return {"feature_key": feature_key, "verification_status": "verified", "schema_versions": output}


@mcp.tool()
def get_schema_history(feature_key: str, logical_role: str = "", limit: int = 20) -> list[dict]:
    """Return a bounded schema-version timeline for one feature and optional logical object."""
    if not FEATURE_KEY.fullmatch(feature_key):
        raise ValueError("Invalid feature_key")
    limit = max(1, min(limit, 100))
    return list(client().query("""
        SELECT schema_version_id, previous_schema_version_id, logical_role, object_kind, database_name,
               object_name, investigation_id, observed_at, normalized_fingerprint
        FROM schema_versions WHERE feature_key = {feature_key:String}
          AND ({logical_role:String} = '' OR logical_role = {logical_role:String})
        ORDER BY observed_at DESC LIMIT {limit:UInt8}
    """, parameters={"feature_key": feature_key, "logical_role": logical_role, "limit": limit}).named_results())


@mcp.tool()
def get_schema_diff(schema_version_id: str) -> list[dict]:
    """Return the persisted bounded physical diff for one schema snapshot version."""
    version = safe_uuid(schema_version_id)
    if not version:
        raise ValueError("schema_version_id must be a UUID")
    return list(client().query("""
        SELECT schema_change_id, previous_schema_version_id, logical_role, operation, impact,
               before_json, after_json, investigation_id, evidence_query_ids, observed_at
        FROM schema_changes WHERE schema_version_id = {id:UUID}
        ORDER BY observed_at, schema_change_id LIMIT 100
    """, parameters={"id": version}).named_results())


@mcp.tool()
def get_context_changelog(version_number: int = 0, limit: int = 100) -> list[dict]:
    """Return a bounded semantic changelog for a context version, or the latest changes when zero."""
    limit = max(1, min(limit, 500))
    ch = client()
    if version_number <= 0:
        rows = ch.query("SELECT max(version_number) FROM business_logic_versions WHERE status = 'published'").result_rows
        version_number = int(rows[0][0] or 0)
    if version_number <= 0:
        return []
    return list(ch.query("""
        SELECT context_change_id, context_id, previous_context_id, domain, object_id, operation,
               before_json, after_json, reason, evidence_refs, confidence, review_required,
               schema_version_ids, created_at
        FROM context_changes WHERE version_number = {version:UInt64}
        ORDER BY domain, object_id LIMIT {limit:UInt16}
    """, parameters={"version": version_number, "limit": limit}).named_results())


@mcp.tool()
def publish_context(markdown: str, snapshot_json: str, change_summary: str = "", effective_at: str | None = None,
                    query_ids: list[str] | None = None, change_reasons: list[dict[str, Any]] | None = None,
                    schema_version_ids: list[str] | None = None) -> dict:
    """Append a validated complete context version, semantic changelog, and embeddings without mutations."""
    if not markdown.strip():
        raise ValueError("markdown is required")
    try:
        snapshot = json.loads(snapshot_json)
    except json.JSONDecodeError as error:
        raise ValueError("snapshot_json must be valid JSON") from error
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_json must be an object")
    ch = client()
    prior_rows = list(ch.query("""SELECT context_id, version_number, snapshot_json FROM business_logic_versions
        WHERE status = 'published' ORDER BY version_number DESC LIMIT 1""").named_results())
    prior_snapshot = json.loads(prior_rows[0]["snapshot_json"]) if prior_rows else None
    changes = context_diff(prior_snapshot, snapshot, change_reasons, schema_version_ids)
    meaningful = [change for change in changes if change["operation"] != "no_change"]
    if prior_snapshot is not None and not meaningful:
        return {"status": "no_change", "version_number": int(prior_rows[0]["version_number"]),
                "context_id": str(prior_rows[0]["context_id"]), "change_summary": "no semantic changes"}
    context_id, version = str(uuid.uuid4()), (int(prior_rows[0]["version_number"]) + 1 if prior_rows else 1)
    previous_id = str(prior_rows[0]["context_id"]) if prior_rows else None
    timestamp = datetime.fromisoformat(effective_at.replace("Z", "+00:00")) if effective_at else utcnow()
    parts = sections(markdown)
    vectors = embed([text for _, text in parts])
    embedding_rows = [[context_id, version, str(uuid.uuid4()), ordinal, title.lower().replace(" ", "_"), "context_section", title,
             timestamp, None, "published", 1.0, hashlib.sha256(text.encode()).hexdigest(), text,
             compact_json({"embedding_model": MODEL}), vector]
            for ordinal, ((title, text), vector) in enumerate(zip(parts, vectors))]
    if embedding_rows:
        ch.insert("business_logic_embeddings_v1", embedding_rows, column_names=["context_id", "version_number", "chunk_id", "chunk_ordinal",
            "section_type", "entity_type", "entity_id", "valid_from", "valid_to", "status", "confidence", "content_sha256",
            "chunk_text", "metadata_json", "embedding"])
    rendered_summary = render_change_summary(changes)
    markdown_digest = hashlib.sha256(markdown.encode()).hexdigest()
    provenance = snapshot.get("provenance") if isinstance(snapshot.get("provenance"), dict) else {}
    source_run_id = safe_uuid(provenance.get("instrumentation_run_id") or provenance.get("analytics_run_id"))
    ch.insert("business_logic_versions", [[context_id, version, previous_id, "published", timestamp, utcnow(), markdown_digest,
        markdown, compact_json(snapshot), rendered_summary, source_run_id, query_ids or [], MODEL, DIMENSIONS, "context-agent"]], column_names=["context_id",
        "version_number", "previous_context_id", "status", "effective_at", "published_at", "content_sha256", "snapshot_markdown",
        "snapshot_json", "change_summary", "source_run_id", "source_query_ids", "embedding_model", "embedding_dimensions", "created_by"])
    change_rows = [[str(uuid.uuid4()), context_id, previous_id, version, change["domain"], change["object_id"], change["operation"],
                    compact_json(change["before"]), compact_json(change["after"]), change["reason"], change["evidence_refs"],
                    change["confidence"], change["review_required"], change["schema_version_ids"], utcnow()] for change in meaningful]
    if change_rows:
        ch.insert("context_changes", change_rows, column_names=["context_change_id", "context_id", "previous_context_id", "version_number",
                  "domain", "object_id", "operation", "before_json", "after_json", "reason", "evidence_refs", "confidence",
                  "review_required", "schema_version_ids", "created_at"])
    return {"status": "published", "context_id": context_id, "version_number": version, "chunks": len(embedding_rows),
            "content_sha256": markdown_digest, "change_summary": rendered_summary, "changes": len(meaningful)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
