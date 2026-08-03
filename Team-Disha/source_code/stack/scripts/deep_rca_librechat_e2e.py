#!/usr/bin/env python3
"""Ask LibreChat orchestrator deeper RCA questions and grade answers."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "stack" / "scripts"))

from thorough_rca_e2e import (  # noqa: E402
    load_env,
    lc_chat,
    lc_login,
    orch_id,
)

QUESTIONS = [
    {
        "id": "deep_android15_compare",
        "prompt": (
            "For 2026-06-23, the primary factor is fill_rate on Android 15. "
            "Using rca_segment_day / drill tools, compare Android 15's fill change "
            "to Android 14 and Android 13 on the same day. Quote the fill_t, fill_b, "
            "and fill_chg numbers for each. Was Android 15 uniquely bad?"
        ),
        "must_any": [
            ["Android 15", "android 15"],
            ["fill"],
            ["Android 14", "android 14", "Android 13", "android 13"],
        ],
        "must_not": ["I cannot", "hallucin"],
    },
    {
        "id": "deep_hidden_ios_apac",
        "prompt": (
            "Explain the hidden fill incident around 2026-06-28 to 2026-06-30 "
            "(iOS 18.1 × APAC). Why might global fill look quiet while the segment "
            "is loud? Quote global fill_chg from rca_daily_wow or investigate_day "
            "and the segment fill_chg from the combo drill. Do not invent numbers."
        ),
        "must_any": [
            ["iOS 18.1", "ios 18.1"],
            ["APAC"],
            ["hidden", "quiet", "global"],
            ["fill"],
        ],
        "must_not": [],
    },
    {
        "id": "deep_ecpm_layered",
        "prompt": (
            "For the layered eCPM window that includes 2026-06-19, which segments "
            "drove the price drop (finance category and/or interstitial × EU)? "
            "Quote segment eCPM changes and explain why early days can look quiet "
            "globally. Use list_all_anomalies and drill/combo tools only — no invented figures."
        ),
        "must_any": [
            ["eCPM", "ecpm", "eCPM"],
            ["finance", "interstitial", "EU"],
        ],
        "must_not": [],
    },
    {
        "id": "deep_volume_vs_fill",
        "prompt": (
            "On 2026-06-21 requests crashed globally. Confirm with detect_day/decompose_day "
            "that the primary factor is requests (not fill or eCPM). Quote req_chg and "
            "briefly say what was ruled out. Then contrast with 2026-06-23 where fill "
            "is primary — one sentence each."
        ),
        "must_any": [
            ["request", "volume"],
            ["2026-06-21", "06-21", "June 21"],
            ["fill", "Android 15", "2026-06-23"],
        ],
        "must_not": [],
    },
    {
        "id": "deep_glossary_then_day",
        "prompt": (
            "First quote the official fill rate and eCPM definitions from the metrics "
            "glossary tool. Then, using those definitions, say whether the Android 15 "
            "issue on 2026-06-23 is a fill problem or an eCPM problem, with one key number."
        ),
        "must_any": [
            ["sum(is_filled)", "is_filled", "fill rate", "Fill rate"],
            ["eCPM", "ecpm", "impression"],
            ["fill", "Android 15"],
        ],
        "must_not": [],
    },
]


def grade(out: str, spec: dict) -> tuple[bool, str]:
    low = out.lower()
    misses = []
    for group in spec["must_any"]:
        if not any(tok.lower() in low for tok in group):
            misses.append(f"missing any of {group}")
    for bad in spec.get("must_not") or []:
        if bad.lower() in low:
            misses.append(f"forbidden '{bad}'")
    # Prefer evidence the agent used tools / store
    tools_hint = any(
        t in low
        for t in (
            "list_all_anomalies",
            "investigate_day",
            "decompose_day",
            "drill_",
            "localize_day",
            "get_metrics_glossary",
            "rca_",
            "fill_chg",
            "req_chg",
            "ecpm",
        )
    )
    if not tools_hint and "0." not in out and "%" not in out:
        misses.append("no numeric/tool evidence visible")
    ok = not misses
    return ok, "; ".join(misses) if misses else "ok"


def main() -> int:
    env = load_env()
    if not env.get("LIBRECHAT_USER_PASSWORD"):
        print("missing LIBRECHAT_USER_PASSWORD", file=sys.stderr)
        return 1
    aid = orch_id()
    client, headers = lc_login(env)
    passed = 0
    results = []
    try:
        for q in QUESTIONS:
            print(f"\n======== {q['id']} ========")
            print(f"Q: {q['prompt'][:120]}...")
            out = lc_chat(client, headers, q["prompt"], aid)
            ok, detail = grade(out, q)
            mark = "OK  " if ok else "FAIL"
            print(f"{mark} {detail}")
            # short preview
            preview = re.sub(r"\s+", " ", out)[:500]
            print(f"--- preview ---\n{preview}\n---------------")
            results.append((q["id"], ok, detail, out))
            if ok:
                passed += 1
    finally:
        client.close()

    print(f"\n======== SUMMARY: {passed}/{len(QUESTIONS)} passed ========")
    for qid, ok, detail, _ in results:
        print(f"{'OK' if ok else 'FAIL'} {qid} — {detail}")
    return 0 if passed == len(QUESTIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
