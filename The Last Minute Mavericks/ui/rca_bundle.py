"""RootCauseOS — RCA bundle adapters.

One place that reads the investigation bundle, whichever shape the producer
emitted (live engine, golden fixture, raw runner file). Returns plain dicts;
renders nothing. Every accessor tolerates a missing key and returns an empty
value rather than raising — an absent field is a normal state here.

Split out of ui/diagnosis.py — see that module for the page itself.
"""
from __future__ import annotations

from ui import explain as X

from ui.rca_text import (
    _UNIT_ALIAS,
    _known_metric,
)

# ------------------------------------------------------- bundle normalising

def _dec(b: dict) -> dict:
    """The decomposition as one dict, whichever shape the producer emitted."""
    d = b.get("decomposition")
    if isinstance(d, list):                       # raw runner shape: list + _meta
        meta = dict(b.get("decomposition_meta") or {})
        meta["factors"] = d
        d = meta
    d = dict(d or {})
    d.setdefault("factors", [])
    if d.get("max_divergence_pct") is None:
        d["max_divergence_pct"] = d.get("lmdi_shapley_max_divergence_pct")
    return d


def _store(b: dict) -> dict:
    """The evidence ledger keyed by evidence id, whichever shape arrived."""
    s = b.get("evidence_store")
    if isinstance(s, dict):
        return s
    out: dict[str, dict] = {}
    for i, e in enumerate(b.get("evidence") or []):
        out[str(e.get("id") or f"ev_{i + 1}")] = e
    return out


def _headline(b: dict) -> dict:
    """The headline block. Older producers put a bare string here — drop it
    rather than crash; the sentence and tiles then render from what is left."""
    h = b.get("headline")
    return h if isinstance(h, dict) else {}


def _window(b: dict) -> dict:
    w = b.get("incident_window")
    if isinstance(w, dict):
        return w
    days = b.get("window") or []
    return {"start": days[0], "end": days[-1]} if days else {}


def _culprit(b: dict) -> dict:
    """{dimension, value, co_cut}; tolerates the engine's `segment` spelling."""
    c = b.get("culprit")
    if not isinstance(c, dict) or not c:
        return {}
    c = dict(c)
    c.setdefault("value", c.get("segment"))
    return c


def _pb(b: dict) -> dict:
    """The playbook classification for this incident.

    ui/incidents.py wires it onto every investigation as `playbook`. When a
    bundle arrives without it (the golden fixture, a hand-loaded file) fall back
    to the same deterministic lookup — it is a pure function over the bundle, so
    the answer is identical either way. Never fatal: guidance is optional, the
    evidence is not.
    """
    pb = b.get("playbook")
    if isinstance(pb, dict) and pb:
        return pb
    try:
        from ui import playbook as _P
        return _P.classify(b) or {}
    except Exception:  # noqa: BLE001 — a missing playbook must not break the read-out
        return {}


def _prose(b: dict) -> str:
    """The engine's narration. Some producers wrap it in {"diagnosis": ...}."""
    d = b.get("diagnosis")
    if isinstance(d, dict):
        d = d.get("diagnosis")
    return str(d or "").strip()


def _factor_unit(f: dict) -> str:
    return _UNIT_ALIAS.get(str(f.get("unit") or "").lower(),
                           X.metric_unit(str(f.get("factor") or "")))


def _ev_label(raw: str) -> str:
    """`fill_rate @ ad_format=native × region=EU` -> `Fill rate · Native ads in EU`."""
    lbl = str(raw or "")
    head, _, seg = lbl.partition("@")
    head = head.strip()
    tail = f" · {X.segment_phrase('', seg.strip())}" if seg.strip() else ""
    if head.endswith("_delta_pct") and _known_metric(head[:-10]):
        return f"{X.metric_name(head[:-10])} change{tail}"
    if _known_metric(head):
        return f"{X.metric_name(head)}{tail}"
    parts = head.split("_")
    for i in range(len(parts) - 1, 0, -1):
        key = "_".join(parts[:i])
        if _known_metric(key):
            rest = " ".join(parts[i:])
            return f"{X.metric_name(key)}{(' ' + rest) if rest else ''}{tail}"
    words = head.replace("_", " ")
    return f"{words[:1].upper()}{words[1:]}{tail}" if words else lbl


def _ev_unit(e: dict) -> str:
    """The unit an evidence value carries — stated, or read off its own label."""
    stated = _UNIT_ALIAS.get(str(e.get("unit") or "").lower())
    if stated:
        return stated
    head = str(e.get("label") or "").partition("@")[0].strip()
    if head.endswith("_delta_pct"):
        return "pct"
    return X.metric_unit(head)
