"""RootCauseOS — Diagnosis page (tab 3): the root-cause read-out, in plain English.

An incident selector (and ?incident= deep link) picks the anomaly; the page then
answers six questions in order, for a reader who has never seen this system:

    What happened    → the metric, the size of the move, the days.
    Why it happened  → which factor in the funnel moved, and by how much.
    Where it is      → the segment we can name, and everything we cleared.
    What this means  → what it is worth, and what kind of problem it is.
    What to do next  → the playbook's triage steps.
    Proof            → every number, the query that produced it, and the SQL.

The first three and the last state what the DATA PROVES. The middle two state
what a STATED RULE (ui/playbook.py — a lookup table, no LLM) recommends, and say
so on the page: a recommendation must never be able to read as a measurement.

Every figure comes from the bundle. Nothing is invented, nothing is guessed, and
an absent value renders as "—" — never as 0, "?", "None", or an apology.

All wording (metric names, segment phrases, units, verdicts) comes from
`ui/explain.py`, the one shared vocabulary, so the page never calls the same
thing two different names.

This module is the page: selection, the shared context, and the order the
sections run in. The parts live next door —

    ui/rca_text.py      wording + number formatting   (pure, no Streamlit)
    ui/rca_bundle.py    bundle shape adapters         (pure, no Streamlit)
    ui/rca_sections.py  one function per section      (renders)

The dependency runs one way: text <- bundle <- sections <- here. Keep it that
way; a section importing this module would be a cycle.
"""
from __future__ import annotations

import streamlit as st

from ui import bundle as B
from ui import explain as X
from ui import incidents as I
from ui import nr_one as n

from ui.rca_text import (
    _UNIT_ALIAS,
    _baseline_sentence,
    _date,
    baseline_caption,
    _delta,
    _humanise,
    _identity_phrase,
    _in,
    _lede,
    _note,
    _num,
    _precise_pct,
    _same_fact,
    _seg_phrase,
    _verdict_words,
)
from ui.rca_bundle import (
    _culprit,
    _dec,
    _headline,
    _prose,
    _store,
    _window,
)
from ui.rca_sections import (
    _funnel_table,
    _head,
    _means,
    _narrative,
    _proof,
    _steps,
    _where,
)

# ------------------------------------------------------------------ selection

def _golden() -> dict | None:
    try:
        return B.load()
    except Exception:  # noqa: BLE001 — no golden bundle is a valid state
        return None


def _slim(incident_id: str) -> dict | None:
    doc = I._load_bundle()  # scan bundle (same file the incident cards use)
    for inv in (doc or {}).get("investigations", []):
        if inv.get("incident_id") == incident_id:
            return inv
    return None


def pick(incident_id: str | None) -> tuple[dict | None, bool, str]:
    """Resolve one incident's bundle: (bundle, full_depth, incident_id).

    The golden/full bundle wins when its incident window matches the
    selected card (matched on window start — the fixture has no card id)."""
    cards = I.incidents()
    ids = [c["id"] for c in cards]
    iid = incident_id if incident_id in ids else (ids[0] if ids else None)
    if iid is None:
        return None, False, ""
    card = next(c for c in cards if c["id"] == iid)
    inv = _slim(iid)
    # engine investigations carry their own real depth (decomposition +
    # evidence_store); render THAT. The golden fixture only outranks it when
    # explicitly pinned via RCOS_BUNDLE or when no engine/file inv exists.
    import os as _os
    engine_depth = bool(inv and (inv.get("decomposition") or inv.get("evidence_store")))
    g = _golden()
    golden_matches = bool(
        g and str(g.get("incident_window", {}).get("start", ""))[:10] == card["window"][0])
    if golden_matches and (_os.environ.get("RCOS_BUNDLE") or not engine_depth):
        return g, True, iid
    if inv:
        return inv, engine_depth, iid
    return (g, True, iid) if golden_matches else (None, False, iid)


def _selector(active: str) -> str:
    """Incident chips row — each a real link (?page=diagnosis&incident=…)."""
    chips = []
    for c in I.incidents():
        on = c["id"] == active
        style = (
            "display:inline-block;padding:5px 12px;margin:0 8px 6px 0;"
            "border-radius:3px;font-size:12px;font-weight:600;"
            "text-decoration:none;border:1px solid "
            + ("var(--nr-accent);color:var(--nr-accent);"
               "background:rgba(64,237,205,0.08)" if on else
               "var(--nr-border2);color:var(--nr-text2)")
        )
        chips.append(
            f'<a href="?page=diagnosis&incident={n.esc(c["id"])}'
            f'{"&theme=dark" if st.query_params.get("theme") == "dark" else ""}" target="_self" '
            f'style="{style}">{n.esc(c["id"])} · {n.esc(c["title"])}</a>')
    return ('<div style="margin:2px 0 14px">'
            '<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;'
            'text-transform:uppercase;color:var(--nr-text3);margin-bottom:6px">'
            'Root-cause analysis · pick an anomaly</div>'
            + "".join(chips) + "</div>")


