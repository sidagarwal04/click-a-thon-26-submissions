"""RootCauseOS — fresh console, tab 1: Metrics.

New Relic-style metrics dashboard with SigNoz-style chrome:
- left side panel: nav + real integration shortcuts + dataset facts
- timeline picker (popover): range presets w/ shortcut chips, grain
  override pills, dataset-clock footer — ranges trail from
  max(event_time), because the dataset is historical
- billboard KPI row, then a grid of chart panels with a GA4-style
  synced crosshair (hover one chart → marker on all six; out-of-band
  values flagged red — local median±2·MAD until the team anomaly API lands)

Run:  streamlit run ui/app.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
import streamlit.components.v1 as components

from ui import nr_one as n
from ui import data as D
from ui import incidents as I

try:  # written in parallel against the frozen contract — may not exist yet
    from ui import storyboard
except ImportError:
    storyboard = None

# Theme lives in the URL (?theme=light), NOT session_state: the sidebar nav uses <a href> links
# which do a full page load and reset session_state — so a query param is the only thing that
# survives page changes AND refresh. Read it before inject so the whole page (CSS vars + inline
# SVG/chat colors that read n.T) renders in one pass. _TQ is appended to every in-app link below.
_THEME = st.query_params.get("theme", "light")   # light is the default (flash-free; see config.toml)
if _THEME not in ("light", "dark"):
    _THEME = "light"
_TQ = "&theme=dark" if _THEME == "dark" else ""   # only the non-default (dark) needs carrying
n.inject(page_title="AdPulse Dashboard", page_icon="◈", theme=_THEME)

# ---------------------------------------------------------------- router
# ?page=metrics (default) | ?page=incidents — driven by plain <a> links in
# the sidebar. The incidents branch below st.stop()s, so the metrics code
# keeps rendering at top level (no giant if-block).
# Route from the REAL request URL (st.context.url), not st.query_params:
# on <a>-navigation Streamlit can reattach the previous websocket session
# and restore ITS stale query params over the URL the user actually opened
# (observed: ?page=metrics silently flipping back to ?page=incidents, which
# also "hid" the timeline pill). context.url always reflects this page load.
from urllib.parse import parse_qs, urlparse

_ctx_url = getattr(st.context, "url", "") or ""
_qs = parse_qs(urlparse(_ctx_url).query)
page = (_qs.get("page") or [st.query_params.get("page", "metrics")])[0]
if page not in ("metrics", "incidents", "rca", "diagnosis", "lite"):
    page = "metrics"
incident_sel = ((_qs.get("incident") or
                 [st.query_params.get("incident") or ""])[0] or None)
# Diagnosis + Lite are merged into one "Root cause analysis" section; old
# deep links (?page=diagnosis&incident=… from storyboard/pin cards) keep
# working — the incident param auto-expands that card's read-out.
if page in ("diagnosis", "lite"):
    page = "rca"

# ---------------------------------------------------------------- metrics
# One panel per metric, NR-grid order. Incident windows are NOT hardcoded:
# they derive from the incident store (scan bundle → statics fallback), so
# a new dataset's scan re-shades the grid with zero UI changes.
_PANELS = [
    # key, panel title, value kind
    ("revenue",     "Revenue",     "usd"),
    ("requests",    "Requests",    "int"),
    ("fill_rate",   "Fill rate",   "rate"),
    ("ecpm",        "eCPM",        "usd"),
    ("ctr",         "CTR",         "rate"),
    ("render_rate", "Render rate", "rate"),
]


def _metric_windows() -> dict[str, tuple[str, str]]:
    """metric key -> merged (min start, max end) across incidents touching it."""
    spans: dict[str, tuple[str, str]] = {}
    for inc in I.incidents():
        w = inc.get("window", ["", ""])
        if not (w[0] and w[1]):
            continue
        for m in inc.get("panes") or []:
            cur = spans.get(m)
            spans[m] = ((min(cur[0], w[0]), max(cur[1], w[1])) if cur
                        else (w[0], w[1]))
    return spans


_SPANS = _metric_windows()
METRICS = [(k, t, kind, _SPANS.get(k)) for k, t, kind in _PANELS]

# ------------------------------------------------------------- time ranges
# SigNoz-style presets. All trail from max(event_time). auto = the grain
# that keeps bucket counts chart-sized for that span.
RANGES = [
    # key, label, chip, ClickHouse INTERVAL (None = full range), seconds, auto grain
    ("10m",  "Last 10 minutes", "10m", "10 MINUTE", 600,        "second"),
    ("30m",  "Last 30 minutes", "30m", "30 MINUTE", 1_800,      "minute"),
    ("1h",   "Last 1 hour",     "1h",  "1 HOUR",    3_600,      "minute"),
    ("6h",   "Last 6 hours",    "6h",  "6 HOUR",    21_600,     "minute"),
    ("12h",  "Last 12 hours",   "12h", "12 HOUR",   43_200,     "hour"),
    ("1d",   "Last 1 day",      "1d",  "1 DAY",     86_400,     "hour"),
    ("3d",   "Last 3 days",     "3d",  "3 DAY",     259_200,    "hour"),
    ("1w",   "Last 1 week",     "1w",  "7 DAY",     604_800,    "hour"),
    ("2w",   "Last 2 weeks",    "2w",  "14 DAY",    1_209_600,  "day"),
    ("full", "Full range",      "35d", None,        3_024_000,  "day"),
]
_RANGE = {r[0]: r for r in RANGES}
GRAIN_SECONDS = {"second": 1, "minute": 60, "hour": 3_600,
                 "day": 86_400, "month": 2_629_800}
MAX_BUCKETS = 2_200
GRAIN_PILLS = ["Auto", "Second", "Minute", "Hour", "Day", "Month"]


def _fmt(value: float, kind: str) -> str:
    """Level values. nr_one's "pct" is a signed delta — rates need x.x%."""
    if kind == "rate":
        return f"{value * 100:.2f}%" if value < 0.1 else f"{value * 100:.1f}%"
    return n.fmt_value(value, kind)


# Real-time correctness: every heavy cache is KEYED BY THE DATASET CLOCK
# (max(event_time), itself re-checked every 10 s — one cheap indexed query).
# New data ⇒ new clock ⇒ new cache key ⇒ fresh queries. Static data keeps
# hitting the cache. This is what makes the dashboard follow the data's own
# timeline instead of a wall-clock TTL.
@st.cache_data(ttl=10, show_spinner=False)
def _dataset_clock() -> str:
    return D.max_event_time()


def _display_clock(value: str) -> str:
    """Format the dataset clock without changing its timezone or meaning."""
    raw = str(value or "").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).strftime("%d %b %Y, %H:%M")
    except ValueError:
        return str(value or "").replace("T", " ")[:16]


@st.cache_data(ttl=600, show_spinner="querying ClickHouse…")
def _load(grain: str, window: str | None,
          clock: str = "") -> tuple[list[dict], dict]:
    return D.series(grain, window)


@st.cache_data(ttl=600, show_spinner=False)
def _row_count(clock: str = "") -> str:
    """Live row count of the active events table; honest em-dash offline."""
    try:
        res = D.query(f"SELECT count() AS c FROM {D.table()}",
                      comment="rcos:ui:rowcount")
        return f"{int(res['rows'][0]['c']):,}"
    except Exception:  # noqa: BLE001 — sidebar fact, never fatal
        return "—"


# ---------------------------------------------------------------- side panel
_LIBRECHAT = D._cfg("LIBRECHAT_URL", "http://localhost:3080")
_LANGFUSE = D._cfg("LANGFUSE_HOST", "https://cloud.langfuse.com")
_CLICKSTACK = D._cfg("CLICKSTACK_URL", "http://localhost:8081")  # 8081: Tailscale holds 8080

