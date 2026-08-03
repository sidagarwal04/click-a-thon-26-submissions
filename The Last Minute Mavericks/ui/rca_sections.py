"""RootCauseOS — RCA read-out sections.

One function per section of the read-out. Each takes the bundle plus the
context ui/diagnosis.py already computed, and writes to Streamlit.

The evidence sections state what the DATA PROVES. `_means` and `_steps`
state what a STATED RULE (ui/playbook.py, a lookup table with no LLM)
recommends, and say so on the page — a recommendation must never be able
to read as a measurement.

Split out of ui/diagnosis.py — see that module for the page itself.
"""
from __future__ import annotations

import streamlit as st

from ui import bundle as B
from ui import explain as X
from ui import nr_one as n

from ui.rca_text import (
    _DASH,
    _cite,
    _delta,
    _facts,
    _humanise,
    _in,
    _lede,
    _measured,
    _note,
    _num,
    _seg_phrase,
    _verdict_words,
)
from ui.rca_bundle import (
    _ev_label,
    _ev_unit,
    _factor_unit,
    _pb,
    _prose,
)

_HYP_TONE = {"supported": ("crit", "What the evidence supports"),
             "ruled_out": ("ok", "Checked and cleared"),
             "inconclusive": ("info", "Not enough evidence either way")}

# ui/playbook.py returns enums; a reader needs sentences. These are UI copy for a
# STATED RULE — never a measurement, and worded so they can never read as one.
_ORIGIN = {
    "internal": "This started inside the business — something in how we serve or price "
                "ads changed, not the market around it.",
    "external": "This started outside the business — advertiser demand, a platform or a "
                "partner behaved differently, not our own systems.",
    "indeterminate": "The evidence does not settle whether this started inside the "
                     "business or outside it.",
}

_CONTROL = {
    "controllable": "It is fixable on our side.",
    "partially": "Part of it is fixable on our side; the rest can only be managed and "
                 "watched.",
    "uncontrollable": "There is no fix on our side — the sensible response is to absorb "
                      "it and watch until it returns to normal.",
}

_URGENCY = {"now": ("Right now", "crit"),
            "today": ("Today", "warn"),
            "monitor": ("Keep watching", "info")}


# ------------------------------------------------------------ page furniture

