#!/usr/bin/env python3
"""Run Atlys PM chat eval cases against POST /api/proxy/chat.

Usage:
  python docs/chat-eval/run_chat_eval.py --loop 1
  python docs/chat-eval/run_chat_eval.py --loop 1 --only S01,C02
  python docs/chat-eval/run_chat_eval.py --loop 2 --cases docs/chat-eval/test-cases.yaml
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = Path(__file__).resolve().parent / "test-cases.yaml"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_cases(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if not data or "cases" not in data:
        raise SystemExit(f"No cases in {path}")
    return data


def parse_sse(line: str) -> Any | None:
    if not line.startswith("data: "):
        return None
    data = line[6:].strip()
    if data == "[DONE]":
        return {"done": True}
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return {"raw": data}


def chat_once(
    base_url: str,
    prompt: str,
    timeout_s: float,
) -> dict[str, Any]:
    cid = str(uuid.uuid4())
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "conversationId": cid,
    }
    text_parts: list[str] = []
    tools: list[dict] = []
    errors: list[str] = []
    status = None
    t0 = time.monotonic()

    with httpx.Client(timeout=httpx.Timeout(timeout_s, connect=30.0)) as client:
        with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/api/proxy/chat",
            json=payload,
            headers={"Accept": "text/event-stream"},
        ) as resp:
            status = resp.status_code
            cid_hdr = resp.headers.get("X-Conversation-Id", cid)
            if status >= 400:
                body = resp.read().decode("utf-8", errors="replace")
                return {
                    "ok": False,
                    "status": status,
                    "conversation_id": cid_hdr,
                    "text": "",
                    "tools": [],
                    "errors": [f"HTTP {status}: {body[:800]}"],
                    "elapsed_s": round(time.monotonic() - t0, 2),
                }
            for line in resp.iter_lines():
                if not line:
                    continue
                obj = parse_sse(line)
                if obj is None:
                    continue
                if obj.get("done"):
                    break
                if "atlys_progress" in obj:
                    prog = obj["atlys_progress"]
                    name = prog.get("name") or ""
                    # strip mcp suffix
                    bare = re.sub(r"_mcp_[A-Za-z0-9_-]+$", "", str(name))
                    tools.append(
                        {
                            "name": bare,
                            "type": prog.get("type"),
                            "ok": prog.get("ok"),
                            "arguments": prog.get("arguments"),
                        }
                    )
                    continue
                if "error" in obj and not obj.get("choices"):
                    errors.append(str(obj.get("error")))
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                if delta.get("content"):
                    text_parts.append(delta["content"])
                # some providers put content on message
                msg = choices[0].get("message") or {}
                if msg.get("content") and not delta.get("content"):
                    text_parts.append(msg["content"])

    text = "".join(text_parts).strip()
    return {
        "ok": status == 200 and bool(text) and not errors,
        "status": status,
        "conversation_id": cid_hdr if status else cid,
        "text": text,
        "tools": tools,
        "errors": errors,
        "elapsed_s": round(time.monotonic() - t0, 2),
    }


def tool_names(tools: list[dict]) -> list[str]:
    names = []
    for t in tools:
        n = t.get("name") or ""
        if n and (t.get("type") in (None, "tool_start", "tool_end", "start", "end", "call") or True):
            names.append(n)
    return names


def evaluate(case: dict, result: dict) -> dict:
    expect = case.get("expect") or {}
    text = result.get("text") or ""
    text_l = text.lower()
    names = tool_names(result.get("tools") or [])
    # unique preserving order
    uniq = list(dict.fromkeys(names))
    failures: list[str] = []
    notes: list[str] = []

    if result.get("status") != 200:
        failures.append(f"http_status={result.get('status')}")
    if not text:
        failures.append("empty_response")
    for e in result.get("errors") or []:
        failures.append(f"stream_error:{e[:200]}")

    tools_any = expect.get("tools_any") or []
    if tools_any and not any(t in uniq for t in tools_any):
        failures.append(f"missing_tools_any expected one of {tools_any}, got {uniq}")

    for t in expect.get("forbid_tools") or []:
        if t in uniq:
            failures.append(f"forbid_tool_used:{t}")

    bad_tables = [x.lower() for x in (expect.get("must_not_tool_table") or [])]
    if bad_tables:
        for t in result.get("tools") or []:
            if (t.get("name") or "") not in (
                "aggregate",
                "table_stats",
                "sample_rows",
                "db_schema",
            ):
                continue
            blob = t.get("arguments")
            if blob is None:
                continue
            if not isinstance(blob, str):
                try:
                    blob = json.dumps(blob)
                except Exception:
                    blob = str(blob)
            blob_l = blob.lower()
            for bad in bad_tables:
                if bad in blob_l:
                    failures.append(f"must_not_tool_table:{bad} via {t.get('name')}")
                    break

    for phrase in expect.get("must_mention") or []:
        if phrase.lower() not in text_l:
            failures.append(f"must_mention:{phrase}")

    any_phrases = expect.get("must_mention_any") or []
    if any_phrases and not any(p.lower() in text_l for p in any_phrases):
        failures.append(f"must_mention_any:{any_phrases}")

    for phrase in expect.get("must_not_mention") or []:
        if phrase.lower() in text_l:
            failures.append(f"must_not_mention:{phrase}")

    if expect.get("response_has_number"):
        if not re.search(r"\d", text):
            failures.append("response_has_number")

    max_named = expect.get("max_tool_calls_named") or {}
    for tool, max_n in max_named.items():
        # Count only start/call events — tool_done is a twin side-channel event.
        starts = [
            t
            for t in (result.get("tools") or [])
            if t.get("name") == tool
            and str(t.get("type") or "")
            in ("tool_start", "tool_call", "start", "call")
        ]
        use_count = len(starts) if starts else sum(
            1 for n in names if n == tool
        )
        if use_count > max_n:
            failures.append(f"max_tool_calls:{tool} used={use_count}>{max_n}")

    # soft note: auto_approve in tool args for C06
    for t in result.get("tools") or []:
        args = t.get("arguments")
        blob = json.dumps(args) if not isinstance(args, str) else args
        if "auto_approve" in blob.lower() and "true" in blob.lower():
            if case.get("id") == "C06":
                failures.append("auto_approve_true_used")
            else:
                notes.append("auto_approve_true_seen")

    passed = len(failures) == 0 and result.get("status") == 200 and bool(text)
    return {
        "passed": passed,
        "failures": failures,
        "notes": notes,
        "tools_used": uniq,
    }


def run_loop(args: argparse.Namespace) -> int:
    suite = load_cases(Path(args.cases))
    base = args.base_url or suite.get("base_url") or "http://127.0.0.1:8000"
    timeout = float(args.timeout or suite.get("timeout_s") or 180)
    only = set(x.strip() for x in (args.only or "").split(",") if x.strip())
    cases = suite["cases"]
    if only:
        cases = [c for c in cases if c["id"] in only]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-only-{'-'.join(sorted(only))}" if only else ""
    out_path = RESULTS_DIR / f"loop-{args.loop}{suffix}.json"
    md_path = RESULTS_DIR / f"loop-{args.loop}{suffix}.md"

    # readiness
    try:
        st = httpx.get(f"{base.rstrip('/')}/api/agent-status", timeout=15.0)
        status_json = st.json()
    except Exception as e:
        print(f"FATAL: agent-status failed: {e}", file=sys.stderr)
        return 2
    if not status_json.get("provisioned"):
        print(f"FATAL: agent not provisioned: {status_json}", file=sys.stderr)
        return 2
    print(f"[{_now()}] loop={args.loop} cases={len(cases)} base={base}")
    print(f"agent={status_json.get('agent_name')} id={status_json.get('agent_id')}")

    results: list[dict] = []
    for i, case in enumerate(cases, 1):
        print(f"\n=== [{i}/{len(cases)}] {case['id']} {case.get('title', '')} ===")
        print(f"prompt: {case['prompt'][:120].strip()}...")
        try:
            raw = chat_once(base, case["prompt"].strip(), timeout)
        except Exception as e:
            raw = {
                "ok": False,
                "status": None,
                "conversation_id": None,
                "text": "",
                "tools": [],
                "errors": [f"exception:{e}"],
                "elapsed_s": None,
            }
        verdict = evaluate(case, raw)
        row = {
            "id": case["id"],
            "tier": case.get("tier"),
            "title": case.get("title"),
            "prompt": case["prompt"].strip(),
            "expect_notes": (case.get("expect") or {}).get("notes"),
            "result": {
                "status": raw.get("status"),
                "conversation_id": raw.get("conversation_id"),
                "elapsed_s": raw.get("elapsed_s"),
                "text": raw.get("text"),
                "tools": raw.get("tools"),
                "errors": raw.get("errors"),
            },
            "verdict": verdict,
        }
        results.append(row)
        mark = "PASS" if verdict["passed"] else "FAIL"
        print(f"→ {mark} tools={verdict['tools_used']} elapsed={raw.get('elapsed_s')}s")
        if verdict["failures"]:
            print(f"  failures: {verdict['failures']}")
        # persist incrementally
        out_path.write_text(json.dumps({"loop": args.loop, "started": _now(), "results": results}, indent=2))

    passed = sum(1 for r in results if r["verdict"]["passed"])
    failed = len(results) - passed
    summary = {
        "loop": args.loop,
        "finished": _now(),
        "base_url": base,
        "passed": passed,
        "failed": failed,
        "total": len(results),
        "results": results,
    }
    out_path.write_text(json.dumps(summary, indent=2))

    lines = [
        f"# Chat eval — loop {args.loop}",
        "",
        f"finished: {summary['finished']}",
        f"score: **{passed}/{len(results)}** passed ({failed} failed)",
        "",
        "| id | tier | result | tools | elapsed | failures |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        v = r["verdict"]
        mark = "PASS" if v["passed"] else "FAIL"
        fails = "; ".join(v["failures"]) if v["failures"] else ""
        tools = ", ".join(v["tools_used"]) or "—"
        lines.append(
            f"| {r['id']} | {r['tier']} | {mark} | {tools} | {r['result'].get('elapsed_s')}s | {fails} |"
        )
    lines.append("")
    lines.append("## Failures detail")
    for r in results:
        if r["verdict"]["passed"]:
            continue
        lines.append(f"### {r['id']} — {r['title']}")
        lines.append(f"- failures: `{r['verdict']['failures']}`")
        lines.append(f"- tools: `{r['verdict']['tools_used']}`")
        excerpt = (r["result"].get("text") or "")[:600].replace("\n", " ")
        lines.append(f"- response excerpt: {excerpt}")
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n")
    print(f"\n=== DONE loop {args.loop}: {passed}/{len(results)} passed ===")
    print(f"wrote {out_path}")
    print(f"wrote {md_path}")
    return 0 if failed == 0 else 1


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--loop", type=int, required=True)
    p.add_argument("--cases", default=str(DEFAULT_CASES))
    p.add_argument("--base-url", default=None)
    p.add_argument("--timeout", default=None)
    p.add_argument("--only", default="", help="Comma-separated case ids")
    args = p.parse_args()
    raise SystemExit(run_loop(args))


if __name__ == "__main__":
    main()
