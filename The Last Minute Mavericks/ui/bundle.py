"""Evidence-bundle loader + {{ev_N}} resolution.

Authoritative shape: contracts/fixtures/example_bundle.json (CONTRACTS §8).
Panels NEVER invent a number: if it isn't in the bundle, it isn't rendered.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = REPO_ROOT / "contracts" / "fixtures" / "example_bundle.json"

_PLACEHOLDER = re.compile(r"\{\{(ev_[A-Za-z0-9_]+)\}\}")

VERDICT_META = {
    # verdict -> (chip kind, stripe, human label)
    "LOCALIZED_1D": ("crit", "crit", "Localized · single dimension"),
    "LOCALIZED_2D": ("crit", "crit", "Localized · 2-D interaction"),
    "GLOBAL_UNLOCALIZED": ("info", "info", "Global · no responsible segment"),
    "NORMAL": ("ok", "ok", "Normal · inside expected band"),
    "INCONCLUSIVE": ("info", "info", "Inconclusive · insufficient evidence"),
}


def load(path: str | Path | None = None, incident: str | None = None,
         *, fresh_api: bool = False) -> dict:
    """Load an evidence bundle.

    Accepts BOTH contract shapes:
    - a single §8 investigation object (the golden fixture), returned as-is;
    - the §8.1 scan wrapper {"scan_summary": ..., "investigations": [...]} —
      returns the investigation selected by RCOS_INCIDENT (index or
      investigation_id; default 0 = top-ranked), with the scan_summary and
      sibling list attached under "_scan" for panels that want them.
    """
    doc = None
    if path is None and not os.environ.get("RCOS_BUNDLE"):
        # richest source first: the live engine API (same normalized doc the
        # Incidents tab renders) — so chat + diagnosis ground on REAL output
        try:
            from ui import incidents as _inc
            if fresh_api:
                # The shim runs in a separate process from Streamlit, so the
                # dashboard cannot clear this process-local cache on refresh.
                _inc._api_cache.update(t=0.0, doc=None)
            doc = _inc._api_doc()
        except Exception:  # noqa: BLE001 — engine down → fixture chain
            doc = None
    if doc is None:
        p = Path(path or os.environ.get("RCOS_BUNDLE") or DEFAULT_FIXTURE)
        doc = json.loads(p.read_text())
    if "investigations" not in doc:
        return doc
    invs = doc["investigations"] or []
    if not invs:
        return {"verdict": "NORMAL", "diagnosis": "Scan complete — no incidents survived the gates.",
                "_scan": {"summary": doc.get("scan_summary", {}), "siblings": []}}
    # per-call `incident` (id or index) wins over the RCOS_INCIDENT env — this is how the chat
    # dock asks about the SPECIFIC incident the user clicked, instead of always the top one.
    sel = str(incident) if incident not in (None, "") else os.environ.get("RCOS_INCIDENT", "0")
    chosen = None
    if sel == "worst":
        # generic question with no incident picked → the biggest move (by |delta|), so
        # "why did revenue drop?" anchors to a real drop, not whichever incident sorts first.
        # Tolerate BOTH bundle shapes: the §8 golden fixture has headline as a DICT with
        # delta_pct, while scan-bundle investigations have headline as a STRING (no pct) —
        # for the string shape, fall back to the culprit's deviation_pct, else 0 (stable sort).
        def _delta(i: dict) -> float:
            hl = i.get("headline")
            if isinstance(hl, dict):
                return abs(hl.get("delta_pct") or 0)
            c = i.get("culprit") or {}
            return abs(c.get("deviation_pct") or 0)
        chosen = max(invs, key=_delta)
    elif sel.isdigit() and int(sel) < len(invs):
        chosen = invs[int(sel)]
    else:
        # Match by any id-like field the bundle carries: the raw engine `id`
        # (scan-bundle investigations only have this), the short `INC-n`
        # (normalized api output), `investigation_id`, or `engine_id`.
        chosen = next(
            (i for i in invs
             if sel in (i.get("id"), i.get("investigation_id"),
                        i.get("incident_id"), i.get("engine_id"))),
            None,
        )
        # INC-{n} (1-based) maps to the nth investigation — the dashboard dock
        # sends the short id the Incidents tab assigned; resolve it back to an
        # index so "ask about the incident you clicked" finds the right one.
        if chosen is None:
            m = re.match(r"^INC-(\d+)$", sel, re.IGNORECASE)
            if m and 0 < int(m.group(1)) <= len(invs):
                chosen = invs[int(m.group(1)) - 1]
        if chosen is None:
            chosen = invs[0]
    chosen = dict(chosen)

    def _sib(i: dict) -> dict:
        """A one-line summary of an incident, so the chat can LIST / COUNT / compare all of
        them (aggregate questions) — not just describe the single anchored one."""
        h = i.get("headline")
        c = i.get("culprit") or {}
        w = i.get("incident_window") or {}
        # Tolerate BOTH bundle shapes: the §8 golden fixture has headline as a DICT
        # with delta_pct, while scan-bundle investigations have headline as a STRING
        # (no pct) — for the string shape, fall back to the culprit's deviation_pct.
        moved = h.get("delta_pct") if isinstance(h, dict) else c.get("deviation_pct")
        return {
            "id": i.get("investigation_id") or i.get("incident_id") or i.get("id"),
            "metric": i.get("metric"),
            "verdict": i.get("verdict"),
            "when": str(w.get("start", ""))[:10] + (f"→{str(w.get('end',''))[:10]}"
                                                    if w.get("end") else ""),
            "moved_pct": moved,
            "culprit": (f"{c.get('dimension')}={c.get('value')}" if c.get("dimension")
                        else "global (no single segment)"),
        }

    chosen["_scan"] = {"summary": doc.get("scan_summary", {}),
                       "count": len(invs),
                       "siblings": [_sib(i) for i in invs]}
    return chosen


def ev(bundle: dict, ev_id: str) -> dict | None:
    return (bundle.get("evidence_store") or {}).get(ev_id)


def diagnosis_tokens(bundle: dict) -> list[tuple[str, str]]:
    """Split diagnosis prose into tokens.

    Returns list of (kind, payload): kind in {"text", "ev", "unresolved"};
    payload is raw text or the ev_id. UNRESOLVED placeholders are surfaced,
    never silently dropped (frontend prompt §3.2).
    """
    out: list[tuple[str, str]] = []
    text = bundle.get("diagnosis", "")
    pos = 0
    for m in _PLACEHOLDER.finditer(text):
        if m.start() > pos:
            out.append(("text", text[pos : m.start()]))
        eid = m.group(1)
        out.append(("ev" if ev(bundle, eid) else "unresolved", eid))
        pos = m.end()
    if pos < len(text):
        out.append(("text", text[pos:]))
    return out


def tamper(bundle: dict) -> dict:
    """inject_hallucination: return a copy whose diagnosis cites a number no query produced.

    Demo of the guardrail (DEMO.md 'money shot'). Does NOT mutate the input.
    """
    b = json.loads(json.dumps(bundle))
    b["diagnosis"] = (
        b.get("diagnosis", "").rstrip()
        + " Estimated recovery suggests revenue of {{ev_999}} (about $181,000) next week."
    )
    return b


def verdict_meta(bundle: dict) -> tuple[str, str, str]:
    return VERDICT_META.get(bundle.get("verdict", ""), ("mut", None, bundle.get("verdict", "UNKNOWN")))
