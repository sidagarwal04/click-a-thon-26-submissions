"""Langfuse trace data for the console, rendered natively.

WHY NATIVE AND NOT AN IFRAME
----------------------------
Langfuse serves `Content-Security-Policy: frame-ancestors 'none'` (and
`X-Frame-Options: SAMEORIGIN`), so its trace pages cannot be embedded in this app --
verified against the live host, not assumed. Rather than drop the requirement, this
module pulls the same underlying data through the Langfuse REST API and renders it
here, and every view still deep-links to Langfuse for the authoritative raw view.

That turns out to be better than an embed would have been: we can foreground the one
field a judge actually needs -- `metadata.context_version` on every LLM generation,
which is the mechanical proof of context freshness -- instead of leaving it buried in
a metadata blob.

Everything here degrades to empty rather than raising: tracing may be disabled, the
network may be down, or a run may predate a trace. The console must still render.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import streamlit as st


@dataclass
class Span:
    """One observation, flattened to what the UI actually shows."""

    id: str
    parent_id: str | None
    name: str
    kind: str                      # GENERATION | SPAN | EVENT
    latency_s: float = 0.0
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    context_version: int | None = None
    level: str = "DEFAULT"
    children: list["Span"] = field(default_factory=list)

    @property
    def is_llm(self) -> bool:
        return self.kind == "GENERATION"


@dataclass
class TraceView:
    trace_id: str
    name: str = ""
    latency_s: float = 0.0
    url: str = ""
    roots: list[Span] = field(default_factory=list)
    by_name: dict[str, Span] = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.roots)

    def all_spans(self) -> list[Span]:
        out: list[Span] = []

        def walk(s: Span) -> None:
            out.append(s)
            for c in s.children:
                walk(c)

        for r in self.roots:
            walk(r)
        return out

    def generations(self) -> list[Span]:
        return [s for s in self.all_spans() if s.is_llm]

    def totals(self) -> dict[str, Any]:
        gens = self.generations()
        return {
            "llm_calls": len(gens),
            "output_tokens": sum(g.output_tokens for g in gens),
            "cost_usd": round(sum(g.cost_usd for g in gens), 4),
            "context_versions": sorted({g.context_version for g in gens if g.context_version}),
        }


def _num(meta: Any, *keys: str) -> Any:
    if not isinstance(meta, dict):
        return None
    for k in keys:
        if k in meta:
            return meta[k]
    return None


def _to_span(o: Any) -> Span:
    usage = getattr(o, "usage_details", None) or {}
    meta = getattr(o, "metadata", None) or {}
    cv = _num(meta, "context_version")
    try:
        cv = int(cv) if cv is not None else None
    except (TypeError, ValueError):
        cv = None
    cost = _num(meta, "cost_usd")
    if cost is None:
        cost = getattr(o, "calculated_total_cost", None)
    return Span(
        id=str(getattr(o, "id", "")),
        parent_id=(str(getattr(o, "parent_observation_id", "")) or None),
        name=str(getattr(o, "name", "") or "(unnamed)"),
        kind=str(getattr(o, "type", "SPAN")),
        latency_s=float(getattr(o, "latency", 0.0) or 0.0),
        model=str(getattr(o, "model", "") or ""),
        input_tokens=int(usage.get("input", 0) or 0) if isinstance(usage, dict) else 0,
        output_tokens=int(usage.get("output", 0) or 0) if isinstance(usage, dict) else 0,
        cost_usd=float(cost or 0.0),
        context_version=cv,
        level=str(getattr(o, "level", "DEFAULT") or "DEFAULT"),
    )


@st.cache_data(ttl=120, show_spinner=False)
def fetch_trace(trace_id: str) -> TraceView:
    """Pull a trace and rebuild its span tree. Never raises."""
    if not trace_id:
        return TraceView(trace_id="", error="no trace id recorded for this run")
    try:
        import tracing as _t  # loads .env and resolves the host/region

        if not _t.tracing_enabled():
            return TraceView(trace_id=trace_id, error="tracing disabled (no Langfuse keys)")
        from langfuse import get_client

        raw = get_client().api.trace.get(trace_id)
    except Exception as exc:  # noqa: BLE001 - the console must survive any API failure
        return TraceView(trace_id=trace_id, error=f"{type(exc).__name__}: {exc}")

    spans = [_to_span(o) for o in (getattr(raw, "observations", None) or [])]
    index = {s.id: s for s in spans}
    roots: list[Span] = []
    for s in spans:
        parent = index.get(s.parent_id) if s.parent_id else None
        if parent is not None and parent is not s:
            parent.children.append(s)
        else:
            roots.append(s)
    for s in spans:
        # Longest-running first reads far better than API order for a timing view.
        s.children.sort(key=lambda c: -c.latency_s)
    roots.sort(key=lambda c: -c.latency_s)

    # Build from the trace id rather than trusting a stored trace_url: rows written
    # before the URL-format fix carry the old, dead `/trace/<id>` form.
    try:
        url = _t.trace_url_for(trace_id)
    except Exception:  # noqa: BLE001
        url = ""
    return TraceView(
        trace_id=trace_id,
        name=str(getattr(raw, "name", "") or ""),
        latency_s=float(getattr(raw, "latency", 0.0) or 0.0),
        url=url,
        roots=roots,
        by_name={s.name: s for s in spans},
    )


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

_STAGE_LABEL = {
    "context.load": "1 · Load context",
    "instrumentation": "2 · Instrument",
    "context.reconcile": "3 · Reconcile context",
    "analytics": "4 · Analyse",
    "report": "5 · Report",
}
_STATUS_COLOR = {
    "ok": ("#1a7f37", "#dafbe1"),
    "warn": ("#9a6700", "#fff8c5"),
    "error": ("#cf222e", "#ffebe9"),
    "declined": ("#cf222e", "#ffebe9"),
    "pending": ("#0969da", "#ddf4ff"),
    "skipped": ("#57606a", "#f6f8fa"),
}


def flow_dot(stage_rows: list[dict[str, Any]], versions: tuple[int, int] | None = None) -> str:
    """Graphviz DOT for the five-stage pipeline, coloured by real outcome.

    Rendered by `st.graphviz_chart`, which draws DOT client-side -- no local graphviz
    binary needed, so this adds no dependency to the project.
    """
    seen: dict[str, str] = {}
    for r in stage_rows:
        stage = str(r.get("stage", ""))
        base = stage.split(".")[0] if stage not in _STAGE_LABEL else stage
        key = stage if stage in _STAGE_LABEL else base
        if key in _STAGE_LABEL:
            # a later row for the same stage supersedes an earlier one
            seen[key] = str(r.get("status", "skipped"))

    lines = [
        "digraph pipeline {",
        '  rankdir=LR; bgcolor="transparent";',
        '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=11 penwidth=1.4];',
        '  edge [color="#8c959f" arrowsize=0.7];',
    ]
    order = list(_STAGE_LABEL)
    for i, key in enumerate(order):
        status = seen.get(key, "skipped")
        fg, bg = _STATUS_COLOR.get(status, _STATUS_COLOR["skipped"])
        label = _STAGE_LABEL[key].replace("·", "-")
        lines.append(
            f'  n{i} [label="{label}\\n{status}" color="{fg}" fillcolor="{bg}" fontcolor="{fg}"];'
        )
    for i in range(len(order) - 1):
        lbl = ""
        if versions and order[i] == "context.reconcile":
            lbl = f' [label=" v{versions[0]} -> v{versions[1]} " fontsize=9 fontcolor="#57606a"]'
        lines.append(f"  n{i} -> n{i+1}{lbl};")
    lines.append("}")
    return "\n".join(lines)


def render_span_tree(view: TraceView, max_depth: int = 3) -> None:
    """The trace, as a readable tree. LLM calls carry their context version inline."""
    if not view.ok:
        st.info(
            f"**Trace unavailable** — {view.error or 'no observations returned'}.\n\n"
            "The run's own stage timeline below is unaffected; it is read from ClickHouse."
        )
        return

    t = view.totals()
    c = st.columns(4)
    c[0].metric("Wall clock", f"{view.latency_s:.1f}s")
    c[1].metric("LLM calls", t["llm_calls"])
    c[2].metric("Output tokens", f"{t['output_tokens']:,}")
    c[3].metric("Cost", f"${t['cost_usd']:.4f}")
    if t["context_versions"]:
        st.caption(
            "Context versions consumed by LLM calls: "
            + ", ".join(f"v{v}" for v in t["context_versions"])
            + " — every generation records the snapshot it read, which is what makes "
            "the freshness claim checkable rather than asserted."
        )

    total = max(view.latency_s, 1e-6)

    def row(s: Span, depth: int) -> None:
        if depth > max_depth:
            return
        pad = "&nbsp;" * (depth * 4)
        share = min(1.0, s.latency_s / total)
        bar_w = max(1, int(share * 100))
        badge = (
            f'<span style="background:#ddf4ff;color:#0969da;padding:1px 6px;'
            f'border-radius:10px;font-size:11px;">LLM</span>'
            if s.is_llm else ""
        )
        cv = (
            f'<span style="color:#1a7f37;font-size:11px;"> ctx v{s.context_version}</span>'
            if s.context_version is not None else ""
        )
        tok = (
            f'<span style="color:#57606a;font-size:11px;"> {s.output_tokens:,} out-tok</span>'
            if s.output_tokens else ""
        )
        st.markdown(
            f'<div style="font-family:ui-monospace,monospace;font-size:12px;line-height:1.7">'
            f"{pad}{badge} <b>{s.name}</b>{cv}{tok} "
            f'<span style="color:#57606a">{s.latency_s:.2f}s</span>'
            f'<div style="{"" if depth else "margin-bottom:2px;"}margin-left:{depth*22}px;'
            f'background:#0969da22;width:{bar_w}%;height:3px;border-radius:2px"></div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        for ch in s.children:
            row(ch, depth + 1)

    for r in view.roots:
        row(r, 0)

    if view.url:
        st.link_button("Open the full trace in Langfuse", view.url)
        st.caption(
            "Opens in a new tab — Langfuse sends `frame-ancestors 'none'`, so it cannot "
            "be embedded here; this tree is rendered from its API instead."
        )
