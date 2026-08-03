"""Plain-English vocabulary for the RCA surfaces.

ONE place that turns engine identifiers into words a human reads. Every RCA panel
imports from here, so `ecpm` is never called three different things on one screen.

Rules this module exists to enforce:
- a metric is named ("eCPM"), and said once in full ("revenue per 1,000 impressions");
- a segment is a phrase ("Native ads in the EU"), never `ad_format=native × region=EU`;
- a number carries its unit — 0.7914 is "79.1%", not "0.7914";
- a verdict is a sentence, not an enum.

Nothing here invents data. Everything is a rendering of a value the engine emitted.
"""
from __future__ import annotations

# metric key -> (display name, what it means in one clause, unit)
_METRICS = {
    "revenue":     ("Revenue",     "money earned",                          "usd"),
    "ecpm":        ("eCPM",        "revenue per 1,000 impressions",         "usd"),
    "requests":    ("Ad requests", "times an ad was asked for",             "int"),
    "fill_rate":   ("Fill rate",   "share of requests that returned an ad", "rate"),
    "render_rate": ("Render rate", "share of filled ads that displayed",    "rate"),
    "ctr":         ("Click rate",  "share of impressions that were clicked", "rate"),
    "impressions": ("Impressions", "ads actually shown",                    "int"),
    "fills":       ("Fills",       "requests that returned an ad",          "int"),
    "clicks":      ("Clicks",      "clicks on shown ads",                   "int"),
}

# dimension key -> (noun for the value, template). {v} is the humanised value.
_DIMS = {
    "ad_format":      ("ad format",      "{v} ads"),
    "region":         ("region",         "in {v}"),
    "country":        ("country",        "in {v}"),
    "device_model":   ("device",         "on {v}"),
    "os_version":     ("OS version",     "on {v}"),
    "category":       ("app category",   "{v} apps"),
    "publisher_tier": ("publisher tier", "{v} publishers"),
    "ad_format×region": ("ad format × region", "{v}"),
    "vertical":       ("vertical",       "in {v}"),
    "campaign_type":  ("campaign type",  "{v} campaigns"),
}

# values that must not be title-cased or otherwise mangled
_KEEP = {"EU", "NAM", "APAC", "LATAM", "MEA", "iOS", "US", "UK", "CTR", "eCPM"}


def metric_name(metric: str) -> str:
    """`ecpm` -> `eCPM`. Unknown metrics come back readable, not raw."""
    m = _METRICS.get(str(metric or "").strip())
    return m[0] if m else str(metric or "?").replace("_", " ").strip().capitalize()


def metric_meaning(metric: str) -> str:
    """The one clause that makes the metric self-explanatory. '' when unknown."""
    m = _METRICS.get(str(metric or "").strip())
    return m[1] if m else ""


def metric_unit(metric: str) -> str:
    """usd | rate | int. Drives fmt_value so no panel guesses a format."""
    m = _METRICS.get(str(metric or "").strip())
    return m[2] if m else "num"


# the same idea arrives under several spellings across engine, fixtures and UI
_UNIT_ALIAS = {"": "num", "int": "int", "count": "int", "integer": "int", "num": "num",
               "ratio": "rate", "fraction": "rate", "rate": "rate",
               "usd": "usd", "dollar": "usd", "currency": "usd",
               "pct": "pct", "percent": "pct", "percentage": "pct",
               "score": "num", "number": "num"}


def fmt_value(value, unit: str = "num", digits: int | None = None) -> str:
    """Format ONE number in its unit. The fix for `0.7914` rendered as `0.7914`.

    `digits=None` means "enough to not lie": a value that would round to zero keeps
    rendering until it shows a real figure, so 0.04% never prints as "0.0%".
    """
    if value is None or value == "":
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)                    # pre-formatted strings pass through
    if v != v or v in (float("inf"), float("-inf")):
        return "—"
    u = _UNIT_ALIAS.get(str(unit or "").strip().lower(), "num")
    if u == "usd":
        return _no_fake_zero(v, "$", "", 2, digits)
    if u == "rate":                          # engine emits rates as fractions
        return _no_fake_zero(v * 100, "", "%", 1, digits)
    if u == "int":
        return f"{v:,.0f}"
    if u == "pct":                           # already a percentage number
        return _no_fake_zero(v, "", "%", 1, digits)
    return f"{v:,.4g}"


def _no_fake_zero(v: float, pre: str, suf: str, base: int, digits: int | None) -> str:
    """Render v, adding decimals until a non-zero value stops looking like zero.

    Printing 0.04% as "0.0%" tells the reader the number IS zero. It isn't.
    """
    sign, a = ("-" if v < 0 else ""), abs(v)   # sign goes OUTSIDE the $ — not "$-0.50"
    if digits is not None:
        return f"{sign}{pre}{a:,.{digits}f}{suf}"
    d = base
    while a != 0 and round(a, d) == 0 and d < 6:
        d += 1
    # one more place buys a SECOND significant digit: 0.0023 -> "0.0023", not "0.002".
    # A single significant digit can still misstate a small value by ~15%.
    if base < d < 6 and round(a, d) != a:
        d += 1
    return f"{sign}{pre}{a:,.{d}f}{suf}"