_SIDEBAR_CSS = """<style>
/* Align the sidebar top with the main content row: the main area starts near the top, but
   Streamlit gives the sidebar a big default top padding — pull it up so the brand lines up. */
/* Align the sidebar brand with the main content's top row. The large top gap is the
   stSidebarHeader region (the collapse-control strip), NOT the content padding — collapse it. */
[data-testid="stSidebarHeader"] { padding: 0.1rem 0.75rem 0 !important; min-height: 0 !important; height: auto !important; }
[data-testid="stSidebarUserContent"], [data-testid="stSidebarContent"] { padding-top: 0.2rem !important; }
.sb-brand { margin-top: 0 !important; padding-top: 0 !important; }
/* nr_one hides the whole Streamlit header — which also hid the sidebar
   re-expand arrow, making collapse one-way. Resurface just that control. */
[data-testid="stExpandSidebarButton"] {
  visibility: visible !important; position: fixed; top: 10px; left: 10px;
  z-index: 999; background: var(--nr-panel2);
  border: 1px solid var(--nr-border2); border-radius: 3px; }
[data-testid="stExpandSidebarButton"] button { color: var(--nr-accent) !important; }
/* timeline pill: placement comes from .st-key-hdrpick (header capsule row) */
[data-testid="stPopover"] { width: auto !important; }
[data-testid="stPopover"] > button, [data-testid="stPopover"] button {
  background: var(--nr-panel2) !important; color: var(--nr-text) !important;
  border: 1px solid var(--nr-border2) !important; }
/* chat dock: its component iframe is pinned bottom-right and sized from
   inside (window.frameElement); collapse its slot in the page flow */
.st-key-chatdock { height: 0; }
.st-key-chatdock iframe {
  position: fixed; bottom: 8px; right: 16px; z-index: 1001; border: 0;
  width: 132px; height: 64px; }
.sb-brand { display:flex; align-items:center; gap:8px; padding:6px 4px 14px;
  border-bottom:1px solid var(--nr-border); margin-bottom:10px; }
.sb-brand .logo { font-size:15px; font-weight:700; letter-spacing:0.10em;
  color:var(--nr-text); }
.sb-brand .logo span { color:var(--nr-accent); }
.sb-tag { font-size:9.5px; font-weight:700; letter-spacing:0.08em;
  color:var(--nr-bg); background:var(--nr-accent); border-radius:3px;
  padding:1px 6px; }
.sb-head { font-size:10px; font-weight:700; letter-spacing:0.12em;
  text-transform:uppercase; color:var(--nr-text3); margin:16px 4px 4px; }
a.sb-item, .sb-item { display:flex; align-items:center; gap:9px;
  padding:7px 10px; margin:1px 0; border-radius:3px; font-size:13px;
  color:var(--nr-text2) !important; text-decoration:none !important;
  border-left:2px solid transparent; }
a.sb-item:hover { background:var(--nr-panel2); color:var(--nr-text) !important; }
.sb-item.active { background:var(--nr-panel2); color:var(--nr-text) !important;
  border-left:2px solid var(--nr-accent); font-weight:600; }
.sb-item.dim { color:var(--nr-text3) !important; cursor:default; }
.sb-item .ic { width:14px; text-align:center; color:var(--nr-text3); }
.sb-item.active .ic { color:var(--nr-accent); }
.sb-soon { margin-left:auto; font-size:9px; font-weight:700;
  letter-spacing:0.08em; color:var(--nr-text3);
  border:1px solid var(--nr-border2); border-radius:3px; padding:0 5px; }
.sb-ext { margin-left:auto; font-size:10px; color:var(--nr-text3); }
.sb-facts { margin-top:18px; padding:10px 12px; border:1px solid var(--nr-border);
  border-radius:3px; font-size:11px; color:var(--nr-text3); line-height:1.7; }
.sb-facts b { color:var(--nr-text2); font-weight:600; }
.sb-facts .mono { font-family:ui-monospace,Menlo,monospace; }
.ux-status { display:grid; grid-template-columns:repeat(5,minmax(0,1fr));
  gap:8px; margin:8px 0 14px; }
.ux-status .box { background:var(--nr-panel); border:1px solid var(--nr-border);
  border-radius:3px; padding:9px 11px; min-width:0; }
.ux-status .k { font-size:9.5px; letter-spacing:0.08em; text-transform:uppercase;
  color:var(--nr-text3); white-space:nowrap; }
.ux-status .v { font-size:13px; color:var(--nr-text); font-weight:600;
  margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ux-status .v.ok { color:var(--nr-green); }
.ux-status .v.warn { color:var(--nr-yellow); }
.ux-status .v.crit { color:var(--nr-red); }
.chat-offline { position:fixed; bottom:16px; right:16px; z-index:1001;
  background:var(--nr-panel2); color:var(--nr-text3); border:1px solid var(--nr-border2);
  border-radius:3px; padding:9px 13px; font-size:12px; font-weight:600; }
@media (max-width: 900px) {
  [data-testid="stSidebar"] { display:none; }
  .block-container { min-width:0; padding-left:1rem; padding-right:1rem; }
  .ux-status { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .st-key-chatdock iframe { right:8px; }
}
@media (min-width: 901px) and (max-width: 1320px) {
  .block-container { max-width:1060px; }
}
</style>"""


def _short_incident_id(inc: dict, idx: int = 0) -> str:
    iid = str(inc.get("id") or "")
    if iid.startswith("INC-"):
        return iid
    return f"INC-{idx + 1}"


def _engine_state() -> tuple[str, str, str]:
    src_label = I.source_label()
    if "live RCA engine" in src_label:
        return "Engine live", src_label, "ok"
    if "scan-bundle file" in src_label:
        return "Bundle file", src_label, "warn"
    return "Static fallback", src_label, "crit"


def _status_strip(clock: str, rows_label: str) -> str:
    incs = I.incidents()
    ss = I.scan_summary() or {}
    engine, _source, tone = _engine_state()
    confirmed = [i for i in incs
                 if "NEEDS REVIEW" not in i.get("title", "")
                 and "LLM SUPPRESSED" not in i.get("title", "")]
    trace_count = sum(1 for inc in confirmed if inc.get("trace_url"))
    found = ss.get("incidents_found")
    if found is None:
        found = ss.get("real_incidents")
    if found is None:
        found = len(confirmed)
    trace = f"{trace_count}/{len(confirmed)} linked" if confirmed else "none"
    trace_tone = "ok" if trace_count else "warn"
    dot = {"ok": "var(--nr-green)", "warn": "var(--nr-yellow)", "crit": "var(--nr-red)"}[tone]
    pill = ("display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;"
            "border-radius:999px;padding:2px 10px;line-height:1.6;")
    return f"""
<div class="ux-status" style="display:flex;align-items:center;gap:8px;margin:-4px 0 10px;">
  <span style="{pill}color:var(--nr-red);background:var(--nr-red-a10);
        border:1px solid var(--nr-red-a35);">{n.esc(found)} incidents</span>
  <span style="{pill}color:var(--nr-green);background:var(--nr-green-a08);
        border:1px solid var(--nr-green-a30);">{n.esc(trace)} traces</span>
  <span title="{n.esc(engine)}" style="width:7px;height:7px;border-radius:50%;background:{dot};
        box-shadow:0 0 5px {dot};display:inline-block;margin-left:2px;"></span>
</div>
<style>
/* Pull the time-range popover (its own Streamlit block) up onto the pill row,
   right-aligned. The wrapper's panel box is stripped so only the pill shows. */
.st-key-hdrpick {{position:relative;margin:-35px 0 4px auto;width:fit-content;z-index:6;}}
.st-key-hdrpick [data-testid="stPopover"] {{background:transparent;border:none;}}
.st-key-hdrpick [data-testid="stPopover"] button {{
  border-radius:999px !important;padding:1px 12px;font-size:11px;font-weight:600;
  min-height:0;height:24px;line-height:1.4;color:var(--nr-text2) !important;
  background:var(--nr-panel) !important;border:1px solid var(--nr-border2) !important;}}
</style>
"""


def _verdict_label(verdict: str) -> str:
    return n.verdict_label(verdict)

def _refresh_all() -> str:
    """Manual refresh: drop every client cache and kick the engine. Milliseconds.

    This used to block. The engine's POST /refresh ran the whole scan inline (~200
    ClickHouse round-trips, ~20 s), so the button hung for its full 8 s client timeout,
    swallowed the timeout, then re-read a cache the recompute had not replaced yet —
    a long freeze that returned the SAME data. /refresh is now non-blocking: it starts
    the recompute and returns at once, and GET /scan keeps serving the last completed
    scan meanwhile, so the dashboard is never blank and never lies about being fresh.

    Returns the engine's status ("started" | "already_running" | "done" | "").
    """
    st.cache_data.clear()
    try:
        I._api_cache.update(t=0.0, doc=None)
    except Exception:  # noqa: BLE001
        pass
    try:
        import json as _json, urllib.request as _rq
        opener = _rq.build_opener(_rq.ProxyHandler({}))
        with opener.open(_rq.Request(
                D._cfg("RCOS_API", "http://127.0.0.1:8000").rstrip("/") + "/refresh",
                method="POST"), timeout=3) as r:      # 3 s is a dead-server guard now
            return str((_json.loads(r.read()) or {}).get("status", ""))
    except Exception:  # noqa: BLE001 — an old/absent engine must not break the button
        return ""


def _scan_age() -> tuple[bool, str]:
    """(a recompute is running, when the shown scan was computed). Cheap: ~1 ms."""
    try:
        import json as _json, urllib.request as _rq
        opener = _rq.build_opener(_rq.ProxyHandler({}))
        with opener.open(D._cfg("RCOS_API", "http://127.0.0.1:8000").rstrip("/")
                         + "/refresh_status", timeout=2) as r:
            s = _json.loads(r.read()) or {}
        return bool(s.get("recomputing")), str(s.get("computed_at") or "")[11:16]
    except Exception:  # noqa: BLE001 — older engines have no such endpoint
        return False, ""


