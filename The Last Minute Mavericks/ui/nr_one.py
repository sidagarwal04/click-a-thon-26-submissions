# Source: /Users/namangoyal/clickathon-inmobi-2026/design-system/nr_one.py
# authored by teammate — vendored until design-system/ lands on main
# Vendored: 2026-08-01
"""nr_one.py — the New Relic One design system as a single drop-in module.

Zero dependencies beyond Streamlit. Copy this ONE file into any Streamlit
project, call ``nr_one.inject()`` once at the top of your app, and every
component below returns ready HTML for ``st.markdown(..., unsafe_allow_html=True)``.

Built from the RootCauseOS dashboard (clickathon-inmobi-2026/rcosui).
Real NR One Core tokens: brand teal #007e8a/#005054, accent #40edcd,
blue #0079bf, neutrals #000e0e -> #e3e4e4, red #ff667a, yellow #fed966,
green #68f261. Inter typography, 14px base, 3px radii, tight line-heights.
"""

from __future__ import annotations

import html as _html
import math as _math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import streamlit as st

# The RCA vocabulary module (metric names + units). Optional on purpose: nr_one stays a
# drop-in single file, so a missing ui.explain degrades to plain formatting, never a crash.
try:                                          # pragma: no cover - import shape only
    from ui import explain as _X              # type: ignore
except Exception:                             # pragma: no cover
    _X = None                                 # type: ignore

# ---------------------------------------------------------------------------
# 1. TOKENS
# ---------------------------------------------------------------------------

T_DARK: Dict[str, str] = {
    # typography
    "font": "'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif",
    # surfaces
    "bg": "#000e0e",        # app background (near-black navy)
    "panel": "#0d1a1a",     # card background
    "panel2": "#122222",    # raised surface (popovers, hover)
    "border": "#1c2e2e",    # hairline border
    "border2": "#2a4040",   # stronger border (gridlines, focus)
    # brand
    "brand": "#007e8a",     # primary teal
    "brand2": "#005054",    # deep teal (hover, borders)
    "accent": "#40edcd",    # bright cyan accent
    "blue": "#0079bf",      # info blue
    "link": "#40edcd",      # hyperlinks
    # text
    "text": "#e3e4e4",      # primary text
    "text2": "#93a2a2",     # secondary text
    "text3": "#5b6d6d",     # tertiary / captions
    # semantic
    "red": "#ff667a",
    "yellow": "#fed966",
    "green": "#68f261",
    "ok": "#68f261",
    "crit": "#ff667a",
    "warn": "#fed966",
    "info": "#0079bf",
    # elevation for fixed overlays (pin card, chat dock)
    "shadow": "0 12px 40px rgba(0,0,0,0.55)",
}

# Light theme — a considered NR One light identity, not an inversion: off-white teal-biased
# surfaces, near-black ink, and a DEEPER teal accent (the dark theme's bright #40edcd cyan is
# near-invisible on white). Semantic colors darkened for legibility on light grounds.
T_LIGHT: Dict[str, str] = {
    "font": T_DARK["font"],
    "bg": "#f5f8f8",        # off-white with a faint teal bias (not pure white)
    "panel": "#ffffff",     # cards
    "panel2": "#eaf1f1",    # raised surface (popovers, hover)
    "border": "#dbe5e5",    # hairline border
    "border2": "#c1d1d1",   # stronger border
    "brand": "#007e8a",     # primary teal (works on both grounds)
    "brand2": "#005054",
    "accent": "#00707c",    # deep teal accent — readable on white
    "blue": "#0068b3",
    "link": "#007e8a",
    "text": "#0a1919",      # near-black ink
    "text2": "#3d5353",     # secondary
    "text3": "#6a7c7c",     # tertiary / captions
    "red": "#d33a4e",
    "yellow": "#a86a00",    # dark amber (readable on white)
    "green": "#1f9d4d",
    "ok": "#1f9d4d",
    "crit": "#d33a4e",
    "warn": "#a86a00",
    "info": "#0068b3",
    "shadow": "0 6px 24px rgba(10,25,25,0.16)",
}

# Active palette (mutated in place by set_theme so inline-SVG/chat colors reading T[...] and the
# CSS :root vars both follow the current theme). Defaults to dark.
T: Dict[str, str] = dict(T_DARK)


def set_theme(mode: str) -> None:
    """Switch the active palette to 'light' or 'dark' (anything but 'light' = dark). Call BEFORE
    inject() and before rendering any component, so both the CSS vars and inline T[...] reads match."""
    T.clear()
    T.update(T_LIGHT if mode == "light" else T_DARK)

def rgba(color: str, alpha: float) -> str:
    """A translucent tint computed from a palette hex — NEVER hand-write an
    rgba literal: dark-theme tints under light-theme text was the app's most
    repeated theming bug. Use rgba(T['red'], .10), not rgba(255,102,122,.10)."""
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def verdict_label(verdict: str) -> str:
    """Humanize engine verdict enums for judged surfaces."""
    if verdict == "GLOBAL_UNLOCALIZED":
        return "Global incident — no segment culprit"
    if (verdict or "").startswith("LOCALIZED"):
        return "Localized root cause"
    return verdict or "Unknown"


# spacing scale (px) — use for margins/paddings in your own markup
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}
# radii
RADIUS = {"sm": 2, "md": 3, "lg": 6}

# status glyphs for chips
GLYPHS: Dict[str, str] = {"ok": "▲", "crit": "△", "warn": "●", "info": "◇"}

def _root_vars() -> str:
    """The :root CSS custom properties for the ACTIVE palette (regenerated each inject so the
    light/dark toggle actually re-colours everything that uses var(--nr-*))."""
    keys = ["font", "bg", "panel", "panel2", "border", "border2", "brand", "brand2",
            "accent", "blue", "link", "text", "text2", "text3", "red", "yellow", "green",
            "shadow"]
    body = "\n".join(f"  --nr-{k}: {T[k]};" for k in keys)
    # theme-computed tints (--nr-red-a10 = active red at 10% …) so no CSS ever
    # hand-writes an rgba literal that only matches ONE theme's palette
    tints = "\n".join(
        f"  --nr-{k}-a{int(a * 100):02d}: {rgba(T[k], a)};"
        for k in ("red", "green", "yellow", "accent", "blue", "text2")
        for a in (0.04, 0.08, 0.10, 0.16, 0.30, 0.35, 0.40))
    return ":root {\n" + body + "\n" + tints + "\n}"


_CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {{
  font-family: var(--nr-font);
  font-size: 14px;
  color: var(--nr-text);
  background-color: var(--nr-bg);
}}

.stApp {{ background-color: var(--nr-bg); }}

/* native Streamlit widgets: config `base` is static, so re-theme them off the active palette
   here (buttons, widget labels, toggle) — otherwise they'd stay dark on the light ground. */
.stButton button, [data-testid="stBaseButton-secondary"] {{
  background: var(--nr-panel) !important; color: var(--nr-text) !important;
  border: 1px solid var(--nr-border2) !important; }}
.stButton button:hover, [data-testid="stBaseButton-secondary"]:hover {{
  border-color: var(--nr-accent) !important; color: var(--nr-accent) !important; }}
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * {{ color: var(--nr-text2) !important; }}
[data-baseweb="popover"] [data-testid="stMarkdownContainer"], .stPopover * {{ color: var(--nr-text); }}
/* the pop-out PANEL (time-picker dropdown) is portal-rendered and follows the static light
   config → force it to the ACTIVE theme so it's dark in dark mode, not a white sheet. */
[data-testid="stPopoverBody"], [data-baseweb="popover"] [data-testid="stPopoverBody"] {{
  background: var(--nr-panel) !important; color: var(--nr-text) !important;
  border: 1px solid var(--nr-border2) !important;
  max-width: 640px !important; }}   /* compact: Time-range | Grain sit close, not spread wide */
[data-testid="stPopoverBody"] p, [data-testid="stPopoverBody"] label,
[data-testid="stPopoverBody"] span, [data-testid="stPopoverBody"] div {{ color: var(--nr-text); }}
[data-testid="stPopoverBody"] .stButton button {{
  background: var(--nr-panel2) !important; color: var(--nr-text) !important;
  border-color: var(--nr-border2) !important; }}
/* radio circles (time range) + grain pills are native widgets that stay light on the static
   config — force them onto the active palette so they aren't white sheets in dark mode. */
[data-testid="stPopoverBody"] button {{
  background: var(--nr-panel2) !important; color: var(--nr-text) !important;
  border-color: var(--nr-border2) !important; }}
[data-testid="stPopoverBody"] [data-baseweb="radio"] div {{
  background: var(--nr-panel2) !important; border-color: var(--nr-border2) !important; }}
[data-testid="stPopoverBody"] [data-baseweb="radio"] div[aria-checked="true"],
[data-testid="stPopoverBody"] [aria-checked="true"] {{ border-color: var(--nr-accent) !important; }}

.block-container {{
  padding-top: 0.6rem;         /* compact: less dead space up top */
  padding-bottom: 3rem;        /* clearance so the fixed Ask-AI dock never covers content */
  max-width: 1560px;           /* wider content = less empty side padding on big screens */
}}

#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}

[data-testid="stSidebar"] {{
  background-color: var(--nr-bg);
  border-right: 1px solid var(--nr-border);
}}
[data-testid="stSidebar"] a[aria-current="page"] {{ color: var(--nr-accent); }}

/* ---------- brand masthead ---------- */
.nr-brand {{
  display: flex; align-items: center; gap: 14px;
  padding: 14px 0 6px; border-bottom: 1px solid var(--nr-border);
  margin-bottom: 10px;
}}
.nr-brand .logo {{ font-size: 17px; font-weight: 700; letter-spacing: 0.14em; color: var(--nr-text); }}
.nr-brand .logo span {{ color: var(--nr-accent); }}
.nr-brand .sub {{ font-size: 12px; color: var(--nr-text3); letter-spacing: 0.02em; }}
.nr-brand .spacer {{ flex: 1; }}
.nr-brand .meta {{ font-size: 11px; color: var(--nr-text3); font-family: ui-monospace, 'SF Mono', Menlo, monospace; }}

/* ---------- crumbs + page head ---------- */
.crumbs {{ font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--nr-text3); margin: 4px 0 2px; }}
.nr-pagehead {{ margin: 6px 0 18px; }}
.nr-pagehead .title {{ font-size: 28px; font-weight: 600; letter-spacing: -0.02em; color: var(--nr-text); line-height: 1.1; }}
.nr-pagehead .subtitle {{ font-size: 13px; color: var(--nr-text2); margin-top: 4px; }}

/* ---------- cards ---------- */
.nr-card {{
  background: var(--nr-panel); border: 1px solid var(--nr-border);
  border-radius: 3px; padding: 14px 16px; margin: 8px 0;
}}
.nr-card--ok {{ border-left: 3px solid var(--nr-green); }}
.nr-card--crit {{ border-left: 3px solid var(--nr-red); }}
.nr-card--warn {{ border-left: 3px solid var(--nr-yellow); }}
.nr-card--info {{ border-left: 3px solid var(--nr-blue); }}

.card-head {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }}
.card-title {{ font-size: 15px; font-weight: 600; color: var(--nr-text); }}
.card-sub {{ font-size: 11.5px; color: var(--nr-text3); }}

/* ---------- KPI row ---------- */
.nr-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(108px, 1fr)); gap: 8px; margin: 4px 0 6px; }}
.nr-kpi {{ background: var(--nr-panel); border: 1px solid var(--nr-border); border-radius: 3px; padding: 6px 10px; }}
.k-label {{ font-size: 10px; letter-spacing: 0.05em; text-transform: uppercase; color: var(--nr-text3); }}
.k-value {{ font-size: 15px; font-weight: 700; color: var(--nr-text); margin: 4px 0 2px; font-variant-numeric: tabular-nums; }}
.k-value.up {{ color: var(--nr-green); }}
.k-value.down {{ color: var(--nr-red); }}
.k-sub {{ font-size: 10px; color: var(--nr-text3); }}

