#!/usr/bin/env python3
"""End-to-end smoke test: CH detect/investigate + RCA MCP + LibreChat chat."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"


def load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def ok(msg: str) -> None:
    print(f"OK  {msg}")


def fail(msg: str) -> None:
    print(f"FAIL  {msg}", file=sys.stderr)


def test_engine() -> bool:
    from clickathon.investigate import investigate

    f = investigate("2026-06-23", narrate=True)
    seg = (f.get("diagnosis") or {}).get("segment")
    factor = (f.get("decomposition") or {}).get("primary_factor")
    narrative = f.get("narrative") or ""
    if factor != "fill_rate":
        fail(f"expected fill_rate, got {factor}")
        return False
    if "Android 15" not in str(seg):
        fail(f"expected Android 15 segment, got {seg}")
        return False
    if "Android 15" not in narrative and "fill" not in narrative.lower():
        fail(f"narrative missing key content: {narrative[:200]}")
        return False
    if "ResponseReasoningItem" in narrative:
        fail("narrative still contains reasoning stub")
        return False
    ok(f"engine investigate → {factor} / {seg}")
    print("--- narrative ---")
    print(narrative[:800])
    print("---------------")
    return True


def test_rca_mcp() -> bool:
    # Initialize session then call tool via JSON-RPC streamable HTTP is tricky;
    # hit health via TCP already known. Use engine path through MCP process locally.
    # Instead: POST initialize + tools/call if possible.
    url = "http://127.0.0.1:8001/mcp"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    with httpx.Client(timeout=120.0) as client:
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0.1"},
            },
        }
        r = client.post(url, headers=headers, json=init)
        if r.status_code >= 400:
            fail(f"MCP initialize HTTP {r.status_code}: {r.text[:300]}")
            return False
        session = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
        if session:
            headers["mcp-session-id"] = session
        # notifications/initialized
        client.post(
            url,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        call = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "investigate_day",
                "arguments": {"day": "2026-06-23", "include_narrative": False},
            },
        }
        r2 = client.post(url, headers=headers, json=call)
        text = r2.text
        if r2.status_code >= 400:
            fail(f"MCP tools/call HTTP {r2.status_code}: {text[:400]}")
            return False
        if "Android 15" not in text and "fill_rate" not in text:
            fail(f"MCP response missing expected RCA content: {text[:500]}")
            return False
        ok("rca-mcp investigate_day returned Android 15 / fill evidence")
        return True


def test_librechat(env: dict[str, str]) -> bool:
    base = os.environ.get("LIBRECHAT_URL", "http://localhost:3080").rstrip("/")
    email = env.get("LIBRECHAT_USER_EMAIL", "")
    password = env.get("LIBRECHAT_USER_PASSWORD", "")
    model = env.get("OPENAI_MODEL", "gpt-5.6-sol")
    if not email or not password:
        fail("missing LibreChat credentials")
        return False

    with httpx.Client(base_url=base, timeout=180.0, follow_redirects=True) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if login.status_code >= 400:
            fail(f"LibreChat login {login.status_code}: {login.text[:300]}")
            return False
        token = login.json().get("token") or ""
        if not token:
            fail(f"no token: {login.text[:300]}")
            return False
        ok("LibreChat login")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }
        # Ask modelSpec path without temperature
        payload = {
            "text": (
                "Call the Clickathon-RCA tool investigate_day for 2026-06-23 "
                "with include_narrative true if available, otherwise detect_day. "
                "Then briefly state the primary factor and segment with numbers from the tool."
            ),
            "endpoint": "openAI",
            "model": model,
            "spec": "inmobi-rca-orchestrator",
            # Explicitly omit temperature
        }
        # Try modern agents/chat completions style endpoints used by LibreChat
        paths = [
            "/api/agents/chat",
            "/api/ask/openAI",
            "/api/chat",
        ]
        last = ""
        for path in paths:
            r = client.post(path, headers=headers, json=payload)
            last = f"{path} -> {r.status_code}: {r.text[:400]}"
            if r.status_code < 400:
                body = r.text
                if "temperature" in body.lower() and "unsupported" in body.lower():
                    fail(f"LibreChat still sending bad temperature via {path}")
                    return False
                if "Unsupported value" in body and "temperature" in body:
                    fail(f"temperature error still present: {body[:300]}")
                    return False
                ok(f"LibreChat accepted request on {path} (HTTP {r.status_code})")
                # SSE may not include full tool result synchronously; acceptance is enough
                # if no temperature error
                if "Android" in body or "fill" in body.lower() or "event:" in body:
                    ok("LibreChat response stream started / contains content")
                return True
        fail(f"LibreChat chat endpoints failed. Last: {last}")
        return False


def main() -> int:
    os.chdir(ROOT)
    env = load_env()
    # Ensure process env has CH/LLM for engine
    for k, v in env.items():
        os.environ.setdefault(k, v)

    results = []
    print("== 1) Engine ==")
    results.append(test_engine())
    print("== 2) RCA MCP ==")
    results.append(test_rca_mcp())
    print("== 3) LibreChat API ==")
    results.append(test_librechat(env))

    if all(results):
        print("\nALL SMOKE CHECKS PASSED")
        return 0
    print("\nSOME CHECKS FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