with st.sidebar:
    clock = _dataset_clock()
    rows_label = _row_count(clock)
    st.markdown(_SIDEBAR_CSS + f"""
<div class="sb-brand"><span class="logo">Ad<span>Pulse</span></span>
  <span class="sb-tag">ENGINE</span></div>
<a class="sb-item{' active' if page == 'metrics' else ''}" href="?page=metrics{_TQ}" target="_self"><span class="ic">◈</span>Metrics</a>
<a class="sb-item{' active' if page == 'incidents' else ''}" href="?page=incidents{_TQ}" target="_self"><span class="ic">◭</span>Incidents</a>
<a class="sb-item{' active' if page == 'rca' else ''}" href="?page=rca{_TQ}" target="_self"><span class="ic">✦</span>Root cause analysis</a>
<div class="sb-head">Shortcuts</div>
<a class="sb-item" href="{n.esc(_LIBRECHAT)}" target="rcos-askai"><span class="ic">▣</span>Ask AI · LibreChat<span class="sb-ext">↗</span></a>
<a class="sb-item" href="{n.esc(_LANGFUSE)}" target="_blank"><span class="ic">☰</span>Traces · Langfuse<span class="sb-ext">↗</span></a>
<a class="sb-item" href="{n.esc(_CLICKSTACK)}" target="_blank"><span class="ic">▧</span>Traces · ClickStack<span class="sb-ext">↗</span></a>
<a class="sb-item" href="https://console.clickhouse.cloud" target="_blank"><span class="ic">▤</span>ClickHouse console<span class="sb-ext">↗</span></a>
<div class="sb-facts"><b>Data</b><br>
<span class="mono">{n.esc(D.table())}</span> · {n.esc(rows_label)} rows<br>
through <span class="mono">{n.esc(clock) or "—"}</span><br>
every chart = one live SQL query</div>
""", unsafe_allow_html=True)
    if st.button("↻ Refresh data", width="stretch",
                 help="Re-read the dataset clock and start a fresh engine scan. "
                      "The scan runs in the background (~20 s — it is ~200 ClickHouse "
                      "queries); the last completed scan stays on screen until the new "
                      "one lands, so nothing goes blank."):
        st.session_state["_refresh_kicked"] = _refresh_all() in ("started", "already_running")
        st.rerun()
    # Honest data age. Without this the button looks broken: it returns instantly (as it
    # should) but the numbers only change when the background scan lands ~20 s later.
    if st.session_state.get("_refresh_kicked"):
        _running, _at = _scan_age()
        if _running:
            st.caption(f"↻ new scan running… showing the scan from {_at or '—'}")
        else:
            st.session_state["_refresh_kicked"] = False
            st.caption(f"✓ scan updated{f' at {_at}' if _at else ''}")
    # Light/dark toggle → writes ?theme= so the choice survives page changes + refresh.
    _is_light = st.toggle("☀ Light mode", value=(_THEME == "light"),
                          help="Switch the dashboard between light and dark themes")
    if ("light" if _is_light else "dark") != _THEME:
        st.query_params["theme"] = "light" if _is_light else "dark"
        st.rerun()
    # Live mode: auto-refresh. Cheap by design — every tick re-checks the dataset clock
    # (one indexed max(event_time) query); the clock-keyed caches only re-query the charts
    # when NEW data has actually arrived, so a live append shows up within a tick.
    _live = st.toggle("🔴 Live", key="_live",
                      help="Auto-refresh every 5s: re-checks max(event_time) and re-queries "
                           "ClickHouse only if new data arrived")

# Live tick — a tiny fragment that re-runs the whole app on its interval when Live is on.
if st.session_state.get("_live"):
    @st.fragment(run_every=5)
    def _live_beat() -> None:
        st.rerun()
    _live_beat()

# ---------------------------------------------------------------- masthead
refreshed = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
_clock = _dataset_clock()
_rows_label = _row_count(_clock)
day_rows, day_prov = _load("day", None, _clock)
live = day_prov.get("source") == "clickhouse"
src = "Live ClickHouse" if live else "Fixture (ClickHouse unreachable)"
# Masthead title removed — the sidebar already brands it "AdPulse"; the status strip
# (incidents / traces / dataset) + time picker are enough up top.
st.markdown(_status_strip(_clock, _rows_label), unsafe_allow_html=True)

# Time-range picker — rendered as a capsule IN the header pill row (the CSS in
# _status_strip overlays this block onto that row). Lives above the page branch
# so its widget state survives page switches (no keep-dance needed).
if "range_sel" not in st.session_state:
    st.session_state["range_sel"] = st.session_state.get(
        "range_keep", "Full range")
if "grain_sel" not in st.session_state:
    st.session_state["grain_sel"] = st.session_state.get("grain_keep", "Auto")
range_label = st.session_state["range_sel"]
range_key = next((r[0] for r in RANGES if r[1] in range_label), "full")
_, label, chip, window, range_s, auto_grain = _RANGE[range_key]
grain_pick = (st.session_state.get("grain_sel") or "Auto").lower()
grain = auto_grain if grain_pick == "auto" else grain_pick
capped = False
if range_s / GRAIN_SECONDS[grain] > MAX_BUCKETS:
    grain, capped = auto_grain, True

with st.container(key="hdrpick"):
    with st.popover(f"🕒 {label} · {grain}"):
        pick_l, pick_r = st.columns([1.2, 1], gap="small")
        with pick_l:
            st.radio("Time range", [r[1] for r in RANGES], key="range_sel")
        with pick_r:
            st.markdown('<div class="sb-head">Grain</div>', unsafe_allow_html=True)
            st.pills("Grain", GRAIN_PILLS, key="grain_sel",
                     label_visibility="collapsed")
            if capped:
                st.caption(f"⚠ {grain_pick} grain over {label.lower()} exceeds "
                           f"{MAX_BUCKETS:,} buckets — using {grain} instead.")
            st.caption("Auto keeps the charts readable for the selected range.")
st.session_state["range_keep"] = range_label
st.session_state["grain_keep"] = st.session_state.get("grain_sel") or "Auto"

# ---------------------------------------------------------------- chat dock
# Native NR One chat, docked bottom-right. Talks to the SAME shim endpoint
# LibreChat uses (rootcauseos-rca → evidence-grounded chain), so it is one
# brain with two surfaces: this in-dashboard dock and full LibreChat (↗).
# Runs in a components.html iframe (needs JS); the iframe itself is pinned
# bottom-right by the .st-key-chatdock CSS and resizes itself via
# window.frameElement so the closed state is just the FAB.
_SHIM = D._cfg("SHIM_URL", "http://localhost:8601")
_PRESETS = ["Do we have an incident?", "Why did revenue drop?", "Who is affected?",
            "What should I do next?", "How confident are you?", "What did you rule out?"]


@st.cache_data(ttl=15, show_spinner=False)
def _shim_online(url: str) -> bool:
    try:
        import urllib.request as _rq
        opener = _rq.build_opener(_rq.ProxyHandler({}))
        with opener.open(url.rstrip("/") + "/v1/models", timeout=1.2) as resp:
            return 200 <= resp.status < 300
    except Exception:  # noqa: BLE001 - chat is additive, never page-fatal
        return False


def _chat_html() -> str:
    t = n.T
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
body {{ margin:0; background:transparent; font-family:{t['font']};
       overflow:hidden; }}
#fab {{ position:absolute; bottom:8px; right:8px; display:flex;
  align-items:center; gap:8px; background:{t['brand']}; color:#fff;
  border:1px solid {t['brand2']}; border-radius:3px; padding:10px 16px;
  font-size:13px; font-weight:600; cursor:pointer; user-select:none; }}
#fab:hover {{ background:{t['brand2']}; }}
#fab b {{ color:{t['accent']}; font-weight:600; }}
#panel {{ position:absolute; inset:8px 8px 64px 8px; display:none;
  flex-direction:column; background:{t['panel']};
  border:1px solid {t['border2']}; border-radius:6px;
  box-shadow:{t['shadow']}; overflow:hidden; }}
#head {{ display:flex; align-items:center; gap:8px; padding:10px 12px;
  font-size:12.5px; font-weight:600; color:{t['text']};
  border-bottom:1px solid {t['border']}; background:{t['panel2']}; }}
#head .dot {{ width:7px; height:7px; border-radius:50%; background:{t['green']}; }}
#head a {{ margin-left:auto; color:{t['text3']}; text-decoration:none; }}
#head span.x {{ cursor:pointer; color:{t['text3']}; padding:0 2px; }}
#head a:hover, #head span.x:hover {{ color:{t['accent']}; }}
#msgs {{ flex:1; overflow-y:auto; padding:12px; display:flex;
  flex-direction:column; gap:10px; }}
.m {{ max-width:88%; font-size:13px; line-height:1.6; color:{t['text']};
  border-radius:3px; padding:8px 11px; white-space:pre-wrap;
  overflow-wrap:anywhere; word-break:break-word; }}
.m a.lnk {{ color:{t['accent']}; text-decoration:underline;
  text-underline-offset:2px; overflow-wrap:anywhere; }}
.m a.lnk:hover {{ color:{t['brand2']}; }}
.m.u {{ align-self:flex-end; background:{t['panel2']};
  border:1px solid {t['border']}; }}
.m.a {{ align-self:flex-start; background:{n.rgba(t['accent'], 0.04)};
  border-left:2px solid {t['accent']}; }}
.m.err {{ border-left-color:{t['red']}; color:{t['red']}; }}
.ev {{ color:{t['accent']}; background:{n.rgba(t['accent'], 0.08)};
  border:1px solid {n.rgba(t['accent'], 0.30)}; border-radius:3px;
  padding:0 5px; font-size:11px; font-weight:600; }}
#hint {{ font-size:11px; letter-spacing:0.06em; text-transform:uppercase;
  color:{t['text3']}; margin:0 0 2px; line-height:1.5; flex:0 0 auto; }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:2px; flex:0 0 auto; }}
.chip {{ font-size:12px; color:{t['text2']}; background:{t['panel2']};
  border:1px solid {t['border2']}; border-radius:3px; padding:5px 10px;
  cursor:pointer; }}