def _head(title: str, sub: str = "") -> None:
    """A plain section heading — no numbers, no internal contract references."""
    st.markdown(f'<div class="nr-section"><span class="title">{n.esc(title)}</span>'
                + (f'<span class="subtitle">{n.esc(sub)}</span>' if sub else "")
                + "</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ narrative

def _narrative(b: dict, store: dict) -> str:
    """The engine's own sentences, with every cited number resolved to its query."""
    parts: list[str] = []
    src = {**b, "evidence_store": store, "diagnosis": _prose(b)}
    for kind, payload in B.diagnosis_tokens(src):
        if kind == "text":
            parts.append(n.esc(_humanise(payload)))
            continue
        if kind == "ev":
            e = store.get(payload) or {}
            shown = _num(e.get("value"), _ev_unit(e))
            parts.append(
                f'<span class="nr-ev" title="{n.esc(_ev_label(e.get("label", "")))} · '
                f'query {n.esc(e.get("query_id", "") or "not recorded")}">{n.esc(shown)}'
                f'<small>{n.esc(_cite(payload))}</small></span>')
            continue
        parts.append(f'<span class="nr-ev nr-ev--unresolved">{n.esc(payload)}'
                     f'<small>no query behind this number</small></span>')
    return f'<div class="nr-prose">{"".join(parts)}</div>'


# ------------------------------------------------------------- funnel table

def _share_cell(pct, biggest: float, driver: bool) -> str:
    if pct is None:
        return f'<td class="num">{_DASH}</td>'
    width = min(abs(float(pct)) / biggest * 100.0, 100.0) if biggest else 0.0
    fill = "var(--nr-accent)" if driver else "var(--nr-border2)"
    return (
        '<td class="num"><div style="display:flex;align-items:center;gap:8px;'
        'justify-content:flex-end">'
        f'<span style="font-variant-numeric:tabular-nums">{n.esc(_num(pct, "pct"))}</span>'
        '<span style="display:inline-block;width:64px;height:6px;border-radius:2px;'
        'background:var(--nr-border);overflow:hidden">'
        f'<span style="display:block;height:100%;width:{width:.1f}%;background:{fill}">'
        '</span></span></div></td>')


def _funnel_table(factors: list[dict], share_mode: bool, metric_name: str) -> str:
    biggest = max((abs(float(f.get("pct_effect") or 0)) for f in factors), default=0.0)
    effect_head = ("Share of the change" if share_mode
                   else f"Effect on {metric_name.lower()}")
    # a column every factor leaves empty is a column of dashes — drop it
    levels = any(f.get("window_value") is not None or f.get("baseline") is not None
                 for f in factors)
    moves = any(f.get("deviation_pct") is not None for f in factors)
    heads = (["What"] + (["In these days", "Normally"] if levels else [])
             + (["How much it moved"] if moves else []) + [effect_head, "Verdict"])
    body: list[str] = []
    for f in factors:
        unit = _factor_unit(f)
        tag, says = _verdict_words(f.get("verdict", ""))
        driver = tag == "primary"
        name = X.metric_name(f.get("factor", ""))
        meaning = X.metric_meaning(f.get("factor", ""))
        row_style = ' style="background:var(--nr-accent-a08)"' if driver else ""
        first = (f'<div style="font-weight:600;color:var(--nr-text)">{n.esc(name)}'
                 + (f' {n.chip("primary driver", "info")}' if driver else "")
                 + "</div>"
                 + (f'<div style="font-size:11px;color:var(--nr-text3)">{n.esc(meaning)}'
                    "</div>" if meaning else ""))
        verdict_cell = (f'<div style="font-weight:600;color:'
                        + ("var(--nr-accent)" if driver else "var(--nr-text2)")
                        + f'">{n.esc(tag)}</div>'
                        + (f'<div style="font-size:11px;color:var(--nr-text3)">'
                           f'{n.esc(says)}</div>' if says else ""))
        cells = f"<td>{first}</td>"
        if levels:
            cells += (f'<td class="num">{n.esc(_num(f.get("window_value"), unit))}</td>'
                      f'<td class="num">{n.esc(_num(f.get("baseline"), unit))}</td>')
        if moves:
            cells += f'<td class="num">{n.esc(_delta(f.get("deviation_pct")))}</td>'
        body.append(f"<tr{row_style}>{cells}"
                    + _share_cell(f.get("pct_effect"), biggest, driver)
                    + f"<td>{verdict_cell}</td></tr>")
    head = "".join(f"<th>{n.esc(h)}</th>" for h in heads)
    return (f'<div class="nr-table-wrap"><table class="nr-table"><thead><tr>{head}</tr>'
            f'</thead><tbody>{"".join(body)}</tbody></table></div>')


def _where(b: dict, *, seg: str, c: dict, mname: str, verdict: str, delta) -> None:
    """Where the move lives, and everything the engine checked and cleared."""
    _head("Where it is",
          "the segment we can name, and what we cleared" if seg
          else "why no single segment is to blame, and what we cleared")
    if seg:
        moved = (_delta(float(c["relative_change"]) * 100)
                 if c.get("relative_change") is not None
                 else (_delta(c.get("deviation_pct")) if c.get("deviation_pct") is not None
                       else (_delta(delta) if delta is not None else "")))
        facts = [
            (f"{mname} here moved", moved),
            ("share of the whole move", _num(c.get("contribution_share_pct"), "pct")),
            ("in these days", _num(c.get("segment_observed"), "rate")),
            ("normally", _num(c.get("segment_baseline"), "rate")),
            ("requests in this segment", _num(c.get("denominator"), "int")),
        ]
        body = _lede(f"The move is concentrated {_in(seg)}.")
        body += _facts(facts)
        if c.get("counterfactual_impact_fills") is not None:
            body += _note(
                f"If this segment had behaved normally, "
                f"{_num(abs(float(c['counterfactual_impact_fills'])), 'int')} more "
                f"requests would have been filled.")
        if c.get("ev"):
            body += _note(f"Evidence {_cite(c['ev'])} in the ledger below.")
        st.markdown(n.card(seg, X.verdict_label(verdict) if verdict else "",
                           body, tone="crit"),
                    unsafe_allow_html=True)
    else:
        st.markdown(n.card(X.verdict_label(verdict) if verdict
                           else "No responsible segment", "",
                           _lede(X.verdict_sentence(verdict)
                                 or "No single segment carries this move."),
                           tone="info"),
                    unsafe_allow_html=True)

    ruled = b.get("ruled_out") or []
    if ruled:
        rows = []
        for r in ruled:
            if isinstance(r, dict):
                rows.append([_seg_phrase("", r.get("segment", "")),
                             _delta(r.get("deviation_pct")),
                             _humanise(r.get("why", ""))])
            else:
                rows.append([_DASH, _DASH, _humanise(r)])
        st.markdown(
            n.card(f"Looked at and cleared ({len(rows)})",
                   "these moved too, but none of them is the cause",
                   n.table_html(["Segment", "It moved", "Why it is not the cause"],
                                rows, aligns=["", "num", ""])),
            unsafe_allow_html=True)

    hyps = b.get("hypotheses") or {}
    for key in ("supported", "ruled_out", "inconclusive"):
        items = hyps.get(key) or []
        if not items:
            continue
        tone_, title_ = _HYP_TONE[key]
        rows = [[_humanise(x.get("hypothesis", "")),
                 x.get("computed", _DASH) or _DASH,
                 x.get("threshold", _DASH) or _DASH,
                 _cite(x.get("ev", ""))] for x in items]
        st.markdown(
            n.card(f"{title_} ({len(items)})", "",
                   n.table_html(["Idea we tested", "What we measured",
                                 "What would have counted", "Evidence"],
                                rows, aligns=["", "num", "", "mono"]),
                   tone=tone_),
            unsafe_allow_html=True)

    g = b.get("uniformity_gate") or {}
    kids = g.get("children") or []
    if kids:
        rows = [[_seg_phrase("", k.get("child", "")),
                 _num(k.get("observed"), "rate"), _num(k.get("expected"), "rate"),
                 _delta((k.get("relative") or 0) * 100),
                 _num(k.get("denominator"), "int")] for k in kids]
        st.markdown(
            n.card("The same story everywhere inside it",
                   _humanise(g.get("interpretation", "")),
                   n.table_html(["Where", "In these days", "Normally", "Moved",
                                 "Requests"], rows,
                                aligns=["", "num", "num", "num", "num"])),
            unsafe_allow_html=True)

    gates = b.get("gate_funnel") or []
    if len(gates) >= 2:
        st.markdown(_note(
            f"We scored {_num(gates[0].get('remaining'), 'int')} candidate segments; "
            f"{_num(gates[-1].get('remaining'), 'int')} survived every check."),
            unsafe_allow_html=True)


def _means(b: dict, *, seg: str, dec: dict) -> None:
    """What the move is worth, and what kind of problem a stated rule says it is.

    Two different kinds of claim live here and the wording keeps them apart: the
    money is MEASURED (the engine emitted it); the origin/controllability reading
    is a LOOKUP in ui/playbook.py — guidance, never a finding.
    """
    pb = _pb(b)
    origin_key = str(pb.get("origin") or "").strip().lower()
    origin = _ORIGIN.get(origin_key, "")
    control = _CONTROL.get(str(pb.get("controllable") or "").strip().lower(), "")
    per_day = dec.get("delta_revenue_per_day")
    money = ""
    if per_day is not None:
        try:
            amount = X.fmt_value(abs(float(per_day)), "usd")
            money = (f"While this lasts, that is {amount} "
                     + ("more" if float(per_day) >= 0 else "less")
                     + " revenue per day"
                     + (f" {_in(seg, 'from')}" if seg else "") + ".")
        except (TypeError, ValueError):
            money = ""
    if not (money or origin or control):
        return

    _head("What this means", "what it is worth, and what kind of problem it is")
    if money:
        st.markdown(
            n.card("", "", _lede(money)
                   + _note("Measured over the incident window by the same queries as the "
                           "evidence below — not an estimate.")),
            unsafe_allow_html=True)
    if not (origin or control):
        return

    body = ""
    if origin:
        body += _lede(origin, 14)
    if control:
        body += _lede(control, 14)
    if origin_key == "indeterminate":
        first = [str(a.get("title") or a.get("text") or "").strip()
                 for a in (pb.get("actions") or [])
                 if str(a.get("urgency") or "").lower() == "now"]
        if first:
            joined = " and ".join(_humanise(t)[:1].lower() + _humanise(t)[1:] for t in first)
            body += _note(f"What would settle it: {joined}. Whichever of those comes back "
                          f"changed is the side this started on.")
        else:
            body += _note("Nothing in the evidence bundle separates the two — settling it "
                          "needs a check outside this data.")
    body += _note("This is how a stated rule reads the result. The sections above are what "
                  "the queries measured; this one is guidance.")
    st.markdown(n.card("What kind of problem this is",
                       "suggested reading, not a measurement", body, tone="info"),
                unsafe_allow_html=True)


def _steps(b: dict) -> None:
    """The playbook's ordered triage steps — presented as advice, with provenance."""
    pb = _pb(b)
    acts = [a for a in (pb.get("actions") or b.get("actions") or []) if isinstance(a, dict)]
    why = _humanise(str(pb.get("rule_explanation") or "").strip())
    note = str(pb.get("confidence_note") or "").strip()
    rule_id = str(pb.get("rule_id") or "").strip()
    if not (acts or why):
        return

    _head("What to do next",
          "suggested steps from the playbook — not conclusions drawn from the data")
    if not acts:
        st.markdown(n.card("No action indicated", "", _lede(why) if why else "", tone="ok"),
                    unsafe_allow_html=True)
    else:
        seen = 0
        groups = [(k, [a for a in acts
                       if str(a.get("urgency") or "").strip().lower() == k])
                  for k in _URGENCY]
        # anything with an unrecognised urgency still has to be shown
        groups.append(("", [a for a in acts
                            if str(a.get("urgency") or "").strip().lower() not in _URGENCY]))
        for key, group in groups:
            if not group:
                continue
            label, tone = _URGENCY.get(key, ("Then", "info"))
            rows = ""
            for a in group:
                seen += 1
                title = _humanise(str(a.get("title") or a.get("text") or "").strip())
                detail = _humanise(str(a.get("detail") or "").strip())
                rows += (
                    '<div style="display:flex;gap:11px;align-items:baseline;margin:9px 0">'
                    '<span style="font-size:11px;font-weight:700;color:var(--nr-text3);'
                    'border:1px solid var(--nr-border2);border-radius:3px;padding:1px 6px;'
                    f'flex:none">{seen}</span><div>'
                    f'<div style="font-size:13px;font-weight:600;color:var(--nr-text)">'
                    f'{n.esc(title)}</div>'
                    + (f'<div style="font-size:12px;color:var(--nr-text3);line-height:1.55;'
                       f'margin-top:2px">{n.esc(detail)}</div>' if detail else "")
                    + "</div></div>")
            st.markdown(n.card(label, f"{len(group)} step{'s' if len(group) > 1 else ''}",
                               rows, tone=tone),
                        unsafe_allow_html=True)

    st.markdown(_note("These steps come from a fixed rule table, not from the query "
                      "results — the evidence sections state what the data proves, this "
                      "section states what the playbook recommends."),
                unsafe_allow_html=True)
    if why or note or rule_id:
        with st.expander("Why these steps appeared"):
            if rule_id:
                st.caption(f"Matched rule: {rule_id}")
            if why:
                st.caption(why)
            if note:
                st.caption(note)


def _proof(b: dict, *, store: dict) -> None:
    """The ledger: every number, its query, its SQL, and what it cannot prove."""
    trace = b.get("trace_url") or (b.get("trace") or {}).get("langfuse_trace_url") or ""
    trace = "" if "REPLACE" in str(trace) else trace
    if store or trace:
        _head("Proof", "every number above, and the query that produced it")
    if store:
        rows = []
        for eid, e in store.items():
            rows.append([_cite(eid), _ev_label(e.get("label", "")),
                         _num(e.get("value"), _ev_unit(e)),
                         e.get("query_id") or _DASH,
                         _measured(e.get("rows_read")),
                         _measured(e.get("duration_ms"), " ms")])
        st.markdown(
            n.table_html(["#", "What was measured", "Value", "ClickHouse query id",
                          "Rows read", "Took"], rows,
                         aligns=["mono", "", "num", "mono", "num", "num"]),
            unsafe_allow_html=True)
        shared = len(rows) - len({r[3] for r in rows})
        if shared > 0:
            st.markdown(_note(
                "Several rows share one query id on purpose: a single query computes "
                "every factor in the funnel for this segment, so each number it "
                "returns points back at the same execution."), unsafe_allow_html=True)
        sqls: list[tuple[str, str]] = []
        for e in store.values():
            sql = str(e.get("sql") or "").strip()
            if sql and sql not in [s for _, s in sqls]:
                sqls.append((str(e.get("query_id") or ""), sql))
        if sqls:
            with st.expander(f"Show the SQL behind these numbers ({len(sqls)})"):
                for qid, sql in sqls:
                    if qid:
                        st.caption(f"query id {qid}")
                    st.code(sql, language="sql")

    if trace:
        st.markdown(
            f'<div style="margin:8px 0"><a href="{n.esc(trace)}" target="_blank" '
            f'style="font-size:12.5px;color:var(--nr-accent);text-decoration:none">'
            f'Open the step-by-step trace of this investigation →</a></div>',
            unsafe_allow_html=True)

    foot: list[tuple[str, str]] = []
    scores = b.get("scores") or {}
    if scores.get("localization_confidence") is not None:
        foot.append(("how confident we are in the segment",
                     _num(scores["localization_confidence"], "num")))
    if scores.get("explained_variance") is not None:
        foot.append(("share of the move explained",
                     _num(float(scores["explained_variance"]) * 100, "pct")))
    if scores.get("hypotheses_eliminated") is not None:
        foot.append(("ideas eliminated", _num(scores["hypotheses_eliminated"], "int")))
    lim = "; ".join(str(x) for x in (b.get("limitations") or []))
    if lim:
        foot.append(("what this does not prove", lim[:220]))
    if foot:
        st.markdown(n.footnote(foot), unsafe_allow_html=True)
