#!/usr/bin/env python3
"""Thorough RCA regression: discovery, per-incident investigate, MCP tools, LibreChat."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Expected discovered patterns (algorithmic — not a hardcoded catalog lookup)
EXPECTED = [
    {
        "label": "layered_ecpm",
        "factor": "ecpm",
        "window_contains": "2026-06-19",
        "segment_any": ["finance", "interstitial", "EU"],
    },
    {
        "label": "global_volume",
        "factor": "requests",
        "window_contains": "2026-06-21",
        "segment_any": ["ALL", "global"],
    },
    {
        "label": "android15_fill",
        "factor": "fill_rate",
        "window_contains": "2026-06-23",
        "segment_any": ["Android 15"],
    },
    {
        "label": "ios_apac_fill",
        "factor": "fill_rate",
        "window_contains": "2026-06-29",
        "segment_any": ["iOS 18.1", "APAC"],
    },
]

INVESTIGATE_CASES = [
    {
        "day": "2026-06-21",
        "label": "A_volume",
        "expect_factor": "requests",
        "expect_in": ["126", "225", "global", "volume", "requests"],
    },
    {
        "day": "2026-06-23",
        "label": "B_android15",
        "expect_factor": "fill_rate",
        "expect_in": ["Android 15", "fill"],
    },
    {
        "day": "2026-06-19",
        "label": "C_ecpm",
        "expect_factor": "ecpm",
        "expect_in": ["ecpm", "eCPM"],
    },
    {
        "day": "2026-06-29",
        "label": "D_ios_apac",
        "expect_factor": "fill_rate",
        "expect_in": ["iOS 18.1", "APAC"],
    },
]


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Suite:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append(Result(name, ok, detail))
        mark = "OK  " if ok else "FAIL"
        print(f"{mark} {name}" + (f" — {detail}" if detail else ""))

    def check(self, name: str, cond: bool, detail: str = "") -> bool:
        self.add(name, cond, detail)
        return cond


def load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def orch_id() -> str:
    yaml = (ROOT / "stack" / "librechat.yaml").read_text(encoding="utf-8")
    m = re.search(r'inmobi-rca-orchestrator[\s\S]*?agent_id:\s*"([^"]+)"', yaml)
    return m.group(1) if m else ""


def blob(obj: Any) -> str:
    return json.dumps(obj, default=str)


def window_covers(inc: dict, day: str) -> bool:
    return inc["window_start"] <= day <= inc["window_end"]


# ── Engine ──────────────────────────────────────────────────────────────


def test_discovery(suite: Suite) -> dict[str, Any]:
    from clickathon.incidents import discover_incidents

    a = discover_incidents()
    b = discover_incidents()
    suite.check("discover.count==4", a.get("count") == 4, f"got {a.get('count')}")
    suite.check(
        "discover.reproducible",
        [(i["window_start"], i["window_end"], i["primary_factor"], i["segment"]) for i in a["incidents"]]
        == [(i["window_start"], i["window_end"], i["primary_factor"], i["segment"]) for i in b["incidents"]],
    )
    suite.check("discover.mode", a.get("mode") == "discovered_incidents")
    suite.check("discover.has_explanations", all("explanation" in i and "Factor:" in i["explanation"] for i in a["incidents"]))

    found: dict[str, dict] = {}
    for exp in EXPECTED:
        match = None
        for inc in a["incidents"]:
            if inc["primary_factor"] != exp["factor"]:
                continue
            if not window_covers(inc, exp["window_contains"]):
                continue
            seg = str(inc.get("segment") or "")
            if any(s in seg for s in exp["segment_any"]):
                match = inc
                break
        ok = match is not None
        suite.check(f"discover.{exp['label']}", ok, "" if ok else f"missing among {[ (i['primary_factor'], i['segment'], i['window_start']) for i in a['incidents'] ]}")
        if match:
            found[exp["label"]] = match
            suite.check(
                f"discover.{exp['label']}.explanation",
                any(s in match["explanation"] for s in exp["segment_any"]),
            )
    return a


def test_investigate_cases(suite: Suite) -> None:
    from clickathon.investigate import investigate

    for case in INVESTIGATE_CASES:
        f = investigate(case["day"], narrate=True)
        dec = (f.get("decomposition") or {}).get("primary_factor")
        diag = f.get("diagnosis") or {}
        text = blob(f) + "\n" + str(f.get("narrative") or "")
        suite.check(
            f"investigate.{case['label']}.factor",
            dec == case["expect_factor"],
            f"got {dec}",
        )
        hits = [s for s in case["expect_in"] if s.lower() in text.lower()]
        suite.check(
            f"investigate.{case['label']}.content",
            len(hits) >= 2,
            f"hits={hits}",
        )
        suite.check(
            f"investigate.{case['label']}.narrative",
            bool(f.get("narrative")) and "ResponseReasoningItem" not in str(f.get("narrative")),
        )
        # Localization expectations
        if case["label"] == "B_android15":
            suite.check(
                "investigate.B.segment_android15",
                "Android 15" in str(diag.get("segment")),
                str(diag.get("segment")),
            )
        if case["label"] == "A_volume":
            suite.check(
                "investigate.A.global_or_requests",
                "global" in str(diag.get("segment") or "").lower()
                or dec == "requests"
                or (f.get("localization") or {}).get("shape") == "global_uniform",
                str(diag),
            )
        if case["label"] == "D_ios_apac":
            loc = blob(f.get("localization") or {}) + str(diag.get("segment") or "")
            suite.check(
                "investigate.D.ios_or_apac",
                "iOS 18.1" in loc or "APAC" in loc,
                loc[:200],
            )


def test_decompose_localize(suite: Suite) -> None:
    from clickathon.decompose import decompose_factors
    from clickathon.drilldown import drill_combo, drill_dimension, localize

    d23 = decompose_factors("2026-06-23")
    suite.check("decompose.2026-06-23.fill", d23.get("primary_factor") == "fill_rate", str(d23.get("primary_factor")))

    d21 = decompose_factors("2026-06-21")
    # volume should dominate even if shares wobble
    from clickathon.detect import daily_wow

    wow = daily_wow("2026-06-21")
    suite.check("detect.2026-06-21.volume_flag", bool((wow.get("flags") or {}).get("volume")))
    suite.check("detect.2026-06-21.req_drop", (wow.get("deltas") or {}).get("req_chg", 0) < -0.4)

    os_scan = drill_dimension("2026-06-23", "os_version", limit=8)
    segs = os_scan.get("segments") or []
    a15 = next((s for s in segs if str(s.get("dim")) == "Android 15"), None)
    suite.check("drill.os.android15", a15 is not None and (a15.get("fill_chg") or 0) < -0.3)

    combo = drill_combo("2026-06-29", "os_region", limit=15)
    hit = next(
        (
            s
            for s in (combo.get("segments") or [])
            if "iOS 18.1" in str(s.get("dim1")) and str(s.get("dim2")) == "APAC"
        ),
        None,
    )
    suite.check("drill.combo.ios_apac", hit is not None and (hit.get("fill_chg") or 0) < -0.3)

    loc = localize("2026-06-23", primary_factor="fill_rate")
    top = loc.get("top_localization") or {}
    suite.check("localize.2026-06-23.android", "Android 15" in str(top.get("segment") or top.get("dim") or ""))

    fr = drill_combo("2026-06-19", "format_region", limit=12)
    eu_int = next(
        (
            s
            for s in (fr.get("segments") or [])
            if str(s.get("dim1")) == "interstitial" and str(s.get("dim2")) == "EU"
        ),
        None,
    )
    suite.check("drill.format_region.eu_int", eu_int is not None and (eu_int.get("ecpm_chg") or 0) < -0.5)


def test_recovery_not_incident(suite: Suite, discovered: dict[str, Any]) -> None:
    """Recoveries like Jun 26 fill↑ vs Android15 baseline should not be standalone incidents."""
    bad_days = {"2026-06-26", "2026-06-27", "2026-07-01", "2026-07-02"}
    for inc in discovered.get("incidents") or []:
        days = set(inc.get("days") or [])
        # window endpoints only — if an incident is ONLY a recovery day, fail
        if inc["window_start"] == inc["window_end"] and inc["window_start"] in bad_days:
            suite.check(f"recovery.not_solo.{inc['window_start']}", False, blob(inc)[:120])
            return
    suite.check("recovery.no_solo_rebound_incidents", True)


# ── MCP ─────────────────────────────────────────────────────────────────


class McpClient:
    def __init__(self, url: str = "http://127.0.0.1:8001/mcp") -> None:
        self.url = url
        self.client = httpx.Client(timeout=180.0)
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._id = 0
        self._init()

    def _init(self) -> None:
        r = self.client.post(
            self.url,
            headers=self.headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "thorough", "version": "1"},
                },
            },
        )
        session = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
        if session:
            self.headers["mcp-session-id"] = session
        self.client.post(
            self.url,
            headers=self.headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

    def call(self, name: str, arguments: dict | None = None) -> str:
        self._id += 1
        r = self.client.post(
            self.url,
            headers=self.headers,
            json={
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            },
        )
        return r.text

    def close(self) -> None:
        self.client.close()


def test_mcp_all_tools(suite: Suite) -> None:
    mcp = McpClient()
    try:
        # list tools
        self_id = 99
        r = mcp.client.post(
            mcp.url,
            headers=mcp.headers,
            json={"jsonrpc": "2.0", "id": self_id, "method": "tools/list", "params": {}},
        )
        text = r.text
        expected_tools = [
            "list_all_anomalies",
            "scan_anomalies_tool",
            "detect_day",
            "decompose_day",
            "drill_dim",
            "drill_combo_tool",
            "segment_scan_tool",
            "localize_day",
            "investigate_day",
        ]
        for t in expected_tools:
            suite.check(f"mcp.tools_list.{t}", t in text)

        out = mcp.call("list_all_anomalies")
        suite.check("mcp.list_all_anomalies", "discovered_incidents" in out and "Android 15" in out)

        out = mcp.call("scan_anomalies_tool", {"start_date": "2026-06-20", "end_date": "2026-06-25"})
        suite.check("mcp.scan_anomalies_tool", "2026-06-21" in out or "2026-06-23" in out)

        out = mcp.call("detect_day", {"day": "2026-06-21"})
        suite.check("mcp.detect_day", "req_chg" in out and "-0.44" in out)

        out = mcp.call("decompose_day", {"day": "2026-06-23"})
        suite.check("mcp.decompose_day", "fill_rate" in out)

        out = mcp.call("drill_dim", {"day": "2026-06-23", "dimension": "os_version"})
        suite.check("mcp.drill_dim", "Android 15" in out)

        out = mcp.call("drill_combo_tool", {"day": "2026-06-29", "combo": "os_region"})
        suite.check("mcp.drill_combo_tool", "iOS 18.1" in out and "APAC" in out)

        out = mcp.call("segment_scan_tool", {"day": "2026-06-23", "dimension": "os_version"})
        suite.check("mcp.segment_scan_tool", "Android 15" in out)

        out = mcp.call("localize_day", {"day": "2026-06-23", "primary_factor": "fill_rate"})
        suite.check("mcp.localize_day", "Android 15" in out)

        out = mcp.call("investigate_day", {"day": "2026-06-23", "include_narrative": False})
        suite.check("mcp.investigate_day", "Android 15" in out and "fill_rate" in out)

        # quiet / control day should not explode
        out = mcp.call("detect_day", {"day": "2026-06-10"})
        suite.check("mcp.detect_quiet_day", "is_anomaly" in out or "deltas" in out)
    finally:
        mcp.close()


# ── LibreChat ───────────────────────────────────────────────────────────


def lc_login(env: dict[str, str]) -> tuple[httpx.Client, dict[str, str]]:
    base = os.environ.get("LIBRECHAT_URL", "http://localhost:3080").rstrip("/")
    client = httpx.Client(
        base_url=base, timeout=300.0, follow_redirects=True, headers={"User-Agent": UA}
    )
    client.get("/")
    login = client.post(
        "/api/auth/login",
        json={"email": env["LIBRECHAT_USER_EMAIL"], "password": env["LIBRECHAT_USER_PASSWORD"]},
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
    return client, headers


def lc_chat(client: httpx.Client, headers: dict[str, str], text: str, agent_id: str) -> str:
    start = client.post(
        "/api/agents/chat",
        headers={**headers, "Accept": "text/event-stream, application/json"},
        json={
            "text": text,
            "endpoint": "agents",
            "agent_id": agent_id,
            "spec": "inmobi-rca-orchestrator",
            "model": os.environ.get("OPENAI_MODEL", "gpt-5.6-sol"),
        },
    )
    if start.status_code >= 400:
        return f"HTTP_ERROR {start.status_code} {start.text[:300]}"
    cid = start.json()["conversationId"]
    tool_blob = ""
    for _ in range(100):
        time.sleep(2)
        st = client.get(f"/api/agents/chat/status/{cid}", headers=headers).json()
        for part in st.get("aggregatedContent") or []:
            if not part:
                continue
            tc = (part.get("tool_call") or {}) if isinstance(part, dict) else {}
            if tc.get("output"):
                tool_blob += "\n" + tc["output"]
            if tc.get("name"):
                tool_blob += f"\nTOOL:{tc.get('name')}"
        if st.get("active") is False:
            break
    msgs = client.get(f"/api/messages/{cid}", headers=headers).json()
    assistant = ""
    for m in msgs:
        if m.get("isCreatedByUser"):
            continue
        assistant += "\n" + (m.get("text") or "")
        for part in m.get("content") or []:
            if isinstance(part, dict) and part.get("type") == "tool_call":
                tc = part.get("tool_call") or {}
                tool_blob += f"\nTOOL:{tc.get('name')}\n{tc.get('output') or ''}"
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text")
                assistant += "\n" + (t.get("value") if isinstance(t, dict) else str(t or ""))
    return tool_blob + "\n" + assistant


def test_librechat(suite: Suite, env: dict[str, str]) -> None:
    aid = orch_id()
    suite.check("librechat.agent_id_present", bool(aid), aid)

    client, headers = lc_login(env)
    try:
        # subagents wired
        ag = client.get(f"/api/agents/{aid}", headers=headers).json()
        kids = (ag.get("subagents") or {}).get("agent_ids") or ag.get("agent_ids") or []
        suite.check("librechat.subagents_3", len(kids) >= 3, str(kids))
        tools = ag.get("tools") or []
        for need in (
            "list_all_anomalies_mcp_Clickathon-RCA",
            "investigate_day_mcp_Clickathon-RCA",
            "decompose_day_mcp_Clickathon-RCA",
            "localize_day_mcp_Clickathon-RCA",
            "drill_combo_tool_mcp_Clickathon-RCA",
        ):
            suite.check(f"librechat.orch_has.{need.split('_mcp_')[0]}", need in tools)

        # Case 1: anomalies
        out = lc_chat(client, headers, "What are the anomalies? Explain each briefly.", aid)
        suite.check("librechat.anomalies.android15", "Android 15" in out)
        suite.check("librechat.anomalies.ios_apac", "iOS 18.1" in out and "APAC" in out)
        suite.check("librechat.anomalies.volume_or_0621", "2026-06-21" in out or "volume" in out.lower())
        suite.check("librechat.anomalies.tool_used", "list_all_anomalies" in out or "discovered_incidents" in out)
        suite.check("librechat.anomalies.not_14_dayflags", "14 of 35" not in out)

        # Case 2: investigate Android 15 day
        out = lc_chat(
            client,
            headers,
            "Investigate 2026-06-23. What is the primary factor and segment? Use tools.",
            aid,
        )
        suite.check("librechat.inv_0623.android", "Android 15" in out)
        suite.check("librechat.inv_0623.fill", "fill" in out.lower())

        # Case 3: investigate volume day
        out = lc_chat(
            client,
            headers,
            "Investigate 2026-06-21. Is this global volume? Quote tool numbers.",
            aid,
        )
        suite.check(
            "librechat.inv_0621.volume",
            "126" in out or "44" in out or "volume" in out.lower() or "requests" in out.lower(),
        )

        # Case 4: hidden fill
        out = lc_chat(
            client,
            headers,
            "Investigate 2026-06-29. Localize the fill issue with combo drill if needed.",
            aid,
        )
        suite.check(
            "librechat.inv_0629.ios_apac",
            "iOS 18.1" in out or ("APAC" in out and "fill" in out.lower()),
        )
    finally:
        client.close()


def main() -> int:
    os.chdir(ROOT)
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    suite = Suite()
    print("\n======== ENGINE ========")
    discovered = test_discovery(suite)
    test_investigate_cases(suite)
    test_decompose_localize(suite)
    test_recovery_not_incident(suite, discovered)

    print("\n======== MCP ========")
    test_mcp_all_tools(suite)

    print("\n======== LIBRECHAT ========")
    test_librechat(suite, env)

    passed = sum(1 for r in suite.results if r.ok)
    failed = [r for r in suite.results if not r.ok]
    print(f"\n======== SUMMARY: {passed}/{len(suite.results)} passed ========")
    if failed:
        print("FAILURES:")
        for r in failed:
            print(f"  - {r.name}: {r.detail}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
