"""RootCauseOS — Investigation Storyboard (tab 2: Incidents).

One self-contained HTML document for streamlit components.html:
- INCIDENT TILES: 2x2 grid, each tile = the SAME n.svg_line_chart the\n  Metrics view uses (band, breach dots, shaded window) for that incident's
  primary metric — overlapping incidents can never collide. A synced
  crosshair tracks the hovered date across all tiles; click = activate.
- STORY VIEW: the active incident as a four-step guided case file
  (Anomaly → Investigation → Verdict → Action) with a stepper, Prev/Next,
  clickable dots and keyboard navigation (←/→ steps, ↑/↓ incidents).

Data comes ONLY from ui.incidents.incidents() plus the caller's daily
rows — no network calls. "Ask AI about this incident" writes one line
to sessionStorage['rcos-chat-seed']; the chat dock polls that key.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import streamlit as st

from ui import nr_one as n
from ui import incidents as I

# ----------------------------------------------------------- timeline math
# Fallback span only — the real axis derives from the caller's daily rows
# and the incidents' windows (see _span), so any new dataset re-anchors it.
_T0 = date(2026, 6, 1)
_DAYS = 35.0
_STEP_LABELS = ["Anomaly", "Investigation", "Verdict", "Action"]


def _span(incidents: list[dict], days: list[dict]) -> tuple[date, float]:
    """(t0, n_days) covering all daily rows and all incident windows."""
    ds: list[date] = []
    for r in days or []:
        try:
            ds.append(date.fromisoformat(str(r.get("d", ""))[:10]))
        except ValueError:
            pass
    for inc in incidents or []:
        for iso in inc.get("window", []):
            try:
                ds.append(date.fromisoformat(str(iso)[:10]))
            except ValueError:
                pass
    if not ds:
        return _T0, _DAYS
    t0, t1 = min(ds), max(ds)
    return t0, float(max((t1 - t0).days + 1, 7))


def _off(iso: str, t0: date, n_days: float) -> float:
    """Day offset of an ISO date from the axis start, clamped to span."""
    try:
        d = (date.fromisoformat(str(iso)[:10]) - t0).days
    except ValueError:
        return 0.0
    return float(max(0, min(int(n_days), d)))


def _pct(day_offset: float, n_days: float) -> float:
    return max(0.0, min(100.0, day_offset / n_days * 100.0))


def _rgba(hex_color: str, alpha: float) -> str:
    """Token hex -> rgba() so every color stays traceable to n.T."""
    h = hex_color.lstrip("#")
    return (f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},"
            f"{int(h[4:6], 16)},{alpha})")


# -------------------------------------------------------------- lane html
_METRIC_KIND = {"revenue": "usd", "requests": "int", "fill_rate": "rate",
                "ecpm": "usd", "ctr": "rate", "render_rate": "rate"}
_METRIC_TITLE = {"revenue": "Revenue", "requests": "Requests",
                 "fill_rate": "Fill rate", "ecpm": "eCPM", "ctr": "CTR",
                 "render_rate": "Render rate"}


def _ribbon(incidents: list[dict], days: list[dict]) -> str:
    """Incident tiles, Metrics-view grammar: a 2x2 grid where every tile
    renders n.svg_line_chart — the exact chart component the metrics grid
    uses (median±2·MAD band, gridlines, red breach points, shaded incident
    window) — for that incident's primary metric. A synced crosshair with
    the grid's own geometry constants tracks the hovered date across all
    tiles. Click a tile = activate its story (shared .iw class)."""
    t0, n_days = _span(incidents, days)
    labels = [(t0 + timedelta(days=k)).isoformat() for k in range(int(n_days))]
    by_date = {str(r.get("d", ""))[:10]: r for r in days or []}
    lanes_html: list[str] = []
    ldata: dict = {"labels": labels, "lanes": []}
    for inc in incidents:
        iid = inc.get("id", "")
        metric = (inc.get("panes") or ["revenue"])[0]
        w = inc.get("window", ["", ""])
        vals, series = [], []
        for dstr in labels:
            r = by_date.get(dstr)
            v = r.get(metric) if r else None
            vals.append(float(v) if v is not None else None)
            if v is not None:
                series.append({"label": dstr, "value": float(v)})
        chart = n.svg_line_chart(series, breached=True, start=w[0], end=w[1])
        # crosshair dot needs the chart's own y-scale (min/max ± 6% pad,
        # mirroring svg_line_chart)
        num = [v for v in vals if v is not None]
        lo = min(num) if num else 0.0
        hi = max(num) if num else 1.0
        pad = max(hi - lo, 1e-9) * 0.06
        ldata["lanes"].append({
            "id": iid, "title": _METRIC_TITLE.get(metric, metric),
            "kind": _METRIC_KIND.get(metric, "num"), "vals": vals,
            "lo": lo - pad, "hi": hi + pad, "n": len(series),
            "win": [w[0], w[1]],
        })
        # other incidents' windows as faint labeled context spans, so the
        # extra dips visible on this metric's line are explained ("that
        # crater is INC-B"), not mysterious. Click = jump to that story.
        # Geometry mirrors svg_line_chart: x(i) = PL + i*IW/(NP-1).
        others = []
        np_ = max(len(labels) - 1, 1)
        oi = 0
        for o in incidents:
            if o.get("id") == iid:
                continue
            ow = o.get("window", ["", ""])
            os_ = _off(ow[0], t0, n_days)
            oe = min(_off(ow[1], t0, n_days), float(len(labels) - 1))
            x0 = (52.0 + os_ * 650.0 / np_) / 720.0 * 100.0
            x1 = (52.0 + oe * 650.0 / np_) / 720.0 * 100.0
            # stagger the id labels across three rows so overlapping context
            # windows don't overprint into an unreadable smear
            others.append(
                f'<div class="oth" data-jump="{n.esc(o.get("id", ""))}" '
                f'title="{n.esc(o.get("id", ""))} — {n.esc(o.get("title", ""))} '
                f'(click to open)" '
                f'style="left:{x0:.2f}%;width:{max(x1 - x0, 1.0):.2f}%">'
                f'<i style="top:{1 + (oi % 3) * 13}px">{n.esc(o.get("id", ""))}</i></div>')
            oi += 1
        lanes_html.append(
            f'<div class="lane iw" data-inc="{n.esc(iid)}">'
            f'<div class="ll"><span class="lid">{n.esc(iid)}</span>'
            f'<span class="lti">{n.esc(inc.get("title", ""))}</span>'
            f'<span class="sev">{n.esc(inc.get("severity", "crit")).upper()}</span></div>'
            f'<div class="ls">{n.esc(_METRIC_TITLE.get(metric, metric))} · '
            f'window {n.esc(w[0])} → {n.esc(w[1])} · dashed = other incidents</div>'
            f'<div class="lc">{chart}{"".join(others)}'
            f'<div class="lx"></div><div class="ldot"></div>'
            f'</div></div>')
    return f"""<div class="lanes" id="lanes">{''.join(lanes_html)}
