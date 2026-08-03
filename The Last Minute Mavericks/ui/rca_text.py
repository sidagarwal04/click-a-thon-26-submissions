"""RootCauseOS — RCA read-out wording and number formatting.

Pure functions: no Streamlit, no bundle shapes. Everything that turns a raw
engine value into the words and figures the read-out prints lives here, so a
number is formatted one way on the whole page.

Split out of ui/diagnosis.py — see that module for the page itself.
"""
from __future__ import annotations

import re

from ui import explain as X
from ui import nr_one as n

_MONTHS = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# engine unit strings -> the vocabulary explain.fmt_value speaks
_UNIT_ALIAS = {"usd": "usd", "money": "usd", "rate": "rate", "ratio": "rate",
               "int": "int", "count": "int", "pct": "pct", "percent": "pct",
               "score": "num", "num": "num"}

_DASH = "—"


# ------------------------------------------------------------- formatting

def _date(raw) -> str:
    """`2026-06-16T00:00:00Z` -> `16 Jun 2026`. Absent -> ''."""
    s = str(raw or "")[:10]
    try:
        return f"{int(s[8:10])} {_MONTHS[int(s[5:7])]} {s[:4]}"
    except (ValueError, IndexError):
        return s


def _num(value, unit: str = "num") -> str:
    """One number in its unit, via the shared vocabulary. None -> —."""
    if unit == "pct" and value is not None:
        try:                       # a signed zero reads as a typo, not a number
            if abs(float(value)) < 0.05:
                return "0.0%"
        except (TypeError, ValueError):
            pass
    return X.fmt_value(value, unit)


def _delta(value) -> str:
    """A signed percentage move, with -0.0% collapsed to a plain 0.0%."""
    try:
        if abs(float(value)) < 0.05:
            return "0.0%"
    except (TypeError, ValueError):
        pass
    return X.fmt_delta(value)


def _precise_pct(value) -> str:
    """A percentage small enough that one decimal would round it away."""
    try:
        return f"{float(value):g}%"
    except (TypeError, ValueError):
        return _DASH