# ---------------------------------------------------------------- render

def render_page(incident_sel: str | None) -> None:
    b, full, iid = pick(incident_sel)
    st.markdown(_selector(iid), unsafe_allow_html=True)
    if not b:
        st.markdown(n.empty_state("Nothing to read out for this anomaly",
                                  "no investigation was stored for it"),
                    unsafe_allow_html=True)
        return
    render(b, full=full, incident_id=iid)


def _compared_with(baseline_window) -> str:
    """Subtitle line. Says which days the engine really compared against — a short slice falls
    back to nearest-days, and this used to claim 'same weekdays' regardless."""
    cap = baseline_caption(baseline_window)
    if cap == "no comparable period":
        return "No comparable period was available, so the split was not computed."
    return f"Compared with the {cap} the incident."


def render(b: dict, full: bool = True, incident_id: str = "") -> None:
    """The whole read-out. `full` is kept for the caller's signature only —
    depth is now shown by what renders, never announced as pending."""
    metric = str(b.get("metric") or "")
    mname = X.metric_name(metric)
    meaning = X.metric_meaning(metric)
    verdict = str(b.get("verdict") or "")
    tone = B.VERDICT_META.get(verdict, ("info", "info", verdict))[0]
    v_chip = n.chip(X.verdict_label(verdict), tone) if verdict else ""
    w = _window(b)
    d_from, d_to = _date(w.get("start")), _date(w.get("end"))
    h = _headline(b)
    unit = _UNIT_ALIAS.get(str(h.get("unit") or "").lower()) or X.metric_unit(metric)
    delta = h.get("delta_pct")
    c = _culprit(b)
    seg = _seg_phrase(c.get("dimension", ""), c.get("value", ""), c.get("co_cut")) if c else ""
    dec = _dec(b)
    factors = [f for f in dec.get("factors", []) if f.get("factor")]
    store = _store(b)

    when = (f"{d_from} to {d_to}" if d_from and d_to and d_from != d_to
            else d_from or d_to or "")

    # ---------------------------------------------------------- page head
    st.markdown(
        '<div class="nr-pagehead">'
        f'<div class="crumbs">Root-cause read-out'
        + (f' · {n.esc(incident_id)}' if incident_id else "")
        + "</div>"
        f'<div class="title">{n.esc(mname)} — what moved, and why {v_chip}</div>'
        '<div class="subtitle">'
        + n.esc(f"{mname} is {meaning}. " if meaning else "")
        + n.esc(f"Incident days {when}. " if when else "")
        + n.esc(_compared_with(dec.get("baseline_window")))
        + "</div></div>",
        unsafe_allow_html=True)

    # ------------------------------------------------------ what happened
    _head("What happened")
    if delta is not None:
        sentence = (f"{mname}"
                    + (f" — {meaning} — " if meaning else " ")
                    + f"{X.direction_word(delta)} {abs(float(delta)):.1f}%"
                    + (f" {_in(seg)}" if seg else " across the whole business")
                    + (f" over {when}." if when else "."))
    else:
        sentence = (f"{mname} moved"
                    + (f" {_in(seg)}" if seg else "")
                    + (f" over {when}." if when else "."))
    st.markdown(_lede(sentence, 16), unsafe_allow_html=True)

    tiles = []
    if h.get("observed") is not None:
        tiles.append(n.kpi_tile(f"{mname} observed", _num(h["observed"], unit),
                                when or "incident days"))
    if h.get("baseline") is not None:
        tiles.append(n.kpi_tile(f"{mname} normally", _num(h["baseline"], unit),
                                baseline_caption(dec.get("baseline_window"))))
    if delta is not None:
        tiles.append(n.kpi_tile("Change", X.fmt_delta(delta),
                                (_in(seg) if seg else "across every segment"),
                                "down" if float(delta) < 0 else "up"))
    if tiles:
        st.markdown(n.kpi_row(tiles), unsafe_allow_html=True)

    v_says = X.verdict_sentence(verdict)
    if v_says:
        st.markdown(
            f'<div style="margin:8px 0 2px">{v_chip}'
            f'<span style="font-size:13.5px;color:var(--nr-text2);margin-left:9px">'
            f'{n.esc(v_says)}</span></div>', unsafe_allow_html=True)

    # ------------------------------------------------------ why it happened
    why = b.get("why") or {}
    lead = str(why.get("sentence") or "").strip()
    driver = next((f for f in factors
                   if _verdict_words(f.get("verdict", ""))[0] == "primary"), None)
    share_mode = abs(sum(abs(float(f.get("pct_effect") or 0))
                         for f in factors) - 100.0) <= 5.0
    if not lead and driver:
        dev = driver.get("deviation_pct")
        share = driver.get("pct_effect")
        lead = (f"{X.metric_name(driver.get('factor', ''))} is what moved: it "
                f"{X.direction_word(dev)} {abs(float(dev)):.1f}%"
                if dev is not None else
                f"{X.metric_name(driver.get('factor', ''))} is what moved")
        if share is not None and share_mode:
            lead += f", which is {_num(abs(float(share)), 'pct')} of the whole change."
        else:
            lead += " — the largest single effect in the funnel."
    # `lead` is built by ui/incidents.py THROUGH ui/explain.py, so it is already in the
    # shared vocabulary. Running _humanise over it again re-expands its own gloss —
    # "(revenue per 1,000 impressions)" came back as "(Revenue per 1,000 Impressions)".
    # _humanise is for text the ENGINE wrote, not for text we already wrote.
    body = _lede(lead) if lead else ""
    # One fact, said once. `mechanism` is set to why.sentence upstream and the narrated
    # prose restates it in the engine's own words — rendering all three put the same
    # sentence on screen three times.
    mech = str(b.get("mechanism") or "").strip()
    if mech and not _same_fact(mech, lead):
        body += _lede(_humanise(mech), 13.5)
    if _prose(b) and not lead:
        body += _narrative(b, store)
    if body or factors:
        _head("Why it happened", "the one thing inside the funnel that moved")
    if body:
        st.markdown(n.card("", "", body), unsafe_allow_html=True)

    if factors:
        notes: list[str] = []
        loud = [f for f in factors
                if _verdict_words(f.get("verdict", ""))[0] == "ruled out"
                and abs(float(f.get("pct_effect") or 0)) >= 5.0]
        if loud and share_mode:
            names = " and ".join(X.metric_name(f.get("factor", "")) for f in loud)
            notes.append(
                f'"Ruled out" means the factor stayed inside its normal range — not that '
                f"its share is zero. {names} still carries a share of the arithmetic "
                f"because it did move a little; it just moved no more than it usually does.")
        if (delta is not None and driver is not None
                and driver.get("deviation_pct") is not None
                and abs(float(driver["deviation_pct"]) - float(delta)) > 0.05):
            notes.append(
                f"Two different quantities, both real: the headline "
                f"{X.fmt_delta(delta)} is how much {mname} moved"
                + (f" {_in(seg)}" if seg else "")
                + f", while {_delta(driver['deviation_pct'])} below is how much the "
                  f"{X.metric_name(driver.get('factor', ''))} factor moved across the whole "
                  f"incident window.")
        # One honest sentence about the maths instead of four lines of method jargon.
        # The nuance the engine's own note makes and that must survive: the factors
        # multiply out exactly, so a zero leftover is guaranteed and proves nothing —
        # the agreement between two independent methods is the only real check. Method
        # names stay, in a trailing parenthetical, because they are citable.
        cross = None
        if dec.get("max_divergence_pct") is not None and dec.get("cross_check"):
            cross = (
                f"The split was worked out two independent ways and they agree to within "
                f"{_precise_pct(dec['max_divergence_pct'])}. That agreement is the real "
                f"check: the factors multiply out exactly, so a zero leftover is "
                f"guaranteed by the arithmetic and proves nothing on its own. "
                f"Method: {dec.get('method', 'the decomposition')}, cross-checked "
                f"against {dec['cross_check']}.")
            notes.append(cross)
        elif dec.get("reconciliation_note"):      # no cross-check to report — keep the caveat
            notes.append(_humanise(dec["reconciliation_note"]))
        if dec.get("identity"):
            notes.append(
                "The factors multiply together to give revenue per day, so between them "
                "they account for the whole change — nothing is left unexplained: "
                + _identity_phrase(dec["identity"]) + ".")
        if dec.get("baseline_window"):
            notes.append(_baseline_sentence(dec["baseline_window"]))
        st.markdown(
            n.card("Factor by factor", "", _funnel_table(factors, share_mode, mname)
                   + "".join(_note(x) for x in notes)),
            unsafe_allow_html=True)

    # the waterfall only reads correctly when the headline measures the SAME
    # quantity the factors decompose (revenue). For an eCPM incident the factors
    # decompose revenue while the headline is eCPM — a waterfall there would be
    # dimensionally wrong, so the share bars above carry the story instead.
    if (factors and metric == "revenue" and h.get("observed") is not None
            and h.get("baseline") is not None):
        base, obs = float(h["baseline"]), float(h["observed"])
        moves = [{"label": X.metric_name(f.get("factor", "")),
                  "contribution": float(f.get("pct_effect") or 0) / 100.0 * base}
                 for f in factors if f.get("pct_effect") is not None]
        if moves:
            st.markdown(n.card("From normal to observed",
                               "each factor's slice of the move",
                               n.svg_waterfall(base, moves, observed=obs,
                                               metric=metric, unit=unit)),
                        unsafe_allow_html=True)

    _where(b, seg=seg, c=c, mname=mname, verdict=verdict, delta=delta)
    _means(b, seg=seg, dec=dec)
    _steps(b)
    _proof(b, store=store)