.chip:hover {{ color:{t['accent']}; border-color:{t['accent']}; }}
.chip.demo {{ color:{t['red']}; border-color:{n.rgba(t['red'], 0.45)}; }}
.chip.demo:hover {{ border-color:{t['red']}; }}
#think.on::before {{ content:''; display:inline-block; width:11px; height:11px;
  border:2px solid {t['border2']}; border-top-color:{t['accent']}; border-radius:50%;
  animation:rot .8s linear infinite; margin-right:7px; vertical-align:-2px; }}
@keyframes rot {{ to {{ transform:rotate(360deg); }} }}
.m.rej {{ border-left-color:{t['red']};
  background:{n.rgba(t['red'], 0.05)}; }}
#think {{ display:none; align-self:flex-start; color:{t['text3']};
  font-size:12px; padding:2px 11px; }}
#think.on {{ display:block; }}
#inrow {{ display:flex; gap:8px; padding:10px 12px;
  border-top:1px solid {t['border']}; background:{t['panel']}; }}
#q {{ flex:1; background:{t['panel2']}; border:1px solid {t['border2']};
  border-radius:3px; color:{t['text']}; font-family:inherit; font-size:13px;
  padding:8px 10px; outline:none; }}
#q:focus {{ border-color:{t['brand']}; }}
#send {{ background:{t['brand']}; color:#fff; border:1px solid {t['brand2']};
  border-radius:3px; font-size:13px; font-weight:600; padding:8px 14px;
  cursor:pointer; }}
#send:hover {{ background:{t['brand2']}; }}
#foot {{ padding:5px 12px; font-size:10px; color:{t['text3']};
  border-top:1px solid {t['border']}; }}
</style>
<div id="panel">
  <div id="head"><span class="dot"></span>Ask AI · this incident
    <a href="{n.esc(_LIBRECHAT)}" target="rcos-askai" title="Open in LibreChat (single tab)">↗</a>
    <span class="x" id="reset" title="Clear conversation">↺</span>
    <span class="x" id="close" title="Close">✕</span></div>
  <div id="msgs"></div>
  <div id="inrow"><input id="q" placeholder="Ask about this incident…">
    <button id="send">Send</button></div>
  <div id="foot">model rootcauseos-rca · every number grounded to a ClickHouse
  query — fabricated figures are rejected</div>
</div>
<div id="fab"><b>▣</b>Ask AI</div>
<script>
const SHIM={json.dumps(_SHIM)}, PRESETS={json.dumps(_PRESETS)};
const FE=window.frameElement, msgs=document.getElementById('msgs'),
      q=document.getElementById('q');
let open=false, busy=false, hist=[];
// v2 key: drops any stale pre-reset history (e.g. old "endpoint unreachable" notices) once.
try {{ hist=JSON.parse(sessionStorage.getItem('rcos-chat-v2')||'[]'); }} catch(e) {{}}
function size() {{
  FE.style.width = open ? '460px' : '132px';
  FE.style.height = open ? 'min(680px, calc(100vh - 40px))' : '64px';
  document.getElementById('panel').style.display = open ? 'flex' : 'none';
}}
function evify(s) {{
  const e=document.createElement('div');
  e.innerText=s;
  return e.innerHTML
    .replace(/\\[([^\\]]+)\\]\\(((?:https?:)?\\/\\/[^)\\s]+)\\)/gi,
      (m,txt,url)=>'<a class="lnk" href="'+url+'" target="_blank" rel="noopener">'+txt+'</a>')
    .replace(/\\[(ev_[a-z0-9_,\\s]+)\\]/gi,(m,g)=>'<span class="ev">'+g+'</span>')
    .replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>');
}}
function chips() {{
  const w=document.createElement('div');
  w.innerHTML='<div id="hint">Ask about this incident</div>';
  const c=document.createElement('div'); c.className='chips';
  PRESETS.forEach(p=>{{ const b=document.createElement('span');
    b.className='chip'; b.innerText=p; b.onclick=()=>send(p); c.appendChild(b); }});
  const d=document.createElement('span');
  d.className='chip demo'; d.innerText='⛔ Demo: try to sneak in a fabricated number';
  d.title='Doctors an answer with an unsupported figure and shows the validator rejecting it';
  d.onclick=()=>send('__demo_fabrication__');
  c.appendChild(d);
  w.appendChild(c); msgs.appendChild(w);
}}
function add(role, text) {{
  const d=document.createElement('div');
  d.className='m '+role;
  if (role.indexOf('a')===0 && text.indexOf('⛔ FABRICATION REJECTED')===0)
    d.className+=' rej';
  d.innerHTML=evify(text);
  msgs.appendChild(d); msgs.scrollTop=msgs.scrollHeight;
}}
function render() {{
  msgs.innerHTML=''; chips();
  hist.forEach(m=>add(m.r, m.t));
  const th=document.createElement('div'); th.id='think';
  th.innerText='analyzing evidence…'; msgs.appendChild(th);
}}
async function send(text) {{
  text=(text||q.value).trim(); if(!text||busy) return;
  q.value=''; busy=true;
  hist.push({{r:'u', t: text==='__demo_fabrication__'
    ? 'Demo: try to sneak in a fabricated number' : text}}); render();
  document.getElementById('think').classList.add('on');
  msgs.scrollTop=msgs.scrollHeight;
  let inc=null; try {{ inc=sessionStorage.getItem('rcos-chat-incident'); }} catch(e) {{}}
  try {{
    const r=await fetch(SHIM+'/v1/chat/completions',{{method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{model:'rootcauseos-rca', rcos_incident: inc || undefined,
        messages:[{{role:'user',content:text}}]}})}});
    const d=await r.json();
    hist.push({{r:'a', t:(d.choices&&d.choices[0].message.content)||
      ('error: '+JSON.stringify(d).slice(0,160))}});
  }} catch(e) {{
    hist.push({{r:'a err', t:'RCA endpoint unreachable at '+SHIM+
      ' — start integrations/openai_shim.py'}});
  }}
  busy=false;
  try {{ sessionStorage.setItem('rcos-chat-v2', JSON.stringify(hist)); }} catch(e) {{}}
  render();
}}
document.getElementById('fab').onclick=()=>{{ open=true; size(); q.focus(); }};
document.getElementById('close').onclick=()=>{{ open=false; size(); }};
document.getElementById('reset').onclick=()=>{{
  hist=[]; try {{ sessionStorage.removeItem('rcos-chat-v2'); }} catch(e) {{}} render();
}};
document.getElementById('send').onclick=()=>send();
q.addEventListener('keydown',e=>{{ if(e.key==='Enter') send(); }});
// cross-iframe seed: the metrics pin card / storyboard "Ask AI" buttons
// drop a prompt here (same-origin srcdoc → sessionStorage is shared,
// same pattern as the 'rcos-chat' history key).
setInterval(()=>{{
  if(busy) return;
  let seed=null;
  try {{ seed=sessionStorage.getItem('rcos-chat-seed'); }} catch(e) {{}}
  if(!seed) return;
  try {{ sessionStorage.removeItem('rcos-chat-seed'); }} catch(e) {{}}
  open=true; size();
  send(seed);
}}, 1000);
render(); size();
</script>
"""


def _render_chat_dock() -> None:
    """Dock is position:fixed via the .st-key-chatdock CSS, so it renders
    identically from either page branch (metrics or incidents)."""
    if not _shim_online(_SHIM):
        st.markdown('<div class="chat-offline">Ask AI offline</div>',
                    unsafe_allow_html=True)
        return
    with st.container(key="chatdock"):
        components.html(_chat_html(), height=680, scrolling=False)


_RCA_CSS = """<style>
.rca-sum { margin: 14px 0 0; }
.rca-sum .card-head { flex-wrap:wrap; row-gap:4px; }
.rca-sum .rca-id { color:var(--nr-accent); font-size:11px; font-weight:700;
  font-family:ui-monospace,'SF Mono',Menlo,monospace; letter-spacing:0.08em; }
/* the segment, as a phrase — the one field that tells six cards apart */
.rca-sum .rca-seg { font-size:13px; font-weight:600; color:var(--nr-text2); }
/* Direction is spelled out AND signed. Both stay red on every card: red here
   means "this is the flagged move", not "this is bad" — eCPM rising and fill
   rate falling are equally incidents. */
.rca-sum .rca-move { margin-left:auto; display:inline-flex; align-items:baseline; gap:6px; }
.rca-sum .rca-dir { font-size:10px; font-weight:700; letter-spacing:0.06em;
  text-transform:uppercase; color:var(--nr-text3); }
.rca-sum .rca-delta { color:var(--nr-red); font-size:15px; font-weight:700; white-space:nowrap; }
.rca-sum .card-head .nr-chip { margin-left:6px; }
.rca-sum .rca-cause { font-size:12.5px; color:var(--nr-text2); margin-top:6px; line-height:1.5; }
/* names the metric next to its numbers, so "$2.93" is never "$2.93 of what?" */
.rca-sum .rca-gloss { color:var(--nr-text3); }
/* native expander re-themed on the design tokens (Streamlit chrome ignores the palette) */
[data-testid="stExpander"] { background:var(--nr-panel);
  border:1px solid var(--nr-border) !important; border-radius:3px; }
[data-testid="stExpander"] summary { color:var(--nr-text2) !important;
  font-size:12px; font-weight:600; }
