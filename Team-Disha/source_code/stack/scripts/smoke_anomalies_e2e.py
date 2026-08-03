#!/usr/bin/env python3
"""E2E: deterministic incident discovery is reproducible + LibreChat surfaces it."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


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


def orch_id_from_yaml() -> str:
    yaml = (ROOT / "stack" / "librechat.yaml").read_text(encoding="utf-8")
    m = re.search(r'inmobi-rca-orchestrator[\s\S]*?agent_id:\s*"([^"]+)"', yaml)
    return m.group(1) if m else ""


def fingerprint(r: dict) -> list[tuple]:
    return [
        (i["window_start"], i["window_end"], i["primary_factor"], i["segment"])
        for i in r["incidents"]
    ]


def test_engine() -> bool:
    from clickathon.incidents import discover_incidents

    a = discover_incidents()
    b = discover_incidents()
    if a["count"] < 1:
        fail("no incidents")
        return False
    if fingerprint(a) != fingerprint(b):
        fail(f"not reproducible: {fingerprint(a)} vs {fingerprint(b)}")
        return False
    blob = json.dumps(a, default=str)
    need = ["Android 15", "iOS 18.1", "APAC", "requests", "ecpm"]
    missing = [n for n in need if n not in blob]
    if missing:
        fail(f"missing expected discovery content {missing}")
        return False
    if a["count"] > 8:
        fail(f"too many incidents count={a['count']}")
        return False
    ok(f"discover_incidents → {a['count']} reproducible windows")
    for i in a["incidents"]:
        print(
            f"  {i['id']} {i['window_start']}..{i['window_end']} "
            f"{i['primary_factor']} {i['segment']}"
        )
    return True


def test_mcp() -> bool:
    url = "http://127.0.0.1:8001/mcp"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    with httpx.Client(timeout=180.0) as client:
        r = client.post(
            url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0.1"},
                },
            },
        )
        session = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
        if session:
            headers["mcp-session-id"] = session
        client.post(
            url,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        r2 = client.post(
            url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "list_all_anomalies", "arguments": {}},
            },
        )
        if "Android 15" not in r2.text or "discovered_incidents" not in r2.text:
            fail(f"MCP bad: {r2.text[:500]}")
            return False
        ok("MCP list_all_anomalies ok")
        return True


def test_librechat(env: dict[str, str]) -> bool:
    base = os.environ.get("LIBRECHAT_URL", "http://localhost:3080").rstrip("/")
    orch_id = orch_id_from_yaml()
    with httpx.Client(
        base_url=base, timeout=300.0, follow_redirects=True, headers={"User-Agent": UA}
    ) as client:
        client.get("/")
        login = client.post(
            "/api/auth/login",
            json={
                "email": env["LIBRECHAT_USER_EMAIL"],
                "password": env["LIBRECHAT_USER_PASSWORD"],
            },
        )
        token = login.json()["token"]
        client.cookies.set("token", token)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": base,
            "Referer": f"{base}/c/new",
            "User-Agent": UA,
        }
        start = client.post(
            "/api/agents/chat",
            headers={**headers, "Accept": "text/event-stream, application/json"},
            json={
                "text": "What are the anomalies? Explain each one.",
                "endpoint": "agents",
                "agent_id": orch_id,
                "spec": "inmobi-rca-orchestrator",
                "model": env.get("OPENAI_MODEL", "gpt-5.6-sol"),
            },
        )
        cid = start.json()["conversationId"]
        tool_blob = ""
        for _ in range(90):
            time.sleep(2)
            st = client.get(f"/api/agents/chat/status/{cid}", headers=headers).json()
            for part in st.get("aggregatedContent") or []:
                if not part:
                    continue
                tc = (part.get("tool_call") or {}) if isinstance(part, dict) else {}
                if tc.get("output"):
                    tool_blob = tc["output"]
            if st.get("active") is False:
                break
        msgs = client.get(f"/api/messages/{cid}", headers=headers).json()
        assistant = ""
        for m in msgs:
            if m.get("isCreatedByUser"):
                continue
            assistant += m.get("text") or ""
        blob = tool_blob + "\n" + assistant
        if "Android 15" not in blob:
            fail(f"LibreChat missing Android 15: {blob[:800]}")
            return False
        if "14 of 35" in assistant:
            fail("still listing 14 day-flags")
            return False
        ok("LibreChat used discovered incidents")
        print("--- assistant ---")
        print((assistant or tool_blob)[:1400])
        print("-----------------")
        return True


def main() -> int:
    os.chdir(ROOT)
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    results = [test_engine(), test_mcp(), test_librechat(env)]
    if all(results):
        print("\nALL CHECKS PASSED")
        return 0
    print("\nSOME CHECKS FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
