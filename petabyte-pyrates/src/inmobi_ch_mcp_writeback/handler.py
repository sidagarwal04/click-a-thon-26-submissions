"""Minimal MCP (Streamable HTTP) Lambda: close anomaly investigations in ClickHouse."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import uuid
from typing import Any

import urllib.error
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "")
CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "")
MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "inmobi-ch-mcp-writeback"
SERVER_VERSION = "1.2.0"
DISPOSITION_VALUES = frozenset({"confirmed", "false_positive", "inconclusive", "pending"})
DISPOSITION_ALIASES: dict[str, str] = {
    "confirmed": "confirmed",
    "confirm": "confirmed",
    "valid": "confirmed",
    "true": "confirmed",
    "true_anomaly": "confirmed",
    "real": "confirmed",
    "real_anomaly": "confirmed",
    "false_positive": "false_positive",
    "falsepositive": "false_positive",
    "false positive": "false_positive",
    "false-positive": "false_positive",
    "invalid": "false_positive",
    "noise": "false_positive",
    "artifact": "false_positive",
    "inconclusive": "inconclusive",
    "unknown": "inconclusive",
    "unclear": "inconclusive",
    "insufficient": "inconclusive",
    "insufficient_evidence": "inconclusive",
}
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

CLOSE_TOOL = {
    "name": "close_anomaly_investigation",
    "description": (
        "Mark an anomaly investigation complete in gold.metric_anomalies: "
        "sets status=closed, disposition (RCA verdict), rca_description, and evidence_json."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "anomaly_id": {
                "type": "string",
                "description": "UUID of the anomaly row in gold.metric_anomalies",
            },
            "disposition": {
                "type": "string",
                "enum": ["confirmed", "false_positive", "inconclusive"],
                "description": (
                    "REQUIRED. Exact enum string only (underscores, lowercase): "
                    "'confirmed' | 'false_positive' | 'inconclusive'. "
                    "Do NOT use: valid, invalid, true, false positive, closed, pending."
                ),
            },
            "rca_description": {
                "type": "string",
                "description": "Plain-language RCA summary",
            },
            "evidence_json": {
                "type": "string",
                "description": "JSON string with investigation evidence",
            },
        },
        "required": ["anomaly_id", "disposition"],
    },
}


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "authorization,content-type,mcp-session-id,accept",
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
    }


def _http_response(status: int, body: str, extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", **_cors_headers()}
    if extra_headers:
        headers.update(extra_headers)
    return {"statusCode": status, "headers": headers, "body": body}


def _authorized(event: dict[str, Any]) -> bool:
    if not MCP_AUTH_TOKEN:
        return True
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    auth = headers.get("authorization", "")
    if auth == f"Bearer {MCP_AUTH_TOKEN}":
        return True
    return headers.get("x-mcp-auth-token") == MCP_AUTH_TOKEN


def _escape_sql(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _normalize_disposition(raw: str) -> str | None:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    return DISPOSITION_ALIASES.get(key)


def _ch_execute(sql: str) -> str:
    if not CLICKHOUSE_HOST:
        raise RuntimeError("CLICKHOUSE_HOST is not configured")
    token = base64.b64encode(f"{CLICKHOUSE_USER}:{CLICKHOUSE_PASSWORD}".encode()).decode()
    req = urllib.request.Request(
        f"https://{CLICKHOUSE_HOST}:8443",
        data=sql.encode(),
        method="POST",
        headers={"Authorization": f"Basic {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode() if exc.fp else str(exc)
        raise RuntimeError(f"ClickHouse HTTP {exc.code}: {detail[:2000]}") from exc


def _close_anomaly(arguments: dict[str, Any]) -> dict[str, Any]:
    anomaly_id = str(arguments.get("anomaly_id", "")).strip()
    if not UUID_RE.match(anomaly_id):
        return {"error": "anomaly_id must be a valid UUID"}

    disposition = _normalize_disposition(str(arguments.get("disposition", "")))
    if disposition is None or disposition not in DISPOSITION_VALUES - {"pending"}:
        return {
            "error": (
                "disposition must be exactly one of: confirmed, false_positive, "
                "inconclusive (lowercase, use underscore in false_positive)"
            )
        }

    rca_description = str(arguments.get("rca_description", "") or "")
    evidence = arguments.get("evidence_json", {})
    if isinstance(evidence, dict):
        evidence_json = json.dumps(evidence, ensure_ascii=False)
    else:
        evidence_json = str(evidence or "")
        if evidence_json:
            try:
                json.loads(evidence_json)
            except json.JSONDecodeError as exc:
                return {"error": f"evidence_json must be valid JSON: {exc}"}

    sql = (
        "ALTER TABLE gold.metric_anomalies UPDATE "
        f"status = 'closed', "
        f"disposition = '{disposition}', "
        f"rca_description = '{_escape_sql(rca_description)}', "
        f"evidence_json = '{_escape_sql(evidence_json)}', "
        f"investigated_at = now64(3) "
        f"WHERE anomaly_id = '{anomaly_id}'"
    )
    _ch_execute(sql)
    return {
        "anomaly_id": anomaly_id,
        "status": "closed",
        "disposition": disposition,
        "rca_description": rca_description,
        "evidence_json": evidence_json,
    }


def _tool_result(payload: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": is_error,
    }


def _handle_rpc(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": [CLOSE_TOOL]},
        }

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name != CLOSE_TOOL["name"]:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": _tool_result({"error": f"unknown tool: {name}"}, is_error=True),
            }
        try:
            outcome = _close_anomaly(arguments)
            if "error" in outcome:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": _tool_result(outcome, is_error=True),
                }
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": _tool_result(outcome),
            }
        except Exception as exc:
            logger.exception("close_anomaly_investigation failed")
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": _tool_result({"error": str(exc)}, is_error=True),
            }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def _parse_body(event: dict[str, Any]) -> Any:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    if not raw.strip():
        return None
    return json.loads(raw)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "POST"
    ).upper()

    if method == "OPTIONS":
        return _http_response(204, "")

    if method == "GET":
        return _http_response(
            200,
            json.dumps(
                {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                    "transport": "streamable-http",
                    "tools": [CLOSE_TOOL["name"]],
                }
            ),
        )

    if not _authorized(event):
        return _http_response(401, json.dumps({"error": "unauthorized"}))

    try:
        payload = _parse_body(event)
    except json.JSONDecodeError:
        return _http_response(400, json.dumps({"error": "invalid JSON body"}))

    if payload is None:
        return _http_response(400, json.dumps({"error": "empty body"}))

    messages = payload if isinstance(payload, list) else [payload]
    responses: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        response = _handle_rpc(message)
        if response is not None:
            responses.append(response)

    session_id = str(uuid.uuid4())
    extra = {"Mcp-Session-Id": session_id}

    if not responses:
        return _http_response(202, "", extra)

    if len(responses) == 1:
        return _http_response(200, json.dumps(responses[0]), extra)

    return _http_response(200, json.dumps(responses), extra)