[data-testid="stExpander"] summary:hover { color:var(--nr-accent) !important; }
[data-testid="stExpander"] summary svg { fill:var(--nr-text3); }
</style>"""


def _rca_page(selected: str | None) -> None:
    """Diagnosis + Lite merged: one card per incident.

    Each card answers four questions at a glance, in plain English: what moved,
    by how much and in which direction, where, and how sure the engine is. Every
    word of vocabulary comes from ui/explain.py — no metric name, segment phrase
    or unit is formatted here. The deep evidence lives in the expander below.
    """
    try:
        from ui import diagnosis as _diag
        from ui import explain as X
    except Exception as e:  # noqa: BLE001 — a judged surface must fail loud but styled
        st.markdown(n.empty_state("Diagnosis module unavailable", n.esc(str(e))),
                    unsafe_allow_html=True)
        return
    incs = [i for i in I.incidents()
            if "NEEDS REVIEW" not in i.get("title", "")
            and "LLM SUPPRESSED" not in i.get("title", "")]
    if not incs:
        st.markdown(n.empty_state("No incidents found",
                                  "the engine did not return any surviving anomalies"),
                    unsafe_allow_html=True)
        return
    st.markdown(n.page_header(
        "Root cause analysis",
        "one card per confirmed incident — what moved, the culprit, the trace; "
        "expand a card for the full evidence read-out"),
        unsafe_allow_html=True)
    st.markdown(_RCA_CSS, unsafe_allow_html=True)

    def _key(inc: dict) -> str:
        """Incident id under either contract name."""
        return str(inc.get("id") or inc.get("incident_id") or "")

    def _window(inc: dict) -> str:
        """`incident_window{start,end}`, or the older two-element list. A
        one-day incident prints one date, not `X → X`."""
        w = inc.get("incident_window")
        if isinstance(w, dict):
            a, b = str(w.get("start") or "")[:10], str(w.get("end") or "")[:10]
        else:
            wl = list(inc.get("window") or []) or ["", ""]
            a, b = str(wl[0])[:10], str(wl[-1])[:10]
        if a and b and a != b:
            return f"{a} → {b}"
        return a or b or "—"

    def _where(inc: dict) -> str:
        """The culprit segment as a phrase. Empty when the engine named none —
        that case is answered by the verdict, not by a blank."""
        c = inc.get("culprit")
        if isinstance(c, dict) and c.get("dimension"):
            dim, val = str(c.get("dimension") or ""), str(c.get("value") or "")
            extra = [f"{k}={v}" for k, v in (c.get("co_cut") or {}).items()
                     if f"{k}=" not in val]
            if extra:
                val = " × ".join([val, *extra])
            return X.segment_phrase(dim, val)
        # older card shape carried the culprit only as "<dimension> = <value>"
        legacy = inc.get("diagnosis")
        cause = legacy.get("cause", "") if isinstance(legacy, dict) else ""
        if " = " in cause and "global" not in cause:
            dim, val = cause.split(" = ", 1)
            return X.segment_phrase(dim.strip(), val.strip())
        return ""

    def _delta_pct(h: dict):
        """`delta_pct` is a number; the older shape kept a rendered string."""
        v = h.get("delta_pct")
        if v is not None:
            return v
        s = str(h.get("delta") or "").replace("−", "-").replace("%", "").strip()
        try:
            return float(s)
        except ValueError:
            return None

    ids = [_key(inc) for inc in incs]
    sel = selected if selected in ids else None
    for idx, inc in enumerate(incs):
        h = inc.get("headline") or {}
        key = _key(inc)
        sid = _short_incident_id(inc, idx)
        metric = str(inc.get("metric") or (inc.get("panes") or [""])[0] or "")
        unit = str(h.get("unit") or X.metric_unit(metric))
        verdict = str(inc.get("verdict") or "")
        window = _window(inc)

        # WHERE — a phrase, or the verdict when there is no segment to name
        where = _where(inc)
        if where:
            sub = f"{window} · {X.verdict_label(verdict)}" if verdict else window
        else:
            where = X.verdict_label(verdict) if verdict else ""
            tail = X.verdict_sentence(verdict)
            sub = f"{window} · {tail}" if tail else window
        seg_html = f'<span class="rca-seg">{n.esc(where)}</span>' if where else ""

        # HOW MUCH — the word carries the direction, the number carries the sign
        delta = _delta_pct(h)
        if delta is None:
            move = '<span class="rca-move"><span class="rca-delta">—</span></span>'
        else:
            move = ('<span class="rca-move" title="Flagged move — the anomaly is the '
                    'gap from expected, in either direction.">'
                    f'<span class="rca-dir">{n.esc(X.direction_word(delta))}</span>'
                    f'<span class="rca-delta">{n.esc(X.fmt_delta(delta))}</span></span>')

        # WHAT — the metric, named, sitting next to its own numbers
        observed = X.fmt_value(h.get("observed"), unit)
        base = h.get("baseline")
        expected = X.fmt_value(base if base is not None else h.get("expected"), unit)
        if observed != "—" and expected != "—":
            nums = f"Observed {observed} against an expected {expected}."
        elif observed != "—":
            nums = f"Observed {observed}. The engine returned no expected value."
        elif expected != "—":
            nums = f"Expected {expected}. The engine returned no observed value."
        else:
            nums = "The engine returned no observed or expected value."
        meaning = X.metric_meaning(metric)
        gloss = (f' <span class="rca-gloss">{n.esc(X.metric_name(metric))} = '
                 f'{n.esc(meaning)}</span>') if meaning else ""
        title = X.metric_name(metric) if metric else str(inc.get("title") or "Incident")

        trace = str(inc.get("trace_url") or "").strip()
        trace_html = (f'<a class="nr-chip nr-chip--ok" href="{n.esc(trace)}" '
                      'target="_blank">View trace</a>' if trace else
                      '<span class="nr-chip nr-chip--warn">Trace pending</span>')
        st.markdown(f"""
<div class="nr-card nr-card--crit rca-sum">
  <div class="card-head">
    <span class="rca-id">{n.esc(sid)}</span>
    <span class="card-title">{n.esc(title)}</span>
    {seg_html}
    {move}
    {trace_html}
  </div>
  <div class="card-sub">{n.esc(sub)}</div>
  <div class="rca-cause">{n.esc(nums)}{gloss}</div>