</div><div id="ltip"></div>
<script>
const LD = {json.dumps(ldata)};
const NL = LD.labels.length;
// geometry constants of nr_one.svg_line_chart — same as the metrics grid
const W=720,H=220,PL=52,PR=18,PT=18,PB=30,IW=W-PL-PR,IH=H-PT-PB;
function lfmt(v, k) {{
  if (v === null || v === undefined) return '—';
  if (k === 'usd') return '$' + v.toFixed(2);
  if (k === 'int') return Math.round(v).toLocaleString();
  return (v * 100).toFixed(2) + '%';
}}
(function () {{
  const lanes = [...document.querySelectorAll('.lane')];
  const tip = document.getElementById('ltip');
  function move(ev) {{
    const svg0 = ev.currentTarget.querySelector('.lc svg');
    if (!svg0) return;
    const r0 = svg0.getBoundingClientRect();
    const fx = (ev.clientX - r0.left) / r0.width * W;
    const i = Math.max(0, Math.min(NL - 1, Math.round((fx - PL) / IW * (NL - 1))));
    const day = LD.labels[i];
    let rows = '';
    lanes.forEach((ln, k) => {{
      const d = LD.lanes[k];
      const lc = ln.querySelector('.lc');
      const svg = lc.querySelector('svg');
      const lx = lc.querySelector('.lx');
      const dot = lc.querySelector('.ldot');
      const v = d.vals[i];
      if (!svg) {{ lx.style.display = 'none'; dot.style.display = 'none'; }}
      else {{
        const r = svg.getBoundingClientRect();
        const left = (PL + i * IW / Math.max(NL - 1, 1)) / W * r.width;
        lx.style.left = left + 'px'; lx.style.display = 'block';
        if (v === null || v === undefined) {{ dot.style.display = 'none'; }}
        else {{
          const yf = (PT + (d.hi - v) / Math.max(d.hi - d.lo, 1e-9) * IH) / H;
          dot.style.left = left + 'px';
          dot.style.top = (yf * r.height) + 'px';
          dot.style.display = 'block';
        }}
      }}
      const hot = d.win[0] <= day && day <= d.win[1];
      rows += '<div class="tr' + (hot ? ' hot' : '') + '"><span>' + d.id +
              ' · ' + d.title + (hot ? ' ⚠' : '') + '</span><span>' +
              lfmt(v, d.kind) + '</span></div>';
    }});
    tip.innerHTML = '<b>' + day + '</b>' + rows;
    tip.style.display = 'block';
    let tx = ev.clientX + 14;
    if (tx + 230 > document.documentElement.clientWidth) tx = ev.clientX - 244;
    tip.style.left = tx + 'px';
    tip.style.top = Math.max(4, Math.min(ev.clientY - 20,
      document.documentElement.clientHeight - 150)) + 'px';
  }}
  function leave() {{
    document.querySelectorAll('.lx,.ldot').forEach(el => el.style.display = 'none');
    tip.style.display = 'none';
  }}
  lanes.forEach(ln => {{
    ln.addEventListener('mousemove', move);
    ln.addEventListener('mouseleave', leave);
  }});
  document.querySelectorAll('.oth').forEach(o => o.addEventListener('click',
    (ev) => {{ ev.stopPropagation();
               if (window.setInc) setInc(o.dataset.jump); }}));
}})();
</script>"""


def _eyebrow_meta(n_incidents: int, t0: date, n_days: float) -> str:
    """Right-hand eyebrow: engine scan stats when a §8.1 bundle is loaded,
    else the plain date-range line."""
    from ui.incidents import scan_summary
    ss = scan_summary()
    if ss:
        found = ss.get("incidents_found")
        if found is None:
            found = n_incidents
        bits = [f'{found} real anomalies']
        if ss.get("candidates_checked"):
            bits.append(f'{ss["candidates_checked"]:,} candidates checked')
        if ss.get("ruled_out_lookalikes") is not None:
            bits.append(f'{ss["ruled_out_lookalikes"]} look-alikes ruled out by the engine')
        return " · ".join(bits)
    end = t0 + timedelta(days=int(n_days) - 1)
    return f"{t0.isoformat()} → {end.isoformat()} · {n_incidents} incidents"


# --------------------------------------------------------- story-view html
def _step_anomaly(inc: dict, data_through: str = "") -> str:
    h = inc.get("headline", {})
    w = inc.get("window", ["", ""])
    display = I.display_snapshot(inc, data_through)
    label = display["metric"] + (f' · {display["where"]}' if display["where"] else "")
    return (
        '<div class="step" data-step="0">'
        '<div class="sec">Step 1 · Anomaly detected</div>'
        f'<div class="big">{n.esc(h.get("delta", ""))}</div>'
        f'<div class="hl">{n.esc(label or h.get("label", ""))}</div>'
        '<div class="obx">'
        f'<div class="ob"><span class="obl">Observed</span>'
        f'<span class="obv red">{n.esc(h.get("observed", ""))}</span></div>'
        f'<div class="ob"><span class="obl">Expected</span>'
        f'<span class="obv">{n.esc(h.get("expected", ""))}</span></div>'
        f'<div class="ob"><span class="obl">Incident window</span>'
        f'<span class="obv">{n.esc(w[0])} → {n.esc(w[1])}</span></div>'
        + (f'<div class="ob"><span class="obl">Data through</span>'
           f'<span class="obv">{n.esc(data_through)}</span></div>' if data_through else "")
        + "</div></div>"
    )


def _step_investigation(inc: dict) -> str:
    d = inc.get("diagnosis", {})
    rows = "".join(
        f'<div class="kv"><b>{n.esc(key)}</b><span>{n.esc(d.get(key, ""))}</span></div>'
        for key in ("contribution", "uniformity", "confidence")
    )
    ruled = "".join(
        f'<div class="ro"><span class="ck">✓</span><span>{n.esc(r)}</span></div>'
        for r in inc.get("ruled_out", [])
    )
    from ui.incidents import SEARCH_SPACE
    turl = str(inc.get("trace_url") or "").strip()
    trace = (
        f'<a class="trc" href="{n.esc(turl)}" target="_blank">'
        'View Langfuse trace ↗</a>' if turl else
        '<span class="trc off" title="Every investigation step will link '
        'to its Langfuse span — trace publishing in progress">'
        'Langfuse trace · pending</span>'
    )
    return (
        '<div class="step" data-step="1">'
        '<div class="sec">Step 2 · Investigation</div>'
        f'<div class="ss">{n.esc(SEARCH_SPACE)}</div>'
        + rows +
        '<div class="sec">What we ruled out</div>' + ruled +
        f'<div class="trow">{trace}</div>'
        "</div>"
    )


def _step_verdict(inc: dict) -> str:
    d = inc.get("diagnosis", {})
    verdict = inc.get("verdict", "")
    v_cls = "loc" if verdict.startswith("LOCALIZED") else "glob"
    cause = I.display_snapshot(inc).get("where") or d.get("cause", "")
    return (
        '<div class="step" data-step="2">'
        '<div class="sec">Step 3 · Verdict</div>'
        f'<div class="vrow"><span class="vb {v_cls}">{n.esc(n.verdict_label(verdict))}</span>'
        f'<span class="cause">{n.esc(cause)}</span></div>'
        '<div class="sec">Mechanism</div>'
        f'<p class="mech">{n.esc(d.get("mechanism", ""))}</p>'
        + (f'<div class="trow"><a class="trc" '
           f'href="?page=diagnosis&incident={n.esc(inc.get("id", ""))}'
           f'{"&theme=dark" if st.query_params.get("theme") == "dark" else ""}" '
           f'target="_blank">Full RCA evidence — decomposition, gates, '
           f'ledger ↗</a></div>')
        + "</div>"
    )


def _step_action(inc: dict) -> str:
    acts = "".join(
        f'<div class="act"><span class="urg {n.esc(a.get("urgency", ""))}">'
        f'{n.esc(a.get("urgency", ""))}</span>'
        f'<span>{n.esc(a.get("text", ""))}</span></div>'
        for a in inc.get("actions", [])
    )
    return (
        '<div class="step" data-step="3">'
        '<div class="sec">Step 4 · What to do next</div>'
        + acts +
        '<div class="arow">'
        f'<button class="ask" data-inc="{n.esc(inc.get("id", ""))}">'
        "Ask AI what to do</button>"
        '<a class="back" href="?page=metrics" target="_blank">Open metrics ↗</a>'
        "</div></div>"
    )


def _case(inc: dict, active: bool = False, data_through: str = "") -> str:
    case_cls = "case on" if active else "case"
    return (
        f'<div class="{case_cls}" data-inc="{n.esc(inc.get("id", ""))}">'
        f'<div class="chead"><span class="cid">{n.esc(inc.get("id", ""))}</span>'
        f'<span class="ct">{n.esc(inc.get("title", ""))}</span>'
        f'<span class="csev">{n.esc(str(inc.get("severity", "crit")).upper())}</span></div>'
        + _step_anomaly(inc, data_through) + _step_investigation(inc)
        + _step_verdict(inc) + _step_action(inc)
        + "</div>"
    )


# ------------------------------------------------------------ the document
def html(incidents: list[dict], days: list[dict],
         selected: str | None = None, data_through: str = "") -> str:
    """The Investigation Storyboard as one self-contained HTML document."""
    incidents = incidents or []
    ids = [i.get("id", "") for i in incidents]
    active = selected if selected in ids else (ids[0] if ids else "")
    seeds = {
        i.get("id", ""): (f'Explain {i.get("id", "")} — the {i.get("title", "")} '
                          "— and what I should do")
        for i in incidents
    }
    ribbon = _ribbon(incidents, days)
    cases = "".join(_case(i, i.get("id", "") == active, data_through)
                     for i in incidents) or (
        '<div class="none">No incidents found in this scan.</div>')
    dots = "".join(
        f'<span class="sd" data-step="{k}"><i>{k + 1}</i>{n.esc(lbl)}</span>'
        + ('<span class="cnx"></span>' if k < 3 else "")
        for k, lbl in enumerate(_STEP_LABELS)
    )
    t = n.T
    red_bg, red_bg2 = _rgba(t["red"], 0.10), _rgba(t["red"], 0.22)
    red_bd, red_bd2 = _rgba(t["red"], 0.30), _rgba(t["red"], 0.55)
    acc_glow, acc_bd = _rgba(t["accent"], 0.85), _rgba(t["accent"], 0.50)
    acc_bg, grn_bg = _rgba(t["accent"], 0.08), _rgba(t["green"], 0.10)
    grn_bd, yel_bg = _rgba(t["green"], 0.35), _rgba(t["yellow"], 0.10)
    yel_bd = _rgba(t["yellow"], 0.35)
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
body {{ margin:0; padding:2px 2px 6px; background:{t['bg']};
  font-family:{t['font']}; color:{t['text']}; }}
.eyerow {{ display:flex; align-items:baseline; margin:2px 2px 8px; }}
.eb {{ font-size:10px; font-weight:700; letter-spacing:0.12em;
  text-transform:uppercase; color:{t['text3']}; }}
.ebm {{ margin-left:auto; font-size:10.5px; color:{t['text3']};
  font-family:ui-monospace,'SF Mono',Menlo,monospace; }}
.lanes {{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px;
  margin:0 0 14px; }}
.lane {{ background:{t['panel']}; border:1px solid {t['border']};
  border-radius:3px; padding:12px 14px 10px; cursor:pointer;
  transition:border-color 0.15s, background 0.15s; }}
.lane:hover {{ border-color:{t['border2']}; }}
.lane.active {{ border-color:{t['brand']}; background:{acc_bg}; }}
.ll {{ display:flex; align-items:baseline; gap:8px; overflow:hidden;
  white-space:nowrap; }}
.lid {{ font-size:10.5px; font-weight:700; letter-spacing:0.06em;
  color:{t['red']}; font-family:ui-monospace,'SF Mono',Menlo,monospace; }}
.lane.active .lid {{ color:{t['accent']}; }}
.lti {{ font-size:13.5px; font-weight:600; color:{t['text']};
  overflow:hidden; text-overflow:ellipsis; }}
.sev {{ margin-left:auto; font-size:9px; font-weight:700;
  letter-spacing:0.06em; color:{t['red']}; border:1px solid {red_bd2};
  border-radius:3px; padding:1px 6px; }}
.ls {{ font-size:10.5px; color:{t['text3']}; margin:2px 0 6px; }}
.lc {{ position:relative; }}
.lc svg {{ display:block; width:100%; height:auto; }}
.ss {{ font-size:11.5px; color:{t['text2']}; background:{acc_bg};
  border:1px solid {t['border']}; border-left:2px solid {t['accent']};
  border-radius:3px; padding:6px 10px; margin:2px 0 10px; }}
.trow {{ margin-top:10px; }}
.trc {{ display:inline-block; font-size:11.5px; font-weight:600;
  color:{t['accent']}; text-decoration:none;
  border:1px solid {acc_bd}; border-radius:3px;
  padding:4px 10px; }}
.trc:hover {{ border-color:{t['accent']}; }}
.trc.off {{ color:{t['text3']}; border-color:{t['border2']};
  cursor:default; }}
.oth {{ position:absolute; top:8.2%; bottom:13.7%;
  background:{_rgba(t['text2'], 0.06)}; border:1px dashed {_rgba(t['text2'], 0.30)};
  border-radius:2px; cursor:pointer; }}
.oth:hover {{ background:{acc_bg};
  border-color:{_rgba(t['accent'], 0.45)}; }}
.oth i {{ position:absolute; top:1px; right:3px; font-style:normal;
  font-size:9.5px; letter-spacing:0.04em; color:{t['text3']};
  font-family:ui-monospace,'SF Mono',Menlo,monospace; white-space:nowrap; }}
.oth:hover i {{ color:{t['accent']}; }}
.lx {{ position:absolute; top:0; bottom:0; width:1px; display:none;
  background:{t['accent']}; opacity:0.55; pointer-events:none; }}
.ldot {{ position:absolute; width:7px; height:7px; border-radius:50%;
  display:none; background:{t['accent']}; border:1px solid {t['bg']};
  transform:translate(-3.5px,-3.5px); pointer-events:none; }}
#ltip {{ position:fixed; display:none; z-index:40; pointer-events:none;
  min-width:210px; background:{t['panel2']}; border:1px solid {t['border2']};
  border-radius:3px; padding:7px 10px; }}
#ltip b {{ display:block; color:{t['accent']}; font-size:10.5px;
  margin-bottom:4px; font-family:ui-monospace,'SF Mono',Menlo,monospace; }}
#ltip .tr {{ display:flex; justify-content:space-between; gap:14px;
  font-size:11.5px; color:{t['text2']}; }}
#ltip .tr span:last-child {{ font-variant-numeric:tabular-nums;
  color:{t['text']}; }}
#ltip .tr.hot {{ color:{t['red']}; font-weight:600; }}
#ltip .tr.hot span:last-child {{ color:{t['red']}; }}
.story {{ background:{t['panel']}; border:1px solid {t['border']};
  border-radius:3px; }}
.chead {{ display:flex; align-items:baseline; gap:10px; padding:12px 14px;
  border-bottom:1px solid {t['border']}; }}
.cid {{ color:{t['accent']}; font-weight:700; font-size:12px;
  letter-spacing:0.06em; font-family:ui-monospace,'SF Mono',Menlo,monospace; }}
.ct {{ color:{t['text']}; font-weight:600; font-size:15px; }}
.csev {{ margin-left:auto; color:{t['red']}; background:{red_bg};
  border:1px solid {red_bd}; border-radius:3px; padding:1px 7px;
  font-size:10px; font-weight:700; letter-spacing:0.06em; }}
.stepper {{ display:flex; align-items:center; gap:10px; padding:10px 14px;
  border-bottom:1px solid {t['border']}; }}
.nav {{ background:transparent; border:1px solid {t['border2']};
  color:{t['text2']}; border-radius:3px; padding:3px 10px; font-size:11px;
  font-weight:600; font-family:inherit; cursor:pointer; }}
.nav:hover:not(:disabled) {{ color:{t['accent']}; border-color:{acc_bd}; }}
.nav:disabled {{ opacity:0.35; cursor:default; }}
.dots {{ flex:1; display:flex; align-items:center; justify-content:center;
  gap:6px; }}
.sd {{ display:inline-flex; align-items:center; gap:6px; cursor:pointer;
  font-size:11px; color:{t['text3']}; padding:2px 8px; border-radius:3px;
  border:1px solid transparent; }}
.sd:hover {{ color:{t['text']}; }}
.sd i {{ font-style:normal; width:16px; height:16px; border-radius:50%;
  border:1px solid {t['border2']}; display:inline-flex; align-items:center;
  justify-content:center; font-size:9.5px; font-weight:700;
  color:{t['text3']}; }}
.sd.on {{ color:{t['text']}; border-color:{t['border2']};
  background:{t['panel2']}; }}
.sd.on i {{ color:{t['bg']}; background:{t['accent']};
  border-color:{t['accent']}; }}
.sd.done i {{ color:{t['accent']}; border-color:{acc_bd}; }}
.cnx {{ width:16px; height:1px; background:{t['border2']}; }}
.case {{ display:none; }} .case.on {{ display:block; }}
.step {{ display:none; padding:14px 16px 16px; min-height:172px; }}
.step.on {{ display:block; }}
.sec {{ font-size:10px; font-weight:700; letter-spacing:0.12em;
  text-transform:uppercase; color:{t['text3']}; margin:14px 0 6px; }}
.step .sec:first-child {{ margin-top:0; }}
.big {{ font-size:28px; font-weight:600; color:{t['red']};
  font-variant-numeric:tabular-nums; }}
.hl {{ font-size:12px; color:{t['text2']}; margin-top:2px; }}
.obx {{ display:flex; gap:28px; margin-top:14px; flex-wrap:wrap; }}
.obl {{ display:block; font-size:10px; letter-spacing:0.06em;
  text-transform:uppercase; color:{t['text3']}; }}
.obv {{ display:block; font-size:15px; font-weight:600; color:{t['text']};
  font-variant-numeric:tabular-nums; margin-top:2px; }}
.obv.red {{ color:{t['red']}; }}
.kv {{ display:flex; gap:8px; font-size:12px; margin:4px 0;
  color:{t['text2']}; line-height:1.5; }}
.kv b {{ color:{t['text3']}; font-weight:600; min-width:96px;
  text-transform:uppercase; font-size:10px; letter-spacing:0.06em;
  padding-top:2px; }}
.ro {{ display:flex; gap:8px; font-size:12px; color:{t['text2']};
  line-height:1.5; margin:4px 0; }}
.ck {{ color:{t['green']}; font-weight:700; }}
.vrow {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.vb {{ display:inline-block; font-size:11px; font-weight:700;
  letter-spacing:0.05em; border-radius:3px; padding:2px 8px; }}
.vb.loc {{ color:{t['green']}; background:{grn_bg};
  border:1px solid {grn_bd}; }}
.vb.glob {{ color:{t['yellow']}; background:{yel_bg};
  border:1px solid {yel_bd}; }}
.cause {{ display:inline-block; color:{t['accent']}; background:{acc_bg};
  border:1px solid {acc_bd}; border-radius:3px; padding:2px 8px;
  font-size:12px; font-weight:600; }}
.mech {{ font-size:13px; line-height:1.65; color:{t['text']}; margin:4px 0; }}
.act {{ display:flex; gap:10px; align-items:baseline; margin:6px 0;
  font-size:12.5px; color:{t['text']}; }}
.urg {{ font-size:9.5px; font-weight:700; letter-spacing:0.06em;
  border-radius:3px; padding:1px 6px; text-transform:uppercase; }}
.urg.now {{ color:{t['red']}; border:1px solid {red_bd2}; }}
.urg.today {{ color:{t['yellow']}; border:1px solid {yel_bd}; }}
.arow {{ display:flex; align-items:center; gap:14px; margin-top:18px; }}
.ask {{ background:{t['brand']}; border:1px solid {t['brand2']};
  color:#fff; border-radius:3px; padding:5px 12px; font-size:12px;
  font-weight:600; font-family:inherit; cursor:pointer; }}
.ask:hover {{ filter:brightness(1.15); }}
.back {{ color:{t['link']}; font-size:12px; text-decoration:none; }}
.back:hover {{ text-decoration:underline; }}
.none {{ border:1px dashed {t['border2']}; border-radius:3px; padding:18px;
  color:{t['text2']}; font-size:13px; margin:8px 0; }}
.hint {{ font-size:10px; color:{t['text3']}; letter-spacing:0.04em;
  margin-top:10px; text-align:center; }}
</style>
<div class="eyerow"><span class="eb">Investigation storyboard</span>
  <span class="ebm">{_eyebrow_meta(len(incidents), *_span(incidents, days))}</span></div>
{ribbon}
<div class="story">
  <div class="stepper">
    <button class="nav" id="prev">‹ Prev</button>
    <div class="dots">{dots}</div>
    <button class="nav" id="next">Next ›</button>
  </div>
  {cases}
</div>
<div class="hint">← → move steps · ↑ ↓ switch incidents ·
  hover a chart to compare days · click a chart to open it · Anomaly → Investigation → Verdict → Action</div>
<script>
const IDS = {json.dumps(ids)};
const SEEDS = {json.dumps(seeds)};
let inc = {json.dumps(active)}, step = 0;
const $$ = (s) => document.querySelectorAll(s);
function render() {{
  $$('.iw').forEach(w => w.classList.toggle('active', w.dataset.inc === inc));
  $$('.case').forEach(c => c.classList.toggle('on', c.dataset.inc === inc));
  $$('.step').forEach(s => s.classList.toggle('on', +s.dataset.step === step));
  $$('.sd').forEach(d => {{
    d.classList.toggle('on', +d.dataset.step === step);
    d.classList.toggle('done', +d.dataset.step < step);
  }});
  document.getElementById('prev').disabled = step === 0;
  document.getElementById('next').disabled = step === 3;
}}
function setInc(id) {{
  if (IDS.indexOf(id) < 0) return;
  inc = id; step = 0; render();
}}
function setStep(k) {{ step = Math.max(0, Math.min(3, k)); render(); }}
$$('.iw').forEach(w => w.addEventListener('click',
  () => setInc(w.dataset.inc)));
$$('.sd').forEach(d => d.addEventListener('click',
  () => setStep(+d.dataset.step)));
document.getElementById('prev').onclick = () => setStep(step - 1);
document.getElementById('next').onclick = () => setStep(step + 1);
$$('.ask').forEach(b => b.addEventListener('click', () => {{
  sessionStorage.setItem('rcos-chat-seed', SEEDS[b.dataset.inc] || '');
  const old = b.textContent;
  b.textContent = 'Sent to chat dock ✓';
  setTimeout(() => {{ b.textContent = old; }}, 1600);
}}));
document.addEventListener('keydown', (e) => {{
  if (e.key === 'ArrowRight') {{ setStep(step + 1); e.preventDefault(); }}
  else if (e.key === 'ArrowLeft') {{ setStep(step - 1); e.preventDefault(); }}
  else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {{
    const k = IDS.indexOf(inc);
    if (k < 0 || !IDS.length) return;
    const d = e.key === 'ArrowDown' ? 1 : -1;
    setInc(IDS[(k + d + IDS.length) % IDS.length]);
    e.preventDefault();
  }}
}});
render();
// self-fit the component iframe to the rendered content (same pattern as the chat
// dock): the python-side height is a row-count GUESS and leaves a blank band —
// measure the real DOM instead, and track step/selection/theme changes live.
function fitFrame() {{
  try {{
    const h = document.documentElement.scrollHeight + 4;
    const fe = window.frameElement;
    if (!fe) return;
    fe.style.height = h + 'px';
    // the Streamlit element-container keeps the python-declared height — size it
    // too, or the grown iframe bleeds OVER the section that follows
    const pe = fe.parentElement;
    if (pe) {{ pe.style.height = h + 'px'; }}
  }} catch (e) {{}}
}}
try {{ new ResizeObserver(fitFrame).observe(document.body); }} catch (e) {{}}
window.addEventListener('load', fitFrame);
fitFrame();
</script>
"""
