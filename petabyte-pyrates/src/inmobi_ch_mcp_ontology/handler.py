"""Minimal MCP (Streamable HTTP) Lambda: return InMobi glossary ontology."""

from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
ONTOLOGY_PATH = Path(__file__).resolve().parent / "ontology.json"

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "inmobi-ch-mcp-ontology"
SERVER_VERSION = "1.1.0"
SERVER_INSTRUCTIONS = (
    "REQUIRED: The agent MUST call get_ontology as the first tool in every "
    "investigation, before any ClickHouse SELECT. Returns metrics, dimensions, "
    "decompositions, and query rules for gold.metrics_hourly."
)

GET_ONTOLOGY_TOOL = {
    "name": "get_ontology",
    "description": (
        "REQUIRED FIRST STEP — call before any ClickHouse query. Returns the "
        "authoritative InMobi RCA glossary: terms, relationships, dimensions, "
        "decompositions, and query rules for gold.metrics_hourly (v1.2)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
    },
    "annotations": {
        "title": "Load RCA ontology (call first)",
        "readOnlyHint": True,
    },
}

_ontology_cache: dict[str, Any] | None = None


def _load_ontology() -> dict[str, Any]:
    global _ontology_cache
    if _ontology_cache is None:
        if not ONTOLOGY_PATH.is_file():
            raise FileNotFoundError(f"ontology bundle missing: {ONTOLOGY_PATH}")
        with ONTOLOGY_PATH.open(encoding="utf-8") as handle:
            _ontology_cache = json.load(handle)
    return _ontology_cache


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
                "instructions": SERVER_INSTRUCTIONS,
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": [GET_ONTOLOGY_TOOL]},
        }

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        if name != GET_ONTOLOGY_TOOL["name"]:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": _tool_result({"error": f"unknown tool: {name}"}, is_error=True),
            }
        try:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": _tool_result(_load_ontology()),
            }
        except Exception as exc:
            logger.exception("get_ontology failed")
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
                    "tools": [GET_ONTOLOGY_TOOL["name"]],
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