</div>""", unsafe_allow_html=True)
        with st.expander(f"Full evidence read-out · {sid}",
                         expanded=(key == sel)):
            try:
                b, full_depth, iid = _diag.pick(key)
                if b:
                    _diag.render(b, full=full_depth, incident_id=iid)
                else:
                    st.markdown(n.empty_state(
                        "No bundle for this incident",
                        "neither the golden §8 bundle nor the §8.1 scan bundle carries it"),
                        unsafe_allow_html=True)
            except Exception as e:  # noqa: BLE001 — one broken incident must not kill the page
                st.markdown(n.empty_state("Read-out unavailable", n.esc(str(e))),
                            unsafe_allow_html=True)


# ------------------------------------------------------------- incidents page
# ?page=incidents swaps billboards/section/grid/provenance for the incident
# storyboard (ui/storyboard.py, written in parallel against the frozen
# contract). Sidebar + masthead above and the chat dock render on BOTH pages.
if page == "rca":
    _rca_page(incident_sel)
    st.markdown(n.footnote([
        ("source", I.source_label()),
        ("overrides", "RCOS_API · RCOS_SCAN_BUNDLE · RCOS_BUNDLE (fixtures = offline fallback)"),
    ]), unsafe_allow_html=True)
    _render_chat_dock()
    st.stop()

if page == "incidents":
    if storyboard is None:
        st.markdown(n.empty_state("Incidents page assembling",
                                  "ui/storyboard.py not present yet"),
                    unsafe_allow_html=True)
    else:
        try:
            ribbon_rows = _load("day", None, _dataset_clock())[0]
        except Exception:
            ribbon_rows = []
        _sb_slot = st.empty()
        _sb_slot.markdown(n.skeleton("grid", 4, "fetching live scan…"), unsafe_allow_html=True)
        _invs = I.incidents()
        _sb_slot.empty()
        # adjudication trays (marked by the adjudicator in the card titles)
        _watch = [i for i in _invs if "NEEDS REVIEW" in i.get("title", "")]
        _ruled = [i for i in _invs if "LLM SUPPRESSED" in i.get("title", "")]
        _conf = [i for i in _invs if i not in _watch and i not in _ruled]
        # theme-aware tray chrome: everything uses var(--nr-*) so the light/dark toggle
        # re-colours it with the rest of the app (native st.metric/caption/info do NOT)
        def _tray_stat(label, value, accent=False, zero_note=""):
            # a bare 0 in a full-weight tile reads as a broken widget — mute it
            # and say why it's empty instead
            color = ("var(--nr-text3)" if not value else
                     "var(--nr-accent)" if accent else "var(--nr-text)")
            note = (f'<div style="font-size:11px;color:var(--nr-text3);">{zero_note}</div>'
                    if (not value and zero_note) else "")
            return (f'<div style="flex:1;background:var(--nr-panel);border:1px solid '
                    f'var(--nr-border);border-radius:3px;padding:12px 16px;">'
                    f'<div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;'
                    f'color:var(--nr-text3);">{label}</div>'
                    f'<div style="font-size:26px;font-weight:700;color:{color};line-height:1.3;">'
                    f'{value}</div>{note}</div>')
        def _tray_section(title, caption):
            return (f'<div style="margin:18px 0 2px;font-size:16px;font-weight:700;'
                    f'color:var(--nr-text);">{title}</div>'
                    f'<div style="font-size:12px;line-height:1.5;color:var(--nr-text3);'
                    f'max-width:860px;margin-bottom:10px;">{caption}</div>')
        def _tray_empty(msg):
            return (f'<div style="background:var(--nr-panel);border:1px solid var(--nr-border);'
                    f'border-left:2px solid var(--nr-border2);border-radius:3px;padding:10px 14px;'
                    f'font-size:12.5px;color:var(--nr-text2);margin-bottom:6px;">{msg}</div>')
        st.markdown('<div style="display:flex;gap:12px;margin-bottom:6px;">'
                    + _tray_stat("Confirmed incidents", len(_conf), accent=True)
                    + _tray_stat("Watchlist — needs review", len(_watch),
                                 zero_note="nothing needs review")
                    + _tray_stat("Ruled out by the LLM", len(_ruled),
                                 zero_note="engine rule-outs carry the receipts")
                    + "</div>", unsafe_allow_html=True)
        st.markdown(_tray_section(
            "Confirmed incidents",
            "Passed statistical detection AND survived adjudication: \u226510% deviation "
            "(deterministic — the LLM may not overrule) or LLM-ruled REAL with confidence "
            "\u22650.7 from computed evidence. Every number traces to a ClickHouse query_id."),
            unsafe_allow_html=True)
        # tile grid is 2-up; reserve space for the case file below the charts
        _h = lambda inv: max(760, 420 + 260 * ((len(inv) + 1) // 2))
        try:
            _data_through = _display_clock(_dataset_clock())
        except Exception:  # noqa: BLE001 — timestamp is additive, never fatal
            _data_through = ""
        components.html(storyboard.html(_conf, ribbon_rows, incident_sel,
                                        data_through=_data_through),
                        height=_h(_conf), scrolling=False)
        st.markdown(_tray_section(
            "Watchlist — needs review",
            "Detected in the 5-10% band but the adjudicator returned INCONCLUSIVE or "
            "confidence <0.7. Never counted as incidents or shown as headlines — parked "
            "here for a human decision. A shaky ruling can never silently delete a signal."),
            unsafe_allow_html=True)
        if _watch:
            components.html(storyboard.html(_watch, ribbon_rows, None,
                                            data_through=_data_through),
                            height=_h(_watch), scrolling=False)
        else:
            st.markdown(_tray_empty("Empty for this scan — every candidate was ruled decisively."),
                        unsafe_allow_html=True)
        st.markdown(_tray_section(
            "Ruled out by the LLM",
            "Sub-10% candidates ruled FALSE_POSITIVE (confidence \u22650.7), kept visible "
            "with the LLM's one-sentence, evidence-cited reason so the call is auditable."),
            unsafe_allow_html=True)
        if _ruled:
            components.html(storyboard.html(_ruled, ribbon_rows, None,
                                            data_through=_data_through),
                            height=_h(_ruled), scrolling=False)
        else:
            st.markdown(_tray_empty("Empty for this scan — the engine's deterministic "
                                    "rule-outs carry the receipts."), unsafe_allow_html=True)
    st.markdown(n.footnote([("source", I.source_label()),
                            ("mode", "live incident API")]),
                unsafe_allow_html=True)
    _render_chat_dock()
    st.stop()

# ---------------------------------------------------------------- billboards


# ---------------------------------------------------------- section header
# (time picker lives in the header capsule row, rendered at the masthead)
n.section_header("01", "Metrics",
                 f"{label.lower()} · {grain} grain · hover any chart for "
                 "the synced crosshair · band is median ± 2·MAD")

_skel_slot = st.empty()
_skel_slot.markdown(n.skeleton("grid", 6, "querying ClickHouse…"), unsafe_allow_html=True)
rows, prov = _load(grain, window, _clock)
_skel_slot.empty()
live = prov.get("source") == "clickhouse"

# billboards react to the SELECTED range: volumes sum over the window, rates average;
# full range keeps the last-day + week-over-week read
if rows:
    tiles = []
    for key, title, kind, _ in METRICS:
        vals = [float(r[key]) for r in rows]
        if key in ("revenue", "requests"):
            val, sub, tone = sum(vals), f"Σ · {label.lower()}", ""
        else:
            val, sub, tone = sum(vals) / len(vals), f"avg · {label.lower()}", ""
        tiles.append(n.kpi_tile(title, _fmt(val, kind), sub, tone))
    st.markdown(n.kpi_row(tiles), unsafe_allow_html=True)


# ---------------------------------------------------------------- chart grid
def _window_keys(inc: tuple[str, str] | None) -> tuple[str, str]:
    """Adapt a (start_date, end_date) incident window to this grain's label
    strings so svg_line_chart's inclusive string-compare shading still hits."""
    if not inc:
        return ("", "")
    start, end = inc
    if grain == "month":
        return (start[:7], end[:7])
    if grain != "day":
        return (start, end + " 23:59:59")
    return (start, end)


def _parse_cause_filters(cause: str) -> list[tuple[str, str]]:
    """Culprit ``cause`` string -> ``[(dim_col, value), ...]`` for a segment query.
    Handles the shapes _card() emits (API + file paths both build ``cause``):
      "os_version = Android 15"                         -> [(os_version, Android 15)]
      "ad_format×region = ad_format=native × region=EU" -> [(ad_format,native),(region,EU)]
      "no responsible segment — the drop is global"     -> []  (global, no filter)
    """
    if not cause or "responsible segment" in cause or "global" in cause:
        return []
    lhs, _, rhs = cause.partition(" = ")
    if not rhs:
        return []
    out: list[tuple[str, str]] = []
    for part in rhs.split("×"):
        part = part.strip()
        if "=" in part:                       # 2-D: each part is "dim=val"
            k, _, v = part.partition("=")
            out.append((k.strip(), v.strip()))
        elif part:                            # 1-D: dim is the left of "cause = value"
            out.append((lhs.strip(), part))
    return out


@st.cache_data(show_spinner=False, ttl=300)
def _cached_segment_series(metric: str, filters: tuple[tuple[str, str], ...]) -> dict:
    """Cached so Streamlit reruns (every hover) don't re-hit ClickHouse."""
    return D.segment_series(metric, [tuple(f) for f in filters])


def _trend_svg(days: list[str], seg: list, rest: list | None,
               win: list[str]) -> str:
    """Inline SVG sparkline for the pin card: the segment's daily series with the
    flagged window in red, a dashed baseline, and (when localized) a muted
    'everyone else' reference line. Rendered here in Python — testable, and it
    keeps the JS f-string free of brace-escaping."""
    npt = len(days)
    if npt < 2:
        return ""
    t = n.T
    W, H, PL, PR, PT, PB = 320, 104, 6, 6, 8, 6
    iw, ih = W - PL - PR, H - PT - PB
    vals = [v for v in seg if v is not None] + [v for v in (rest or []) if v is not None]
    if not vals:
        return ""
    vmax = max(vals) * 1.08 or 1.0
    def X(i: float) -> float: return PL + iw * (i / (npt - 1))
    def Y(v: float) -> float: return PT + ih * (1 - v / vmax)
    def inwin(i: int) -> bool: return win[0] <= days[i] <= win[1]

    def path(a: list) -> str:
        d, started = "", False
        for i, v in enumerate(a):
            if v is None:
                continue
            d += ("L" if started else "M") + f"{X(i):.1f},{Y(v):.1f}"
            started = True
        return d

    outs = sorted(v for i, v in enumerate(seg) if v is not None and not inwin(i))
    base = outs[len(outs) // 2] if outs else vmax
    wi = [i for i in range(npt) if inwin(i)]
    band = ""
    if wi:
        bx0, bx1 = X(max(0, wi[0] - 0.5)), X(min(npt - 1, wi[-1] + 0.5))
        band = (f'<rect x="{bx0:.1f}" y="{PT}" width="{bx1 - bx0:.1f}" '
                f'height="{ih}" fill="{n.rgba(t["red"], 0.12)}"/>')
    baseln = (f'<line x1="{PL}" y1="{Y(base):.1f}" x2="{W - PR}" y2="{Y(base):.1f}" '
              f'stroke="{t["text3"]}" stroke-width="1" stroke-dasharray="2 3" opacity="0.55"/>')
    restln = (f'<path d="{path(rest)}" fill="none" stroke="{t["text3"]}" '
              f'stroke-width="1.3" stroke-dasharray="3 3" opacity="0.85"/>' if rest else "")
    segln = f'<path d="{path(seg)}" fill="none" stroke="{t["accent"]}" stroke-width="1.7"/>'
    winln = ""
    if wi:
        lo, hi, d, started = max(0, wi[0] - 1), min(npt - 1, wi[-1] + 1), "", False
        for i in range(lo, hi + 1):
            if seg[i] is None:
                continue
            d += ("L" if started else "M") + f"{X(i):.1f},{Y(seg[i]):.1f}"
            started = True
        winln = f'<path d="{d}" fill="none" stroke="{t["red"]}" stroke-width="2.1"/>'
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" style="display:block;'
            f'height:auto;margin:8px 0 0">{band}{baseln}{restln}{segln}{winln}</svg>')