/* ---------- loading skeletons ---------- */
@keyframes nr-shimmer {{ 0% {{ background-position: -400px 0; }} 100% {{ background-position: 400px 0; }} }}
.nr-skel {{ border-radius: 3px; background: linear-gradient(90deg, var(--nr-panel) 25%, var(--nr-panel2) 50%, var(--nr-panel) 75%);
  background-size: 800px 100%; animation: nr-shimmer 1.1s linear infinite; border: 1px solid var(--nr-border); }}
.nr-skel-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 6px 0; }}
.nr-skel-tile {{ height: 148px; }}
.nr-skel-row {{ height: 54px; margin: 6px 0; }}
.nr-spin {{ display: inline-block; width: 14px; height: 14px; border: 2px solid var(--nr-border2);
  border-top-color: var(--nr-accent); border-radius: 50%; animation: nr-rot 0.8s linear infinite;
  vertical-align: -2px; margin-right: 7px; }}
@keyframes nr-rot {{ to {{ transform: rotate(360deg); }} }}

/* ---------- sections ---------- */
.nr-section {{ display: flex; align-items: baseline; gap: 10px; margin: 10px 0 6px; }}
.nr-section .num {{ font-size: 11px; font-weight: 700; color: var(--nr-accent); border: 1px solid var(--nr-border2); border-radius: 3px; padding: 1px 6px; }}
.nr-section .title {{ font-size: 16px; font-weight: 600; color: var(--nr-text); }}
.nr-section .subtitle {{ font-size: 12px; color: var(--nr-text3); }}

/* ---------- chips ---------- */
.nr-chip {{ display: inline-block; font-size: 11px; font-weight: 600; letter-spacing: 0.04em; border-radius: 3px; padding: 2px 8px; white-space: nowrap; }}
.nr-chip--ok {{ color: var(--nr-green); background: var(--nr-green-a10); border: 1px solid var(--nr-green-a35); }}
.nr-chip--crit {{ color: var(--nr-red); background: var(--nr-red-a10); border: 1px solid var(--nr-red-a35); }}
.nr-chip--warn {{ color: var(--nr-yellow); background: var(--nr-yellow-a10); border: 1px solid var(--nr-yellow-a35); }}
.nr-chip--info {{ color: var(--nr-accent); background: var(--nr-accent-a10); border: 1px solid var(--nr-accent-a35); }}

/* ---------- tables ---------- */
.nr-table-wrap {{ overflow-x: auto; margin: 6px 0; }}
.nr-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
.nr-table th {{ text-align: left; font-size: 10.5px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--nr-text3); font-weight: 600; padding: 6px 10px; border-bottom: 1px solid var(--nr-border2); white-space: nowrap; }}
.nr-table td {{ padding: 7px 10px; border-bottom: 1px solid var(--nr-border); color: var(--nr-text); vertical-align: top; }}
.nr-table tr:hover td {{ background: var(--nr-accent-a04); }}
.nr-table td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.nr-table td.mono {{ font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 11.5px; }}

/* ---------- empty states ---------- */
.nr-empty {{ border: 1px dashed var(--nr-border2); border-radius: 3px; padding: 18px; color: var(--nr-text2); font-size: 13px; margin: 8px 0; }}
.nr-empty b {{ color: var(--nr-text); }}
.nr-empty .why {{ display: block; font-size: 12px; color: var(--nr-text3); margin-top: 4px; }}

/* ---------- evidence / detail chips ---------- */
.nr-ev {{
  display: inline-block; color: var(--nr-accent); background: var(--nr-accent-a08);
  border: 1px solid var(--nr-accent-a30); border-radius: 3px; padding: 1px 7px;
  font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; margin: 1px 2px; cursor: pointer;
}}
.nr-ev small {{ font-size: 9.5px; font-weight: 400; color: var(--nr-text3); margin-left: 4px; }}
.nr-ev--unresolved {{ color: var(--nr-red); background: var(--nr-red-a08); border-color: var(--nr-red-a40); }}
.nr-ev--unresolved small {{ color: var(--nr-red); }}

/* ---------- prose ---------- */
.nr-prose {{ font-size: 13.5px; line-height: 1.65; color: var(--nr-text); margin: 6px 0; }}

/* ---------- footer ---------- */
.nr-foot {{ display: flex; flex-wrap: wrap; gap: 18px; margin-top: 30px; padding-top: 12px; border-top: 1px solid var(--nr-border); font-size: 11px; color: var(--nr-text3); }}
.nr-foot b {{ color: var(--nr-text2); font-weight: 600; }}
.nr-foot .mono {{ font-family: ui-monospace, 'SF Mono', Menlo, monospace; }}

