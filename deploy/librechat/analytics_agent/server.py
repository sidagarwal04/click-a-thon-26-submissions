#!/usr/bin/env python3
"""Private MCP adapter for the environment-only analytics runner."""

from __future__ import annotations

import base64
import json
import os
import subprocess
from typing import Any

from fastmcp import FastMCP

MAX_REQUEST_BYTES = 1_000_000
RUNNER = "/opt/atlys/analytics_runner.py"

mcp = FastMCP("Atlys Analytics Runner")


@mcp.tool
def run_analytics(request: dict[str, Any]) -> dict[str, Any]:
    """Run one bounded analytics action and return its single JSON response."""

    encoded_json = json.dumps(
        request, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded_json) > MAX_REQUEST_BYTES:
        return {
            "ok": False,
            "error": {
                "code": "request_too_large",
                "message": "request exceeds 1,000,000 bytes",
            },
            "status": None,
            "raw_rows_to_llm": 0,
        }

    child_env = os.environ.copy()
    child_env["ATLYS_REQUEST_B64"] = base64.b64encode(encoded_json).decode("ascii")
    try:
        completed = subprocess.run(
            ["python", RUNNER],
            env=child_env,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": {
                "code": "runner_timeout",
                "message": "analytics runner exceeded 45 seconds",
            },
            "status": "query_failure",
            "raw_rows_to_llm": 0,
        }

    stdout = completed.stdout.strip()
    if completed.returncode != 0 or not stdout:
        return {
            "ok": False,
            "error": {
                "code": "runner_failure",
                "message": "analytics runner did not return a JSON result",
            },
            "status": "agent_failure",
            "raw_rows_to_llm": 0,
        }
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": {
                "code": "runner_protocol_error",
                "message": "analytics runner returned invalid JSON",
            },
            "status": "agent_failure",
            "raw_rows_to_llm": 0,
        }
    if not isinstance(response, dict):
        return {
            "ok": False,
            "error": {
                "code": "runner_protocol_error",
                "message": "analytics runner response was not an object",
            },
            "status": "agent_failure",
            "raw_rows_to_llm": 0,
        }
    return response


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