def _incident_trend_html(card: dict) -> str:
    """Best-effort trend block for one card; '' on any failure (no chart is fine)."""
    try:
        metric = (card.get("panes") or ["fill_rate"])[0]
        filters = _parse_cause_filters((card.get("diagnosis") or {}).get("cause", ""))
        s = _cached_segment_series(metric, tuple(filters))
        svg = _trend_svg(s["days"], s["seg"], s.get("rest"), card.get("window", ["", ""]))
        if not svg:
            return ""
        legend = "Affected segment" if filters else "All traffic"
        ref = "" if not s.get("rest") else (
            f' &nbsp;<span style="color:{n.T["text3"]}">┈ Other traffic</span>')
        return (f'<div style="font-size:9.5px;letter-spacing:0.06em;text-transform:uppercase;'
                f'color:{n.T["text3"]};margin-top:10px">35-day trend &nbsp;'
                f'<span style="color:{n.T["accent"]}">▬ {legend}</span>{ref}'
                f' &nbsp;<span style="color:{n.T["red"]}">▬ Incident window</span></div>{svg}')
    except Exception:  # noqa: BLE001 — a missing chart must never break the card
        return ""


def _incidents_with_trend() -> list[dict]:
    """The pin-card incidents, each enriched with a ``trend_html`` sparkline."""
    try:
        data_through = _display_clock(_dataset_clock())
    except Exception:  # noqa: BLE001 — labels are additive, never fatal
        data_through = ""
    cards = []
    for raw in I.incidents():
        c = dict(raw)
        c.update({f"_display_{k}": v for k, v in
                  I.display_snapshot(c, data_through).items()})
        c["trend_html"] = _incident_trend_html(c)
        cards.append(c)
    return cards


def _grid_html(rows: list[dict]) -> str:
    """The six chart panels + synced-crosshair JS as one self-contained HTML
    document (rendered via components.html — st.markdown strips <script>).
    Geometry constants mirror nr_one.svg_line_chart exactly."""
    labels = [r["d"] for r in rows]
    panes, data = [], {"labels": labels, "series": {}}
    for key, title, kind, inc in METRICS:
        series = [{"label": r["d"], "value": r[key]} for r in rows]
        start, end = _window_keys(inc)
        chart = n.svg_line_chart(series, breached=bool(inc),
                                 start=start, end=end)
        vals = [float(r[key]) for r in rows]
        lo, hi = min(vals), max(vals)
        span = max(hi - lo, 1e-9)
        lo, hi = lo - span * 0.06, hi + span * 0.06   # svg_line_chart's pad
        s = sorted(vals)
        m = len(s)
        med = s[m // 2] if m % 2 else (s[m // 2 - 1] + s[m // 2]) / 2.0
        mad = sorted(abs(v - med) for v in s)[m // 2]
        band = max(mad * 1.4826 * 2.0, 1e-9)
        data["series"][key] = {"title": title, "kind": kind, "vals": vals,
                               "lo": lo, "hi": hi, "med": med, "band": band}
        sub = n.esc(label.lower() if not inc
                    else f"{label.lower()} · incident {inc[0]} → {inc[1]}")
        panes.append(
            f'<div class="pane" data-key="{key}">'
            f'<div class="t">{n.esc(title)}</div><div class="s">{sub}</div>'
            f'<div class="cw">{chart}'
            f'<div class="xline"></div><div class="dot"></div></div></div>'
        )
    t = n.T
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
body {{ margin:0; background:{t['bg']}; font-family:{t['font']}; }}
.grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
.pane {{ background:{t['panel']}; border:1px solid {t['border']};
        border-radius:3px; padding:12px 14px; }}
.pane .t {{ font-size:14px; font-weight:600; color:{t['text']}; }}
.pane .s {{ font-size:11px; color:{t['text3']}; margin:2px 0 8px; }}
.cw {{ position:relative; }}
.cw svg {{ display:block; width:100%; height:auto; }}
.xline {{ position:absolute; top:0; width:1px; height:100%; display:none;
         background:repeating-linear-gradient(to bottom, {t['accent']} 0 4px,
         transparent 4px 8px); opacity:.7; pointer-events:none; }}
.dot {{ position:absolute; width:7px; height:7px; border-radius:50%; display:none;
       background:{t['accent']}; border:1px solid {t['bg']}; pointer-events:none;
       transform:translate(-3.5px,-3.5px); }}
.dot.anom {{ background:{t['red']}; }}
#tip {{ position:fixed; display:none; z-index:10; pointer-events:none;
       background:{t['panel2']}; border:1px solid {t['border2']}; border-radius:3px;
       padding:8px 10px; font-size:11.5px; color:{t['text']}; min-width:210px; }}
#tip b {{ display:block; margin-bottom:5px; color:{t['accent']};
         font-family:ui-monospace,Menlo,monospace; font-size:11px; }}
#tip .row {{ display:flex; justify-content:space-between; gap:16px; }}
#tip .row span:last-child {{ font-variant-numeric:tabular-nums; }}
#tip .row.anom {{ color:{t['red']}; font-weight:600; }}
#tip .inc {{ border-bottom:1px solid {t['border2']}; margin-bottom:6px;
  padding-bottom:6px; }}
#tip .inc .iid {{ color:{t['red']}; font-weight:700; font-size:11px;
  letter-spacing:0.05em; }}
#tip .inc .it {{ color:{t['text']}; font-weight:600; font-size:12.5px; margin:1px 0; }}
#tip .inc .ic {{ color:{t['text2']}; font-size:11px; }}
#tip .inc .ip {{ color:{t['accent']}; font-size:10.5px; margin-top:4px; }}
#pin {{ position:fixed; top:10px; right:10px; bottom:10px; width:390px;
  display:none; flex-direction:column; z-index:20; overflow:hidden;
  background:{t['panel']}; border:1px solid {t['border2']}; border-radius:6px;
  box-shadow:{t['shadow']}; }}
#pin.on {{ display:flex; }}
#pin .ph {{ display:flex; align-items:center; gap:8px; padding:10px 12px;
  background:{t['panel2']}; border-bottom:1px solid {t['border']}; }}
#pin .sev {{ color:{t['red']}; background:{n.rgba(t['red'], 0.10)};
  border:1px solid {n.rgba(t['red'], 0.35)}; border-radius:3px; padding:1px 7px;
  font-size:10.5px; font-weight:700; letter-spacing:0.05em; }}
#pin .pt {{ color:{t['text']}; font-weight:600; font-size:13px; }}
#pin .px {{ margin-left:auto; cursor:pointer; color:{t['text3']}; font-size:13px; }}
#pin .px:hover {{ color:{t['accent']}; }}
#pin .cta {{ display:flex; gap:8px; margin:0 0 2px; }}
#pin .pbtn {{ display:inline-block; background:{t['brand']}; color:#fff;
  border:1px solid {t['brand2']}; border-radius:3px; padding:7px 13px;
  font-size:12.5px; font-weight:600; text-decoration:none; cursor:pointer; }}
#pin .pbtn:hover {{ background:{t['brand2']}; }}
#pin .pbtn.ghost {{ background:transparent; color:{t['text2']};
  border-color:{t['border2']}; }}
#pin .pbtn.ghost:hover {{ color:{t['accent']}; border-color:{t['accent']};
  background:transparent; }}
#pin details {{ margin:12px 0 0; }}
#pin summary {{ font-size:10px; font-weight:700; letter-spacing:0.12em;
  text-transform:uppercase; color:{t['text3']}; cursor:pointer; }}
#pin details ul {{ margin-top:5px; }}
#pin .pb {{ flex:1; overflow-y:auto; padding:12px 14px; }}
#pin .sec {{ font-size:10px; font-weight:700; letter-spacing:0.12em;
  text-transform:uppercase; color:{t['text3']}; margin:12px 0 5px; }}
#pin .sec:first-child {{ margin-top:0; }}
#pin .big {{ font-size:21px; font-weight:600; color:{t['red']};
  font-variant-numeric:tabular-nums; }}
#pin .hl {{ font-size:11.5px; color:{t['text2']}; margin-top:2px; }}
#pin .cause {{ display:inline-block; color:{t['accent']};
  background:{n.rgba(t['accent'], 0.08)}; border:1px solid {n.rgba(t['accent'], 0.30)};
  border-radius:3px; padding:2px 8px; font-size:12px; font-weight:600; }}
#pin p {{ font-size:12.5px; line-height:1.6; color:{t['text']}; margin:6px 0; }}
#pin .kv {{ display:flex; gap:8px; font-size:11.5px; margin:3px 0;
  color:{t['text2']}; }}
#pin .kv b {{ color:{t['text3']}; font-weight:600; min-width:86px;
  text-transform:uppercase; font-size:10px; letter-spacing:0.06em;
  padding-top:1px; }}
#pin ul {{ margin:2px 0 0 16px; padding:0; }}
#pin li {{ font-size:12px; color:{t['text2']}; line-height:1.55; margin:3px 0; }}
#pin .act {{ display:flex; gap:8px; align-items:baseline; margin:5px 0;
  font-size:12.5px; color:{t['text']}; }}
#pin .urg {{ font-size:9.5px; font-weight:700; letter-spacing:0.06em;
  border-radius:3px; padding:1px 6px; text-transform:uppercase; }}