/* ---------- streamlit chrome fixes ---------- */
[data-testid="stVerticalBlock"] > div {{ gap: 0.4rem; }}
h1, h2, h3 {{ font-family: var(--nr-font) !important; }}
[data-testid="stMetric"] {{ background: var(--nr-panel); border: 1px solid var(--nr-border); border-radius: 3px; padding: 10px 14px; }}
button[kind="primary"] {{ background: var(--nr-brand); border: 1px solid var(--nr-brand2); border-radius: 3px; color: #fff; font-family: var(--nr-font); }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--nr-border); border-radius: 3px; }}
[data-testid="stExpander"] details {{ border: 1px solid var(--nr-border); border-radius: 3px; background: var(--nr-panel); }}
[data-testid="stPopover"] {{ background: var(--nr-panel2); border: 1px solid var(--nr-border2); }}
"""


def inject(page_title: str = "Dashboard", page_icon: str = "◈",
           layout: str = "wide", theme: str = None) -> None:
    """Apply the NR One theme: page config + global CSS (idempotent).

    Call ONCE at the very top of your app, before any other st call. Pass theme='light' or 'dark'
    to select the palette (defaults to the current active palette). The :root vars are regenerated
    from the active palette so a mid-session theme switch re-colours the whole page.
    """
    if theme is not None:
        set_theme(theme)
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout=layout,
        initial_sidebar_state="expanded",
    )
    st.markdown(f"<style>{_root_vars()}\n{_CSS}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 2. SAFETY + FORMATTERS
# ---------------------------------------------------------------------------

def esc(value: Any) -> str:
    """Escape any string that comes from data — never trust your backend."""
    if value is None:
        return ""
    return _html.escape(str(value))


def fmt_value(value: Any, kind: str = "num", default: str = "—") -> str:
    """Format a value by kind: usd, pct, z, score, ms, int, num, or raw str."""
    if value is None:
        return default
    kind = kind or "num"
    if isinstance(value, str):
        return value
    if kind == "usd":
        return f"${value:,.2f}"
    if kind == "pct":
        return f"{value:+.1f}%"
    if kind == "z":
        return f"{value:.2f}"
    if kind == "score":
        return f"{value:.2f}"
    if kind == "ms":
        return f"{value:,.0f} ms"
    if kind == "int":
        return f"{value:,.0f}"
    return f"{value:,.0f}"


def human_bytes(n: Any) -> str:
    """Human-readable byte size (B/KB/MB/GB/TB)."""
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0 or unit == "TB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024.0
    return f"{n:,.1f} PB"


# ---------------------------------------------------------------------------
# 3. COMPONENTS (all return HTML strings for unsafe_allow_html=True)
# ---------------------------------------------------------------------------

def brand(product: str, tagline: str = "", meta: str = "") -> str:
    """Product masthead: PRODUCT <accent>word</accent> · tagline · meta."""
    logo = esc(product)
    if " " in product:
        head, _, tail = product.rpartition(" ")
        logo = f"{esc(head)} <span>{esc(tail)}</span>"
    return (
        '<div class="nr-brand"><span class="logo">' + logo + "</span>"
        + (f'<span class="sub">{esc(tagline)}</span>' if tagline else "")
        + '<span class="spacer"></span>'
        + (f'<span class="meta">{esc(meta)}</span>' if meta else "")
        + "</div>"
    )


def page_header(title: str, subtitle: str = "") -> str:
    """Big page title block. (The old uppercase eyebrow just repeated the title verbatim —
    a visible duplicate — so it's dropped.)"""
    return (
        f'<div class="nr-pagehead" style="margin-top:2px">'
        f'<div class="title">{esc(title)}</div>'
        + (f'<div class="subtitle">{esc(subtitle)}</div>' if subtitle else "")
        + "</div>"
    )


def chip(text: str, sev: str = "info") -> str:
    """Small status chip with glyph. sev: ok | crit | warn | info."""
    glyph = GLYPHS.get(sev, "◇")
    return f'<span class="nr-chip nr-chip--{sev}">{glyph} {esc(text)}</span>'


def kpi_tile(label: str, value: str, sub: str = "", tone: str = "") -> str:
    """One KPI tile; tone ('up'/'down') colors the value green/red."""
    return (
        f'<div class="nr-kpi"><div class="k-label">{esc(label)}</div>'
        f'<div class="k-value {esc(tone)}">{esc(value)}</div>'
        f'<div class="k-sub">{esc(sub)}</div></div>'
    )


def kpi_row(tiles: Sequence[str]) -> str:
    """Responsive KPI grid from tile strings."""
    return f'<div class="nr-kpis">{"".join(tiles)}</div>'


def card(title: str = "", sub: str = "", body: str = "", tone: str = "") -> str:
    """NR card with optional header and tone (ok/crit/warn/info)."""
    head = ""
    if title:
        head = (f'<div class="card-head"><span class="card-title">{esc(title)}</span>'
                f'<span class="card-sub">{esc(sub)}</span></div>')
    tone_cls = f" nr-card--{tone}" if tone else ""
    return f'<div class="nr-card{tone_cls}">{head}{body}</div>'


def section_header(num: str, title: str, subtitle: str = "") -> None:
    """Numbered section header, written directly to the page."""
    st.markdown(
        f'<div class="nr-section"><span class="num">{esc(num)}</span>'
        f'<span class="title">{esc(title)}</span>'
        + (f'<span class="subtitle">{esc(subtitle)}</span>' if subtitle else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def table_html(headers: Sequence[str], rows: Sequence[Sequence[Any]],
               aligns: Optional[Sequence[str]] = None) -> str:
    """NR table; aligns: '', 'num' (right), 'mono' (monospace)."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body: List[str] = []
    for row in rows:
        tds = []
        for i, cell in enumerate(row):
            cls = aligns[i] if aligns and i < len(aligns) else ""
            tds.append(f'<td class="{cls}">{esc(cell)}</td>')
        body.append("<tr>" + "".join(tds) + "</tr>")
    return (
        f'<div class="nr-table-wrap"><table class="nr-table"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


def empty_state(title: str, why: str = "") -> str:
    """Dashed empty-state block with an honest explanation."""
    why_html = f' <span class="why">{esc(why)}</span>' if why else ""
    return f'<div class="nr-empty"><b>{esc(title)}</b>{why_html}</div>'


def detail_chip(label: str, value: Any, fmt_kind: str = "num",
                details: Optional[Dict[str, Any]] = None,
                popover_caption: str = "") -> None:
    """Inline chip; clicking opens a popover with a detail block (query/sql/ev)."""
    val = fmt_value(value, fmt_kind or "num")
    chip_html = (
        f'<span class="nr-ev">{esc(val)} <small>{esc(label)}</small></span>'
    )
    st.markdown(chip_html, unsafe_allow_html=True)
    with st.popover(f"{label}", use_container_width=False):
        if popover_caption:
            st.caption(popover_caption)
        details = details or {}
        rows = []
        for k, v in details.items():
            rows.append((k, v))
        if rows:
            st.markdown(
                table_html(["key", "value"], rows, aligns=["", "mono"]),
                unsafe_allow_html=True,
            )


def footnote(items: Sequence[Tuple[str, str]]) -> str:
    """Page footer of key/value pairs."""
    spans = "".join(
        f'<span>{esc(k)} <b>{esc(v)}</b></span>' for k, v in items
    )
    return f'<div class="nr-foot">{spans}</div>'


# ---------------------------------------------------------------------------
# 4. SVG CHARTS (pure HTML/SVG, no JS, no charting lib)
# ---------------------------------------------------------------------------

def _polyline(points: Sequence[Sequence[float]]) -> str:
    # Stroked path only — no drop-to-baseline close (that tail drew a stray
    # vertical stroke at the right edge of every chart).
    if not points:
        return ""
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)


def svg_line_chart(series: Sequence[Dict[str, Any]], value_key: str = "value",
                   label_key: str = "label", breached: bool = False,
                   start: str = "", end: str = "",
                   value_label: str = "") -> str:
    """Daily-style line chart with median±2·MAD band and optional shaded range.

    series: [{label: '2026-06-29', value: 510.2}, ...]
    start/end: shade the range [start, end] (inclusive, string compare).
    """
    # Sort by label ONLY, and keep the FULL label: the old [:10] truncation
    # collapsed every sub-day label to its date, so the tuple sort re-ordered
    # points within a day by VALUE — the drawn line was a per-day sorted
    # sawtooth while the hover dot tracked true chronological values.
    pts = sorted(
        [(str(r.get(label_key)), float(r.get(value_key) or 0))
         for r in (series or []) if r.get(value_key) is not None],
        key=lambda p: p[0],
    )
    if len(pts) < 2:
        return empty_state("No series", "no rows to plot")
    W, H = 720, 220
    pad_l, pad_r, pad_t, pad_b = 52, 18, 18, 30
    inner_w, inner_h = W - pad_l - pad_r, H - pad_t - pad_b
    labels = [d for d, _ in pts]
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    span = max(hi - lo, 1e-9)
    lo -= span * 0.06
    hi += span * 0.06

    def X(i: int) -> float:
        return pad_l + i * inner_w / max(len(pts) - 1, 1)

    def Y(v: float) -> float:
        return pad_t + (hi - v) / max(hi - lo, 1e-9) * inner_h

    s = sorted(vals)
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    mad = sorted(abs(v - med) for v in s)[n // 2]
    band = max(mad * 1.4826 * 2.0, 1e-9)

    parts: List[str] = []

    idx_in = [i for i, d in enumerate(labels) if start and end and start <= d <= end]
    if idx_in:
        x0 = X(min(idx_in))
        x1 = X(max(idx_in)) + (X(1) - X(0))
        parts.append(f'<rect x="{x0:.1f}" width="{max(x1 - x0, 4):.1f}" '
                     f'y="{pad_t:.1f}" height="{inner_h:.1f}" '
                     f'fill="{T["brand"]}" opacity="0.06"/>')

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + frac * inner_h
        parts.append(f'<line x1="{pad_l:.1f}" y1="{y:.1f}" x2="{W - pad_r:.1f}" '
                     f'y2="{y:.1f}" stroke="{T["border"]}" stroke-width="1"/>')

    band_top = [(X(i), Y(med + band)) for i in range(len(pts))]
    band_bot = [(X(i), Y(med - band)) for i in range(len(pts))]
    band_path = (
        f"M {band_top[0][0]:.1f} {band_top[0][1]:.1f} "
        + " L ".join(f"{x:.1f} {y:.1f}" for x, y in band_top[1:])
        + " L " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in reversed(band_bot))
        + " Z"
    )
    med_path = f"M {X(0):.1f} {Y(med):.1f} L {X(len(pts) - 1):.1f} {Y(med):.1f}"
    line_path = _polyline([(X(i), Y(v)) for i, v in enumerate(vals)])
    parts.append(
        f'<path d="{band_path}" fill="{T["brand"]}" opacity="0.16"/>'
        f'<path d="{med_path}" fill="none" stroke="{T["border2"]}" '
        f'stroke-width="1" opacity="0.5" stroke-dasharray="4 4"/>'
        f'<path d="{line_path}" fill="none" stroke="{T["link"]}" stroke-width="2"/>'
    )

    # Ticks show an abbreviated date ("Jun 01") at a size that survives the
    # viewBox downscale; a single-day series shows HH:MM instead.
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def _tick(d: str) -> str:
        if same_day:
            return d[11:16] or d[:10]
        try:
            return f"{months[int(d[5:7])]} {d[8:10]}"
        except (ValueError, IndexError):
            return d[:10]

    same_day = len({d[:10] for d in labels}) == 1
    step = max((len(pts) + 4) // 5, 1)
    for i in range(0, len(pts), step):
        parts.append(f'<text x="{X(i):.1f}" y="{H - 8:.1f}" font-size="13" '
                     f'fill="{T["text3"]}">{esc(_tick(labels[i]))}</text>')

    # minimal y-scale: min/max endpoint labels in the left gutter
    def _axis(v: float) -> str:
        a = abs(v)
        if a >= 1e6:
            return f"{v / 1e6:.2f}M"
        if a >= 1e4:
            return f"{v / 1e3:.0f}k"
        return f"{v:,.4g}"

    for v, y in ((hi, pad_t + 10), (lo, pad_t + inner_h)):
        parts.append(f'<text x="{pad_l - 6:.1f}" y="{y:.1f}" text-anchor="end" '
                     f'font-size="12" fill="{T["text3"]}">{esc(_axis(v))}</text>')

    if breached and idx_in:
        for i in idx_in:
            parts.append(f'<circle cx="{X(i):.1f}" cy="{Y(vals[i]):.1f}" r="3" '
                         f'fill="{T["red"]}"/>')

    if value_label:
        parts.append(
            f'<text x="{W - pad_r:.1f}" y="{pad_t + 4:.1f}" text-anchor="end" '
            f'font-size="10" fill="{T["text3"]}">{esc(value_label)}</text>'
        )

    return f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto">{"".join(parts)}</svg>'


def svg_donut(pct: Optional[float], center_label: str = "", sub_label: str = "") -> str:
    """Donut showing pct (0-100); center shows the number."""
    if pct is None:
        return empty_state("No share", "value absent from the data")
    pct = max(0.0, min(float(pct), 100.0))
    cx, cy, r = 46.0, 46.0, 34.0
    circ = 2.0 * 3.14159 * r
    dash = circ * pct / 100.0
    sub = f'<text x="{cx:.1f}" y="{cy + 17:.1f}" text-anchor="middle" font-size="8.5" ' \
          f'fill="{T["text3"]}">{esc(sub_label)}</text>' if sub_label else ""
    return (
        f'<svg viewBox="0 0 92 92" width="92" height="92">'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" '
        f'stroke="{T["border"]}" stroke-width="10"/>'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" '
        f'stroke="{T["brand"]}" stroke-width="10" '
        f'stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-dashoffset="0" '
        f'transform="rotate(-90 {cx:.1f} {cy:.1f})"/>'
        f'<text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" font-size="11" '
        f'fill="{T["text"]}">{esc(center_label or f"{pct:.0f}%")}</text>'
        f'{sub}</svg>'
    )


def _wf_num(value: Any, default: float = 0.0) -> float:
    """Anything -> a finite float. None, '', 'abc', NaN and inf all collapse to `default`."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if _math.isfinite(f) else default


def _wf_unit(metric: str = "", unit: str = "") -> str:
    """Resolve the unit for a metric key: explicit `unit` wins, then ui.explain, else ''."""
    if unit:
        return unit
    if metric and _X is not None:
        return _X.metric_unit(metric)
    return ""


def _wf_amount(value: float, unit: str = "", signed: bool = False) -> str:
    """One number with its unit, e.g. '$2.34' / '+$0.51' / '-0.4%' / '1.57k'.

    Without a known unit the number is still shown — compact, never bare-truncated —
    because an unlabelled bar was the original chart's worst failure.
    """
    v = _wf_num(value)
    mag = abs(v)
    if unit and _X is not None:
        body = _X.fmt_value(mag, unit)
        if mag and not any(c in "123456789" for c in body):
            # rounds to $0.00 / 0.0% — say the real size instead of a fake zero
            body = ("$" + f"{mag:,.2g}" if unit == "usd"
                    else f"{mag * 100:,.2g}%" if unit == "rate"
                    else f"{mag:,.2g}")
    elif mag >= 1e6:
        body = f"{mag / 1e6:.2f}M"
    elif mag >= 1e4:
        body = f"{mag / 1e3:.1f}k"
    elif mag == 0:
        body = "0"
    else:
        body = f"{mag:,.4g}"
    if not signed:
        return body if v >= 0 else f"-{body}"
    if v == 0:
        return f"±{body}"
    return f"{'+' if v > 0 else '-'}{body}"


def _wf_name(label: Any, limit: int = 18) -> str:
    """Engine key -> readable factor name, truncated to what the label gutter can hold."""
    raw = str(label if label not in (None, "") else "?")
    name = _X.metric_name(raw) if _X is not None else raw.replace("_", " ").capitalize()
    return name if len(name) <= limit else name[: limit - 1].rstrip() + "…"


def svg_waterfall(baseline: float, factors: Sequence[Dict[str, Any]],
                  observed: Optional[float] = None, *,
                  metric: str = "", unit: str = "", width: int = 560,
                  baseline_label: str = "Normal",
                  observed_label: str = "Observed") -> str:
    """HORIZONTAL waterfall of the revenue identity: what each factor added to the move.

    Bars run left-to-right on a **change-vs-normal** axis anchored at zero, so the
    dashed zero line *is* the baseline and every factor bar is proportional to what
    it actually contributed. Names live in a left gutter (readable at 12px instead of
    a rotated 6px tick) and every bar carries its value in the right gutter.

    factors: [{label, contribution}, ...] — contribution is in the metric's own units
             and the contributions are expected to add up to (observed - baseline).
             Whatever they don't explain is drawn as an explicit "Unexplained" bar.
    Keyword-only extras are additive; the positional signature is unchanged.
    """
    items = [f for f in (factors or []) if isinstance(f, dict)]
    if not items:
        return empty_state("No decomposition",
                           "the engine emitted no factor contributions for this incident")

    u = _wf_unit(metric, unit)
    base = _wf_num(baseline)
    contribs = [_wf_num(f.get("contribution")) for f in items]
    explained = sum(contribs)
    obs = _wf_num(observed, base + explained)
    total = obs - base

    # ---- rows: Normal marker -> one bar per factor -> (Unexplained) -> Observed total
    rows: List[Dict[str, Any]] = [{
        "kind": "total", "name": baseline_label, "sub": "baseline level",
        "start": 0.0, "end": 0.0, "amount": base,
    }]
    reconciled = abs(total - explained) <= max(abs(total), abs(explained)) * 0.05
    run = 0.0
    for f, c in zip(items, contribs):
        share = ""
        if reconciled and abs(total) > 1e-12:
            p = c / total * 100.0
            if abs(p) >= 0.5:
                share = (f"{p:.0f}% of the move" if p > 0
                         else f"{abs(p):.0f}% against the move")
            else:
                share = "<1% of the move"
        rows.append({"kind": "delta", "name": _wf_name(f.get("label")), "sub": share,
                     "start": run, "end": run + c, "amount": c})
        run += c
    residual = total - run
    if abs(residual) > max(abs(total) * 0.005, 1e-9):
        rows.append({"kind": "resid", "name": "Unexplained", "sub": "residual",
                     "start": run, "end": total, "amount": residual})
    rows.append({"kind": "total", "name": observed_label,
                 "sub": f"{_wf_amount(total, u, signed=True)} vs normal",
                 "start": 0.0, "end": total, "amount": obs})

    # ---- geometry ---------------------------------------------------------
    W = int(max(420, min(int(_wf_num(width, 560)) or 560, 960)))
    PAD_L, PAD_R, GUT_L, GUT_R = 10, 10, 122, 92
    HEAD_H, ROW_H, BAR_H, AXIS_H = 26, 34, 15, 26
    x0, x1 = PAD_L + GUT_L, W - PAD_R - GUT_R
    plot_w = max(x1 - x0, 40)
    H = HEAD_H + len(rows) * ROW_H + AXIS_H

    edges = [0.0] + [r["start"] for r in rows] + [r["end"] for r in rows]
    lo, hi = min(edges), max(edges)
    if hi - lo < 1e-12:                                   # every contribution was zero
        step = max(abs(base) * 0.01, 1.0)
        lo, hi = -step, step
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    span = hi - lo

    def X(v: float) -> float:
        return x0 + (v - lo) / span * plot_w

    zero_x = X(0.0)
    parts: List[str] = []

    # column headers
    parts.append(f'<text x="{PAD_L}" y="12" font-size="10" letter-spacing="0.06em" '
                 f'fill="var(--nr-text3)">FACTOR</text>')
    parts.append(f'<text x="{W - PAD_R}" y="12" text-anchor="end" font-size="10" '
                 f'letter-spacing="0.06em" fill="var(--nr-text3)">AMOUNT</text>')

    # the baseline reference: a dashed zero line through every row, labelled with the level
    rows_bottom = HEAD_H + len(rows) * ROW_H
    parts.append(f'<line x1="{zero_x:.1f}" y1="{HEAD_H - 8}" x2="{zero_x:.1f}" '
                 f'y2="{rows_bottom + 6}" stroke="var(--nr-accent)" stroke-width="1" '
                 f'stroke-dasharray="3 3" opacity="0.55"/>')
    anchor = "middle"
    if zero_x - x0 < 46:
        anchor = "start"
    elif x1 - zero_x < 46:
        anchor = "end"
    parts.append(f'<text x="{zero_x:.1f}" y="{HEAD_H - 12}" text-anchor="{anchor}" '
                 f'font-size="10" fill="var(--nr-text3)">'
                 f'normal {esc(_wf_amount(base, u))}</text>')

    for i, r in enumerate(rows):
        top = HEAD_H + i * ROW_H
        bar_y = top + 5
        xa, xb = X(_wf_num(r["start"])), X(_wf_num(r["end"]))
        left, right = min(xa, xb), max(xa, xb)
        kind = r["kind"]
        min_w = 3.0 if kind == "total" else 2.0
        tiny = (right - left) < min_w
        if tiny:                                   # "checked it, it did nothing" stays visible
            left, right = xa - min_w / 2, xa + min_w / 2
        if kind == "total":
            fill, stroke, dash = "var(--nr-accent-a16)", "var(--nr-accent)", ""
            val_fill = "var(--nr-text)"
        elif kind == "resid":
            fill, stroke, dash = "none", "var(--nr-text3)", ' stroke-dasharray="3 2"'
            val_fill = "var(--nr-text2)"
        else:
            c = _wf_num(r["amount"])
            fill = ("var(--nr-text3)" if c == 0 else                # exactly nil = no direction
                    "var(--nr-green)" if c > 0 else "var(--nr-red)")
            stroke, dash = "none", ""
            val_fill = "var(--nr-text2)" if c == 0 else fill
        signed = kind != "total"
        amount_txt = _wf_amount(r["amount"], u, signed=signed)
        parts.append(
            f'<g><title>{esc(r["name"])}: {esc(amount_txt)}</title>'
            f'<rect x="{left:.1f}" y="{bar_y}" width="{max(right - left, min_w):.1f}" '
            f'height="{BAR_H}" rx="1.5" fill="{fill}" stroke="{stroke}"{dash}/></g>'
        )
        if tiny and kind != "total":               # tick so a near-zero factor is still findable
            parts.append(f'<line x1="{xa:.1f}" y1="{bar_y - 5}" x2="{xa:.1f}" '
                         f'y2="{bar_y + BAR_H + 5}" stroke="{stroke if stroke != "none" else fill}" '
                         f'stroke-width="1" opacity="0.6"/>')
        if i:                                      # waterfall connector to the row above
            prev_x = X(_wf_num(rows[i - 1]["end"]))
            if abs(prev_x - xa) < 0.75 and rows[i - 1]["kind"] != "total":
                parts.append(f'<line x1="{xa:.1f}" y1="{top - ROW_H + 5 + BAR_H}" '
                             f'x2="{xa:.1f}" y2="{bar_y}" stroke="var(--nr-border2)" '
                             f'stroke-width="1" stroke-dasharray="2 2"/>')
            parts.append(f'<line x1="{PAD_L}" y1="{top:.1f}" x2="{W - PAD_R}" y2="{top:.1f}" '
                         f'stroke="var(--nr-border)" stroke-width="1"/>')
        weight = ' font-weight="600"' if kind == "total" else ""
        parts.append(f'<text x="{PAD_L}" y="{top + 16}" font-size="12"{weight} '
                     f'fill="var(--nr-text)">{esc(r["name"])}</text>')
        if r.get("sub"):
            parts.append(f'<text x="{PAD_L}" y="{top + 28}" font-size="10" '
                         f'fill="var(--nr-text3)">{esc(r["sub"])}</text>')
        parts.append(f'<text x="{W - PAD_R}" y="{top + 16}" text-anchor="end" font-size="11" '
                     f'font-weight="600" fill="{val_fill}">{esc(amount_txt)}</text>')

    # ---- axis: the scale that makes bar length mean something --------------
    ay = rows_bottom + 8
    parts.append(f'<line x1="{x0}" y1="{ay}" x2="{x1}" y2="{ay}" '
                 f'stroke="var(--nr-border2)" stroke-width="1"/>')
    parts.append(f'<text x="{PAD_L}" y="{ay + 12}" font-size="10" '
                 f'fill="var(--nr-text3)">change vs normal</text>')
    for v, ax in ((lo, "start"), (0.0, "middle"), (hi, "end")):
        if v != 0 and abs(X(v) - zero_x) < 40:        # never let an end tick hit the zero tick
            continue
        tick = "0" if v == 0 else _wf_amount(v, u, signed=True)
        parts.append(f'<text x="{X(v):.1f}" y="{ay + 12}" text-anchor="{ax}" font-size="10" '
                     f'fill="var(--nr-text3)">{esc(tick)}</text>')

    return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto" role="img" '
            f'aria-label="Waterfall of contributions to the change vs normal">'
            f'{"".join(parts)}</svg>')


def svg_funnel(steps: Sequence[Dict[str, Any]]) -> str:
    """Funnel: steps = [{gate: 'G1 effect', remaining: 60}, ...]."""
    steps = list(steps or [])
    if not steps:
        return ""
    W, H = 460, len(steps) * 46 + 18
    maxv = max(float(s.get("remaining") or 0) for s in steps)
    parts: List[str] = []
    for i, s in enumerate(steps):
        rem = float(s.get("remaining") or 0)
        frac = rem / maxv if maxv else 0.0
        bw = max(24.0, frac * (W - 130))
        x = (W - bw) / 2
        y = 10 + i * 46
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="24" rx="2" '
            f'fill="{T["brand"]}" opacity="0.25"/>'
        )
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="3" rx="1" '
            f'fill="{T["brand"]}"/>'
        )
        parts.append(
            f'<text x="{x - 8:.1f}" y="{y + 16:.1f}" text-anchor="end" font-size="11" '
            f'fill="{T["text2"]}">{esc(s.get("gate", ""))}</text>'
        )
        parts.append(
            f'<text x="{x + bw + 8:.1f}" y="{y + 16:.1f}" text-anchor="start" '
            f'font-size="12" font-weight="600" fill="{T["text"]}">{rem:,.0f}</text>'
        )
    return f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto">{"".join(parts)}</svg>'

def skeleton(kind: str = "grid", n_tiles: int = 6, note: str = "loading…") -> str:
    """Shimmer placeholder shown while a section's data/component loads."""
    if kind == "grid":
        tiles = "".join('<div class="nr-skel nr-skel-tile"></div>' for _ in range(n_tiles))
        return (f'<div style="font-size:11px;color:var(--nr-text3);margin:2px 0 6px;">'
                f'<span class="nr-spin"></span>{esc(note)}</div>'
                f'<div class="nr-skel-grid">{tiles}</div>')
    rows = "".join('<div class="nr-skel nr-skel-row"></div>' for _ in range(n_tiles))
    return (f'<div style="font-size:11px;color:var(--nr-text3);margin:2px 0 6px;">'
            f'<span class="nr-spin"></span>{esc(note)}</div>{rows}')


# ---------------------------------------------------------------------------
# 9. SELF-CHECK  (python -m ui.nr_one)
# ---------------------------------------------------------------------------

def demo() -> None:
    """Assert the chart contracts a broken read-out would violate. No test framework."""
    live = [{"label": "requests", "contribution": 0.0747},
            {"label": "fill_rate", "contribution": -0.0023},
            {"label": "render_rate", "contribution": -0.0001},
            {"label": "ecpm", "contribution": 0.5177}]
    svg = svg_waterfall(2.34, live, observed=2.93, metric="revenue")

    # structure
    assert svg.startswith("<svg") and svg.endswith("</svg>"), "must be one closed <svg>"
    assert svg.count("<svg") == 1 and svg.count("</svg>") == 1
    assert svg.count("<g>") == svg.count("</g>") == len(live) + 2      # 4 factors + 2 totals

    # every bar is named AND valued — the two things the old chart omitted
    for name in ("Ad requests", "Fill rate", "Render rate", "eCPM", "Normal", "Observed"):
        assert f">{name}<" in svg, f"missing bar label {name}"
    assert ">$2.34<" in svg and ">$2.93<" in svg, "totals must show their level"
    assert ">+$0.52<" in svg, "eCPM contribution must be printed with its unit"
    assert "change vs normal" in svg and "normal $2.34" in svg, "axis + baseline label"
    assert "88% of the move" in svg, "share of the move must be stated"
    assert "-$0.0023" in svg, "a near-zero factor states its real size, never '-$0.00'"

    # no text below 10px anywhere
    sizes = [float(s.split('"')[0]) for s in svg.split('font-size="')[1:]]
    assert sizes and min(sizes) >= 10.0, f"font smaller than 10px: {min(sizes)}"

    # direction is colour; the total is accent-outlined, never red
    assert "var(--nr-green)" in svg and "var(--nr-red)" in svg
    assert "var(--nr-accent)" in svg and "#" not in svg, "tokens only, no raw hex"

    # a near-zero factor still gets a bar with a minimum size + a locating tick
    widths = [float(s.split('"')[0]) for s in svg.split(' width="')[1:]]
    assert min(widths) >= 2.0, "near-zero bars must keep a visible minimum width"

    # unexplained residual is drawn, not silently swallowed
    gap = svg_waterfall(2.34, [{"label": "ecpm", "contribution": 0.10}], observed=2.93)
    assert ">Unexplained<" in gap and ">+0.49<" in gap

    # degenerate inputs: no crash, no broken svg
    assert "No decomposition" in svg_waterfall(1.0, [])
    assert "No decomposition" in svg_waterfall(0, None)               # type: ignore[arg-type]
    for bad in (
        svg_waterfall(0.0, [{"label": "ecpm", "contribution": 0.0}], observed=0.0),
        svg_waterfall(None, [{"label": None, "contribution": None}], observed=None),  # type: ignore[arg-type]
        svg_waterfall(float("nan"), [{"label": "x", "contribution": float("inf")}]),
        svg_waterfall(5.0, [{"label": "ecpm", "contribution": "oops"}], observed=5.0),
        svg_waterfall(1.0, [{}, "not-a-dict"], observed=2.0),         # type: ignore[list-item]
        svg_waterfall(1e9, [{"label": "requests", "contribution": -4.2e8}], width=99),
    ):
        assert bad.startswith("<svg") and bad.endswith("</svg>") and "nan" not in bad.lower()

    # the positional call ui/diagnosis.py makes still works untouched
    assert svg_waterfall(1574.48, [{"label": "fill_rate", "contribution": -68.93}],
                         1536.99).startswith("<svg")
    print("nr_one.py OK")


if __name__ == "__main__":
    demo()