def fmt_delta(pct, digits: int | None = 1) -> str:
    """Signed percentage move, always with its sign so direction is unmissable.

    Signed zero is normalised: `-0.0%` reads as a typo, not as "no change".
    """
    try:
        v = float(pct)
    except (TypeError, ValueError):
        return "—"
    if v != v or v in (float("inf"), float("-inf")):
        return "—"
    if v == 0:
        return "0.0%" if digits is None else f"{0:.{digits}f}%"
    d = 1 if digits is None else digits
    while round(v, d) == 0 and d < 6:        # keep a real move from printing "+0.0%"
        d += 1
    return f"{v:+,.{d}f}%"


def _value_word(raw: str) -> str:
    v = str(raw).strip()
    if v in _KEEP:
        return v
    if v.upper() in _KEEP:
        return v.upper()
    # underscores FIRST: "tier_2" contains a digit, so the digit branch below would
    # return it untouched and render "tier_2 publishers"
    if "_" in v:                             # tier_3 -> Tier 3
        return v.replace("_", " ").strip().capitalize()
    if any(ch.isdigit() for ch in v):        # "Android 15", "iOS 18.1" — leave alone
        return v
    return v.capitalize()


def _pairs(segment: str) -> list[tuple[str, str]]:
    """`ad_format=native × region=EU` -> [(ad_format, native), (region, EU)]."""
    out: list[tuple[str, str]] = []
    for part in str(segment or "").replace("∩", "×").split("×"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out.append((k.strip(), v.strip()))
        else:
            out.append(("", part))
    return out


def segment_phrase(dimension: str = "", segment: str = "") -> str:
    """A segment as a readable phrase.

    `ad_format=native × region=EU` -> `Native ads in EU`
    `os_version=Android 15`        -> `Android 15 devices`
    Falls back to the raw string rather than losing information.
    """
    pairs = _pairs(segment)
    if not pairs:
        return str(segment or dimension or "—")
    if len(pairs) == 1 and not pairs[0][0]:
        # bare value with the dimension supplied separately
        return segment_phrase(dimension, f"{dimension}={pairs[0][1]}") if dimension else pairs[0][1]
    parts: list[str] = []
    for key, val in pairs:
        word = _value_word(val)
        spec = _DIMS.get(key)
        if spec is None:
            parts.append(f"{key.replace('_', ' ')} {word}".strip() if key else word)
            continue
        rendered = spec[1].format(v=word)
        # "on Android 15" reads better trailing; keep template order as written
        parts.append(rendered)
    # join: first part is the subject, the rest qualify it -> "Native ads in EU"
    head, tail = parts[0], parts[1:]
    return " ".join([head, *tail]).strip()


def dimension_name(dimension: str) -> str:
    """`ad_format×region` -> `ad format × region`, for 'we looked at ...' copy."""
    d = str(dimension or "").strip()
    spec = _DIMS.get(d)
    if spec:
        return spec[0]
    return " × ".join(p.replace("_", " ") for p in d.split("×")) if d else ""


# verdict -> (short label, the sentence a non-expert needs)
_VERDICTS = {
    "LOCALIZED_1D": ("Traced to one segment",
                     "The move is concentrated in a single segment, not spread across the business."),
    "LOCALIZED_2D": ("Traced to a combination",
                     "The move only shows up where two things overlap — neither one alone explains it."),
    "GLOBAL_UNLOCALIZED": ("No single segment to blame",
                           "Every segment moved together, so naming one would be wrong. "
                           "The cause is upstream of any single slice."),
    "INCONCLUSIVE": ("Not enough evidence",
                     "The data does not support naming a cause with confidence."),
    "NORMAL": ("Within normal range",
               "The movement stays inside the expected band for this metric."),
}


def verdict_label(verdict: str) -> str:
    """'' for an absent verdict — a caller can suppress a chip, but cannot un-render
    a literal '?' once it is on screen."""
    key = str(verdict or "").strip()
    if not key:
        return ""
    v = _VERDICTS.get(key)
    return v[0] if v else key.replace("_", " ").capitalize()


def verdict_sentence(verdict: str) -> str:
    v = _VERDICTS.get(str(verdict or "").strip())
    return v[1] if v else ""


# engine factor verdict -> how to say it about a FUNNEL FACTOR
_FACTOR_VERDICT = {
    "driver": ("primary", "This is what moved."),
    "primary_driver": ("primary", "This is what moved."),
    "contributing": ("contributing", "Moved too, but it is not the main cause."),
    "normal → ruled out": ("ruled out", "Checked and normal — not the cause."),
    "ruled out": ("ruled out", "Checked and normal — not the cause."),
    "context (not a CPM revenue factor)": ("context",
                                           "Tracked for context; it does not affect revenue here."),
}


def factor_verdict(verdict: str) -> tuple[str, str]:
    """(short tag, explaining sentence) for a decomposition factor.

    Producers disagree on spelling — the engine says `normal → ruled out`, the golden
    fixture says `ruled_out`. Retry with underscores as spaces rather than falling
    through to the raw token.
    """
    key = str(verdict or "").strip()
    hit = _FACTOR_VERDICT.get(key) or _FACTOR_VERDICT.get(key.replace("_", " ").lower())
    return hit or (key or "—", "")


def segment_in(dimension: str = "", segment: str = "") -> str:
    """`segment_phrase` with any leading preposition stripped, for callers that
    supply their own ("in {x}"). Without this you get "in on Android 15"."""
    p = segment_phrase(dimension, segment)
    for lead in ("in ", "on ", "for "):
        if p.lower().startswith(lead):
            return p[len(lead):]
    return p


def where_phrase(culprit: dict | None, verdict: str = "") -> str:
    """The WHERE answer, including the no-culprit case.

    A global incident has no segment; that is a real answer, not a blank.
    """
    c = culprit or {}
    if c.get("dimension") or c.get("value"):
        return segment_phrase(c.get("dimension", ""), c.get("value", ""))
    if str(verdict or "").strip() == "GLOBAL_UNLOCALIZED":
        return "across every segment"
    return "—"


def direction_word(pct, metric: str = "") -> str:
    """'fell' / 'rose' / 'held steady' — so prose never says 'moved -30%'.

    Exactly zero is its own case: `0 < 0` is false, so a naive two-way test calls a
    flat metric a rise.
    """
    try:
        v = float(pct)
    except (TypeError, ValueError):
        return "moved"
    if v == 0:
        return "held steady"
    return "fell" if v < 0 else "rose"


def demo() -> None:
    """Self-check: the transforms that the whole RCA read-out depends on."""
    assert metric_name("ecpm") == "eCPM"
    assert metric_name("fill_rate") == "Fill rate"
    assert metric_meaning("ecpm") == "revenue per 1,000 impressions"
    assert metric_unit("fill_rate") == "rate"

    assert fmt_value(0.7914, "rate") == "79.1%"
    assert fmt_value(2.9257, "usd") == "$2.93"
    assert fmt_value(17663.6667, "int") == "17,664"
    assert fmt_value(None, "usd") == "—"
    assert fmt_delta(-30.6) == "-30.6%"
    assert fmt_delta(23.5) == "+23.5%"

    assert segment_phrase("ad_format×region", "ad_format=native × region=EU") == "Native ads in EU"
    assert segment_phrase("category", "category=finance") == "Finance apps"
    assert segment_phrase("os_version", "os_version=Android 15") == "on Android 15"
    assert segment_phrase("publisher_tier", "publisher_tier=tier_2") == "Tier 2 publishers"
    assert segment_phrase("", "") == "—"

    assert verdict_label("GLOBAL_UNLOCALIZED") == "No single segment to blame"
    assert verdict_label("") == "", "absent verdict must be suppressible, not '?'"
    assert factor_verdict("normal → ruled out")[0] == "ruled out"
    assert factor_verdict("ruled_out")[0] == "ruled out", "fixture spelling"
    assert factor_verdict("")[0] == "—"

    # unit aliases the engine and the fixtures actually emit
    assert fmt_value(0.7914, "ratio") == "79.1%"
    assert fmt_value(17663.0, "count") == "17,663"
    assert fmt_value(3.5, "") == "3.5"
    # a real number must never render as a fake zero
    assert fmt_value(0.04, "pct") == "0.04%", fmt_value(0.04, "pct")
    assert fmt_value(-0.0023, "usd") == "-$0.0023", fmt_value(-0.0023, "usd")
    assert fmt_value(-12.5, "usd") == "-$12.50", "sign belongs outside the currency mark"
    assert fmt_value(float("nan"), "usd") == "—"
    assert fmt_delta(-0.0) == "0.0%", "signed zero reads as a typo"
    assert fmt_delta(0.02) == "+0.02%", fmt_delta(0.02)

    # composable segment phrasing — segment_phrase already carries a preposition
    assert segment_in("os_version", "os_version=Android 15") == "Android 15"
    assert where_phrase(None, "GLOBAL_UNLOCALIZED") == "across every segment"
    assert where_phrase({"dimension": "category", "value": "category=finance"}) == "Finance apps"
    assert where_phrase(None) == "—"
    assert direction_word(-1) == "fell"
    assert direction_word(4.2) == "rose"
    assert direction_word(0) == "held steady"      # `0 < 0` is false — must not say "rose"
    assert direction_word(None) == "moved"
    print("explain.py OK")


if __name__ == "__main__":
    demo()