def _measured(value, suffix: str = "") -> str:
    """A measurement that may not have been taken.

    The engine omits rows_read/duration_ms on some paths; a literal 0 there is a
    missing measurement, not a real one, and printing `0` reads as a bug.
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return _DASH
    if f == 0:
        return _DASH
    return f"{X.fmt_value(f, 'int')}{suffix}"


def _cite(ev_id: str) -> str:
    """`ev_17b` -> `17b` — a footnote marker, not an internal identifier."""
    return str(ev_id or "").replace("ev_", "", 1) or _DASH


def _known_metric(key: str) -> bool:
    return bool(X.metric_meaning(key))


def _seg_phrase(dimension: str = "", value: str = "", co_cut=None) -> str:
    """The culprit as words, co-cut folded in: `Native ads in EU`."""
    seg = str(value or "")
    if seg and "=" not in seg and dimension and "×" not in dimension:
        seg = f"{dimension}={seg}"
    for k, v in (co_cut or {}).items():
        seg += f" × {k}={v}"
    return X.segment_phrase(dimension, seg)


def _in(phrase: str, prep: str = "in") -> str:
    """`Native ads in EU` -> `in Native ads in EU`; `on Android 15` -> `on Android 15`.

    explain.segment_phrase already carries its own preposition for some
    dimensions, so a blind "in " prefix would read "in on Android 15"."""
    p = str(phrase or "").strip()
    if not p:
        return ""
    return p if p.split(" ", 1)[0].lower() in ("in", "on", "at", "for") else f"{prep} {p}"


def _verdict_words(raw: str) -> tuple[str, str]:
    """(tag, sentence) for a factor verdict, tolerating `ruled_out` vs `ruled out`."""
    tag, says = X.factor_verdict(raw)
    if not says and "_" in str(raw or ""):
        tag, says = X.factor_verdict(str(raw).replace("_", " "))
    return tag, says


_SEG_RE = re.compile(r"\b[a-z_]+=[^\s,;.]+(?:\s*[×∩]\s*[a-z_]+=[^\s,;.]+)*")


def _same_fact(a: str, b: str) -> bool:
    """Are these two strings the same statement? Compared on letters and digits only,
    so casing, punctuation and metric-name expansion cannot hide a duplicate."""
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", str(s or "").lower())  # noqa: E731
    x, y = norm(a), norm(b)
    return bool(x) and bool(y) and (x == y or x in y or y in x)


def _identity_phrase(raw: str) -> str:
    """The funnel identity with maths notation a non-mathematician can read.

    `requests × fill_rate × render_rate × ecpm/1000 ≡ revenue/day`
    -> `Ad requests × Fill rate × Render rate × eCPM ÷ 1000 = Revenue per day`
    (metric names are handled by _humanise; this only fixes the operators).
    """
    s = _humanise(str(raw or ""))
    return (s.replace("≡", "=").replace("/1000", " ÷ 1000")
             .replace("/day", " per day").replace("  ", " ").strip().rstrip("."))


_DATE_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*\.\.\s*(\d{4}-\d{2}-\d{2})")


def baseline_caption(raw: str) -> str:
    """Three-word version of _baseline_sentence for a KPI tile / subtitle.

    Same rule: read what the engine did, never assert it. Two call sites in ui/diagnosis.py
    hardcoded "same weekdays before", which stayed on screen even when the engine had fallen
    back to nearest-days on a short slice.
    """
    s = str(raw or "").strip().lower()
    if s.startswith("no baseline"):
        return "no comparable period"
    return "same weekdays before" if s.startswith("same weekdays") else "nearest days before"


def _baseline_sentence(raw: str) -> str:
    """Say what "normal" was measured against, without machine date syntax.

    `same weekdays preceding 2026-06-16..2026-06-18, window + other incidents excluded`
    -> `"Normal" is the same weekdays just before 16 Jun 2026 to 18 Jun 2026, with the
       incident days and any other incidents left out.`

    Read the rule OUT of the engine's string — never assume it. On a slice too short to hold a
    second occurrence of the window's weekdays the engine falls back to nearest-days, and
    hardcoding "the same weekdays" here printed a claim the SQL did not support.
    """
    s = str(raw or "").strip()
    if s.lower().startswith("no baseline"):
        # the engine found nothing to compare against; the date range in that sentence is the
        # INCIDENT window, so the generic path below would invent a baseline out of it
        return "There was no comparable period to measure “normal” against, so the split was not computed."
    m = _DATE_RANGE_RE.search(s)
    if not m:
        return f"“Normal” is {s.rstrip('.')}." if s else ""
    a, b = _date(m.group(1)), _date(m.group(2))
    span = f"{a} to {b}" if a and b and a != b else (a or b)
    lead = ("the same weekdays" if s.lower().startswith("same weekdays")
            else "the nearest days")
    when = "just before" if "preceding" in s.lower() else "around"
    days = re.search(r"\((\d+) days?:", s)
    count = f" ({days.group(1)} days)" if days and days.group(1) != "1" else (
        " (1 day)" if days else "")
    tail = (", with the incident days and any other incidents left out."
            if "exclud" in s.lower() else ".")
    return f"“Normal” is {lead}{count} {when} {span}{tail}"


def _humanise(text: str) -> str:
    """Rewrite a sentence the engine wrote into the shared vocabulary.

    `ecpm moved 25.0% at ad_format=native × region=EU`
    -> `eCPM moved 25.0% at Native ads in EU`
    """
    out = _SEG_RE.sub(lambda m: X.segment_phrase("", m.group(0)), str(text or ""))
    out = re.sub(r"\b(on|in|at|for)\s+\1\b", r"\1", out, flags=re.IGNORECASE)

    def _name(m: re.Match) -> str:
        key = m.group(0)
        if not _known_metric(key):
            return key
        full = X.metric_name(key)
        # idempotent: ui/playbook.py already names its metrics, and rewriting the
        # "requests" inside an existing "Ad requests" produced "Ad Ad requests"
        if out[max(m.end() - len(full), 0):m.end()] == full:
            return key
        return full

    return re.sub(r"\b[a-z][a-z_]*\b", _name, out)


def _lede(text: str, size: float = 15.5) -> str:
    return (f'<div class="nr-prose" style="font-size:{size}px;line-height:1.55">'
            f'{n.esc(text)}</div>')


def _note(text: str) -> str:
    return (f'<div style="font-size:11.5px;color:var(--nr-text3);margin:6px 0 0;'
            f'line-height:1.5">{n.esc(text)}</div>')


def _facts(pairs: list[tuple[str, str]]) -> str:
    return "".join(
        f'<div style="font-size:12.5px;color:var(--nr-text);margin:5px 0">'
        f'<b style="color:var(--nr-text3);font-size:10px;letter-spacing:0.06em;'
        f'text-transform:uppercase;margin-right:8px">{n.esc(k)}</b>{n.esc(v)}</div>'
        for k, v in pairs if v and v != _DASH)