#pin .urg.now {{ color:{t['red']}; border:1px solid {n.rgba(t['red'], 0.45)}; }}
#pin .urg.today {{ color:{t['yellow']}; border:1px solid {n.rgba(t['yellow'], 0.45)}; }}
#pin .pf {{ padding:6px 12px; border-top:1px solid {t['border']};
  font-size:10px; color:{t['text3']}; }}
</style>
<div class="grid">{''.join(panes)}</div><div id="tip"></div>
<div id="pin"><div class="ph"><span class="sev">INCIDENT</span>
  <span class="pt"></span><span class="px" title="Close">✕</span></div>
  <div class="pb"></div>
  <div class="pf">diagnosis from the incident store (live engine when available) —
  attaches to the incident API when provided</div></div>
<script>
const D = {json.dumps(data)};
const INC = {json.dumps(_incidents_with_trend())};
function vlabel(v) {{ return v === 'GLOBAL_UNLOCALIZED'
  ? 'Global incident — no segment culprit'
  : (v && v.indexOf('LOCALIZED') === 0 ? 'Localized root cause' : (v || 'Unknown')); }}
const W=720,H=220,PL=52,PR=18,PT=18,PB=30,IW=W-PL-PR,IH=H-PT-PB;
const NP=D.labels.length;
function fmt(v,k){{
  if(k==='usd') return '$'+v.toFixed(2);
  if(k==='int') return Math.round(v).toLocaleString();
  return (v*100).toFixed(2)+'%';
}}
function esc(s){{ const d=document.createElement('div'); d.innerText=s||'';
  return d.innerHTML; }}
function incAt(pane,label){{
  const day=label.slice(0,10);
  const hits=INC.filter(x=>x.panes.includes(pane)&&x.window[0]<=day&&day<=x.window[1]);
  hits.sort((a,b)=>(Date.parse(a.window[1])-Date.parse(a.window[0]))-
                   (Date.parse(b.window[1])-Date.parse(b.window[0])));
  return hits[0]||null;  // narrowest matching window wins (most specific)
}}
let hovered=null;  // {{pane, i}} for click-to-pin
function openPin(inc){{
  const pin=document.getElementById('pin');
  pin.querySelector('.pt').innerText=inc.id+' — '+inc.title;
  pin.querySelector('.pb').innerHTML=
    '<div class="cta"><a class="pbtn" id="openinv" href="#">Open investigation →</a>'+
    '<span class="pbtn ghost" id="askai" title="Seed the chat dock">Ask AI</span></div>'+
    '<div class="sec">What happened</div>'+
    '<div class="big">'+esc(inc.headline.delta)+'</div>'+
    '<div class="hl">'+esc((inc._display_metric || inc.headline.label || 'Incident')+
      (inc._display_where ? ' · '+inc._display_where : ''))+'</div>'+
    '<div class="hl">Observed '+esc(inc.headline.observed)+' vs expected '+
      esc(inc.headline.expected)+'</div>'+
    '<div class="hl">Incident window: '+esc((inc.window || []).join(' → '))+'</div>'+
    (inc._display_data_through ? '<div class="hl">Data through: '+
      esc(inc._display_data_through)+'</div>' : '')+
    (inc.trend_html||'')+
    '<div class="sec">Diagnosis · '+esc(vlabel(inc.verdict))+'</div>'+
    '<span class="cause" title="'+esc(inc._display_dimension || '')+'">'+
      esc(inc._display_where || inc.diagnosis.cause)+'</span>'+
    '<p>'+esc(inc.diagnosis.mechanism)+'</p>'+
    '<div class="kv"><b>Contribution</b><span>'+esc(inc.diagnosis.contribution)+'</span></div>'+
    '<div class="kv"><b>Uniformity</b><span>'+esc(inc.diagnosis.uniformity)+'</span></div>'+
    '<div class="kv"><b>Confidence</b><span>'+esc(inc.diagnosis.confidence)+'</span></div>'+
    '<details><summary>Ruled out ('+inc.ruled_out.length+' checks)</summary><ul>'+
      inc.ruled_out.map(r=>'<li>'+esc(r)+'</li>').join('')+'</ul></details>'+
    '<div class="sec">Do next</div>'+
      inc.actions.map(a=>'<div class="act"><span class="urg '+esc(a.urgency)+'">'+
        esc(a.urgency)+'</span><span>'+esc(a.text)+'</span></div>').join('');
  pin.querySelector('#askai').onclick=()=>{{
    try {{
      sessionStorage.setItem('rcos-chat-incident', inc.id);   // so the dock asks about THIS incident
      sessionStorage.setItem('rcos-chat-seed',
        'Explain '+inc.id+' — '+inc.title+' — and what I should do');
    }} catch(e) {{}}
  }};
  pin.querySelector('#openinv').onclick=(e)=>{{
    e.preventDefault();
    // a relative href from inside this srcdoc component iframe resolves against the component
    // host (404), so navigate the PARENT app window explicitly — carrying the current theme.
    // sandbox has no allow-top-navigation: parent.location and _top are both blocked.
    // Build an ABSOLUTE url from the parent (readable via allow-same-origin) and open a
    // tab (allow-popups-to-escape-sandbox) — same pattern as the case-file deep-dive.
    var q='?page=diagnosis&incident='+encodeURIComponent(inc.id)+'{_TQ}';
    var base; try {{ base=parent.location.origin+parent.location.pathname; }}
    catch(err) {{ base=''; }}
    window.open(base+q, '_blank');
  }};
  pin.classList.add('on');
}}
document.querySelector('#pin .px').onclick=
  ()=>document.getElementById('pin').classList.remove('on');
function show(i,e){{
  document.querySelectorAll('.pane').forEach(p=>{{
    const s=D.series[p.dataset.key], cw=p.querySelector('.cw');
    const svg=cw.querySelector('svg'), r=svg.getBoundingClientRect();
    const left=(PL+i*IW/Math.max(NP-1,1))/W*r.width;
    const line=cw.querySelector('.xline'), dot=cw.querySelector('.dot');
    line.style.left=left+'px'; line.style.display='block';
    const v=s.vals[i], yf=(PT+(s.hi-v)/Math.max(s.hi-s.lo,1e-9)*IH)/H;
    dot.style.left=left+'px'; dot.style.top=(yf*r.height)+'px';
    dot.style.display='block';
    dot.classList.toggle('anom', Math.abs(v-s.med)>s.band);
  }});
  const tip=document.getElementById('tip');
  const inc=hovered?incAt(hovered.pane,D.labels[i]):null;
  const incHtml=inc?('<div class="inc"><span class="iid">'+esc(inc.id)+' · '+
    esc(inc.headline.delta)+'</span><div class="it">'+esc(inc.title)+
    '</div><div class="ic">'+esc(inc.diagnosis.cause)+'</div>'+
    '<div class="ip">click the chart to pin the full diagnosis →</div></div>'):'';
  tip.innerHTML=incHtml+'<b>'+D.labels[i]+'</b>'+Object.values(D.series).map(s=>{{
    const anom=Math.abs(s.vals[i]-s.med)>s.band;
    return '<div class="row'+(anom?' anom':'')+'"><span>'+s.title+
           (anom?' ⚠':'')+'</span><span>'+fmt(s.vals[i],s.kind)+'</span></div>';
  }}).join('');
  tip.style.display='block';
  let x=e.clientX+14;
  if(x+230>document.documentElement.clientWidth) x=e.clientX-244;
  tip.style.left=x+'px';
  tip.style.top=Math.max(4,Math.min(e.clientY-30,document.documentElement.clientHeight-170))+'px';
}}
function hide(){{
  document.querySelectorAll('.xline,.dot').forEach(el=>el.style.display='none');
  document.getElementById('tip').style.display='none';
}}
document.querySelectorAll('.pane').forEach(p=>{{
  p.addEventListener('mousemove',e=>{{
    const svg=p.querySelector('.cw svg'), r=svg.getBoundingClientRect();
    const fx=(e.clientX-r.left)/r.width*W;
    const i=Math.max(0,Math.min(NP-1,Math.round((fx-PL)/IW*(NP-1))));
    hovered={{pane:p.dataset.key, i:i}};
    show(i,e);
  }});
  p.addEventListener('mouseleave',()=>{{ hovered=null; hide(); }});
  p.addEventListener('click',()=>{{
    if(!hovered) return;
    const inc=incAt(hovered.pane, D.labels[hovered.i]);
    if(inc) openPin(inc);
  }});
}});
</script>
"""


if len(rows) < 2:
    st.markdown(n.empty_state("Not enough data at this grain",
                              "fewer than 2 buckets returned"),
                unsafe_allow_html=True)
else:
    components.html(_grid_html(rows), height=470, scrolling=False)

# ---------------------------------------------------------------- chat dock
_render_chat_dock()

# ---------------------------------------------------------------- provenance
foot = [("source", D.table() if live else "fixture"),
        ("range", label.lower()), ("grain", grain)]
if live:
    foot += [
        ("rows read", f"{prov.get('read_rows', 0):,}"),
        ("query time", f"{prov.get('elapsed_ms', 0):.0f} ms"),
        ("query id", (lambda q: q[:40] + ("…" if len(q) > 40 else ""))(
            str(prov.get("query_id", "")))),
    ]
st.markdown(n.footnote(foot), unsafe_allow_html=True)
