"""Evidence score: a single 0-100 index over how many corroborating checks an
incident passed.

READ THIS BEFORE CHANGING ANYTHING HERE
---------------------------------------
This is the most heavily blended number the system displays -- six weighted
components over inputs from four different tables.

An earlier version of this note claimed it was "the ONLY number not directly
reproducible from one ClickHouse query", and that was wrong in a way worth
correcting rather than quietly deleting: `impact_usd` is
(expected - actual) x an observed rate, `breadth` is breached/evaluated, and
`deviation_score` is (value - centre)/spread. Those are Python arithmetic over
queried inputs too. Nothing about them is fabricated -- every input is logged and
every formula is in code -- but the sentence as written would not survive a
reviewer who checked it, and it understated how much of the screen needs the
treatment this file pioneered.

`engine/provenance.py` now generalises exactly that treatment to every figure:
each number is classed `measured` (one query returns it), `derived` (published
formula plus its input queries) or `config` (a constant, with its settings path).
This score is `derived`, and so is the dollar impact; the difference is degree,
not kind.

The problem statement is explicit that a single fabricated figure costs more than
a missed anomaly. So this is built under three hard constraints, and all three are
load-bearing:

1. THE FORMULA IS PUBLISHED AND FIXED. `FORMULA_TEXT` below is rendered in the UI
   next to the score. The weights are constants in this file. They are not tuned
   per incident, not learned, and not adjusted to make any particular incident look
   better.

2. EVERY INPUT IS INDIVIDUALLY TRACEABLE. Each component records the raw value it
   read and where it came from, and the UI renders that breakdown beneath the bar.
   A reader can therefore check each input against the evidence and re-add the
   points by hand.

3. IT IS AN EVIDENCE SCORE, NEVER A PROBABILITY. It must not be worded as "82%
   likely to be correct" or "82% confident". It answers "how much corroboration
   does this finding have?", not "how likely is it true?". Those are different
   claims and only the first one is supported.

WHY THE SCORE MUST BE ABLE TO GO DOWN
-------------------------------------
A score that only rises with more evidence is decoration. The corroboration
component is deliberately signed: a CHRONIC slice -- one that breaches in most
windows it is evaluated in -- scores negative, because a slice that is always out
of band has a mis-set baseline rather than an incident. That is evidence against
the finding, and the number has to be able to say so.
"""

from dataclasses import dataclass, field
from typing import Optional

from engine.config import settings

# --- weights (must sum to MAX_SCORE for the positive components) -------------
W_PERSISTENCE = 20
W_ROBUSTNESS = 20
W_DEVIATION = 20
W_SEASONALITY = 15
W_MECHANISM = 15
W_CORROBORATION = 10
MAX_SCORE = 100

# Label bands. Stated in the UI so the word and the number cannot drift apart.
LABEL_BANDS = ((75, "strong"), (50, "moderate"), (25, "weak"), (0, "very weak"))

# The FULL formula, including every sub-weight and partial-credit multiplier.
#
# The previous version listed only the six top-level weights, while the header above and the
# UI both claimed the total could be re-added by hand. It could not: the method points, the
# 12/8 split inside band robustness, the kink at the amber threshold, the sample-count target
# and the three partial-credit fractions were all undisclosed. A published formula that omits
# half its terms is a stronger claim than the code supports, which is exactly the kind of
# overstatement this file exists to avoid. Everything is stated now.
FORMULA_TEXT = (
    "Evidence score, out of 100, is the sum of six components; a reader can re-add it from the "
    "per-component values shown beneath. "
    "(1) Persistence, max 20: min(1, consecutive_windows / required) x 20. "
    "(2) Band robustness, max 20: method points + sample points. Method points are 12 for "
    "median+MAD, 6 when MAD was zero and it fell back to standard deviation, 3 for a "
    "never-varying history, 0 for no usable band. Sample points are min(1, n / (2 x "
    "min_samples)) x 8, so full credit needs twice the minimum sample count. "
    "(3) Deviation size, max 20: 20 at or beyond the red threshold; between amber and red it "
    "scales 12 to 20; below amber it is 12 x (score / amber). "
    "(4) Seasonality disproof, max 15: 15 when the sibling test ran and the segment was "
    "isolated, 3 when it ran and the siblings moved together, 6 when the test could not be run "
    "at all. "
    "(5) Mechanism match, max 15: the rule table's own confidence x 15, so an unmatched "
    "mechanism scores 0. "
    "(6) Corroboration, -10 to +10: +10 for a prior occurrence of the same fingerprint, +4 for "
    "a first occurrence, and MINUS 10 when the slice is chronically out of band, because that "
    "indicates a mis-set baseline rather than an incident. "
    "The total is clamped to 0-100. Labels: 75+ strong, 50+ moderate, 25+ weak, below 25 very "
    "weak. This is an index over corroborating checks, not a probability."
)

# Sub-weights inside band robustness: HOW the band was built, and how much history
# stood behind it. Split because a robust method on thin history and a weak method
# on deep history are different situations and should not score identically.
_METHOD_POINTS = {
    "median_mad": 12,            # robust to outliers -- the default, best case
    "mean_sigma_fallback": 6,    # MAD was 0, fell back to stdev; usable but not robust
    "constant_history": 3,       # the metric never varied; a move is real but unscaled
    "insufficient": 0,           # no band at all -- nothing may be concluded
}
_MAX_METHOD_POINTS = 12
_MAX_SAMPLE_POINTS = W_ROBUSTNESS - _MAX_METHOD_POINTS  # 8


@dataclass
class ScoreComponent:
    """One line of the breakdown. `raw` is what was read; `points` is what it earned."""

    name: str
    points: float
    max_points: float
    raw: str          # the actual value(s) read, for hand-checking
    reason: str       # why those points
    source: str = ""  # where the input came from

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "points": round(self.points, 1),
            "max_points": self.max_points,
            "raw": self.raw,
            "reason": self.reason,
            "source": self.source,
        }


@dataclass
class EvidenceScore:
    score: int
    label: str
    components: list = field(default_factory=list)
    formula: str = FORMULA_TEXT
    caveat: str = (
        "This is the one figure on screen that is a weighted blend rather than a direct "
        "query result. The formula is fixed and published, and every input below is "
        "traceable, so the total can be re-added by hand. It measures corroboration, "
        "not probability of correctness."
    )

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "label": self.label,
            "formula": self.formula,
            "caveat": self.caveat,
            "components": [c.as_dict() for c in self.components],
            "components_sum": round(sum(c.points for c in self.components), 1),
        }


def _label_for(score: int) -> str:
    for threshold, label in LABEL_BANDS:
        if score >= threshold:
            return label
    return LABEL_BANDS[-1][1]


def _persistence(incident) -> ScoreComponent:
    required = max(1, settings.consecutive_points_required)
    got = max((getattr(m, "consecutive_points", 1) for m in incident.members), default=1)
    points = min(1.0, got / required) * W_PERSISTENCE
    return ScoreComponent(
        name="Persistence",
        points=points,
        max_points=W_PERSISTENCE,
        raw=f"{got} consecutive {incident.grain} window(s), {required} required",
        reason=(
            f"the breach held for {got} consecutive window(s), so it is not a single-bucket blip"
            if got >= required else
            f"the breach was seen in {got} window(s) but {required} are required to confirm it"
        ),
        source="metric_events.consecutive_points",
    )


def _robustness(incident) -> ScoreComponent:
    root = _root_member(incident)
    method = getattr(root, "method", "insufficient") if root else "insufficient"
    n = int(getattr(root, "sample_count", 0) or 0) if root else 0
    method_pts = _METHOD_POINTS.get(method, 0)
    # Full sample credit at twice the minimum -- enough history that the median and
    # MAD are not being carried by a handful of points.
    target_n = max(2, settings.band_min_samples * 2)
    sample_pts = min(1.0, n / target_n) * _MAX_SAMPLE_POINTS
    return ScoreComponent(
        name="Band robustness",
        points=method_pts + sample_pts,
        max_points=W_ROBUSTNESS,
        raw=f"method={method}, n={n} comparable windows (full credit at n>={target_n})",
        reason=(
            f"the band was built with {method}"
            + (" (robust to outliers, so past incidents do not widen it)" if method == "median_mad"
               else " (MAD was zero, so scale fell back to standard deviation)" if method == "mean_sigma_fallback"
               else " (the metric never varied historically, so the move is real but has no scale)"
               if method == "constant_history"
               else " -- no usable band, so nothing can be concluded from it")
            + f", from {n} comparable historical window(s)"
        ),
        source="baselines.method / baselines.sample_count",
    )


def _deviation(incident) -> ScoreComponent:
    root = _root_member(incident)
    score = abs(getattr(root, "deviation_score", 0.0)) if root else 0.0
    amber, red = settings.band_k_amber, settings.band_k_red
    if score >= red:
        points = W_DEVIATION
    elif score >= amber and red > amber:
        points = 12 + 8 * (score - amber) / (red - amber)
    else:
        points = 12 * (score / amber) if amber else 0.0
    points = max(0.0, min(float(W_DEVIATION), points))
    return ScoreComponent(
        name="Deviation size",
        points=points,
        max_points=W_DEVIATION,
        raw=f"{score:.1f} band-widths from centre (amber at {amber}, red at {red})",
        reason=(
            f"the value sits {score:.1f} band-widths outside its expected range"
            + (" -- far beyond the red threshold" if score >= red else "")
        ),
        source="metric_events.deviation_score",
    )


def _seasonality(incident) -> ScoreComponent:
    s = incident.seasonality or {}
    if not s.get("tested"):
        return ScoreComponent(
            name="Seasonality disproof",
            points=W_SEASONALITY * 0.4,
            max_points=W_SEASONALITY,
            raw="independent sibling test not available",
            reason=(
                "seasonality is still controlled for by the same-weekday/same-hour baseline, but "
                "the independent sibling test could not run, so there is no second, "
                "baseline-free argument against a seasonal explanation"
            ),
            source="incidents.seasonality",
        )
    breached = s.get("siblings_breached", 0)
    evaluated = s.get("siblings_evaluated", 0)
    isolated = bool(s.get("isolated"))
    return ScoreComponent(
        name="Seasonality disproof",
        points=W_SEASONALITY if isolated else W_SEASONALITY * 0.2,
        max_points=W_SEASONALITY,
        raw=f"{breached} of {evaluated} sibling {incident.root_scope_type} value(s) also moved",
        reason=(
            f"only {breached} of {evaluated} values of this dimension moved, so it fell while its "
            f"siblings held -- seasonality acts on people, and people carry every device and OS, "
            f"so it cannot move one population and leave the rest flat"
            if isolated else
            f"{breached} of {evaluated} values moved together, which is the shape a population-wide "
            f"or seasonal effect would also produce -- the segment attribution is weaker here"
        ),
        source="incidents.seasonality",
    )


def _mechanism(incident) -> ScoreComponent:
    conf = float(incident.signature_confidence or 0.0)
    return ScoreComponent(
        name="Mechanism match",
        points=conf * W_MECHANISM,
        max_points=W_MECHANISM,
        raw=f"signature={incident.signature}, rule-table confidence={conf:.2f}",
        reason=(
            f"the spread fingerprint matched {incident.signature} in the deterministic rule table "
            f"at confidence {conf:.2f}"
            if incident.signature != "S0" else
            "the spread fingerprint matched no known mechanism, so the cause is reported as unknown "
            "rather than guessed -- the deviation and its segment are still established"
        ),
        source="incidents.signature / signature_confidence",
    )


def _corroboration(incident) -> ScoreComponent:
    h = incident.history or {}
    if not h.get("looked_up"):
        return ScoreComponent(
            name="Corroboration",
            points=0.0,
            max_points=W_CORROBORATION,
            raw="history not looked up",
            reason=h.get("reason", "history lookup was not performed for this incident"),
            source="incidents.history",
        )
    if h.get("chronic"):
        detail = h.get("chronic_detail") or {}
        return ScoreComponent(
            name="Corroboration",
            points=-float(W_CORROBORATION),
            max_points=W_CORROBORATION,
            raw=(f"chronic: breached {detail.get('breached_windows', '?')} of "
                 f"{detail.get('evaluated_windows', '?')} evaluated windows"),
            reason=(
                "this slice breaches in most windows it is evaluated in, which points at a mis-set "
                "baseline rather than an incident -- counted AGAINST the finding, not for it"
            ),
            source="incidents.history.chronic_detail",
        )
    recurrence = int(h.get("recurrence_count", 0) or 0)
    if recurrence > 0:
        return ScoreComponent(
            name="Corroboration",
            points=float(W_CORROBORATION),
            max_points=W_CORROBORATION,
            raw=f"{recurrence} prior occurrence(s) of the same fingerprint",
            reason=(
                f"the same mechanism on the same scope has been recorded {recurrence} time(s) "
                f"before, which corroborates this as a real, repeating failure mode"
            ),
            source="incidents.history.recurrence_count",
        )
    return ScoreComponent(
        name="Corroboration",
        points=W_CORROBORATION * 0.4,
        max_points=W_CORROBORATION,
        raw="first recorded occurrence",
        reason=(
            "no prior occurrence is on record. That is not evidence against the finding -- a first "
            "occurrence is still an occurrence -- so it scores partial rather than zero"
        ),
        source="incidents.history.recurrence_count",
    )


def _root_member(incident):
    """The member breach the incident is attributed to -- the one whose band and
    deviation the score should reflect."""
    for m in incident.members:
        if (m.metric == incident.root_metric
                and m.scope_type == incident.root_scope_type
                and m.scope_value == incident.root_scope_value
                and m.grain == incident.grain):
            return m
    return incident.members[0] if incident.members else None


def evidence_score(incident) -> EvidenceScore:
    """Scores one clustered Incident. Pure -- no I/O, no queries."""
    components = [
        _persistence(incident),
        _robustness(incident),
        _deviation(incident),
        _seasonality(incident),
        _mechanism(incident),
        _corroboration(incident),
    ]
    total = sum(c.points for c in components)
    score = int(round(max(0.0, min(float(MAX_SCORE), total))))
    return EvidenceScore(score=score, label=_label_for(score), components=components)


def attach_scores(incidents: list) -> None:
    """Attaches `evidence_score_detail` to each incident, best-effort.

    Never raises: a scoring failure must not lose the finding, which is the same
    rule persistence and narration follow.
    """
    for inc in incidents:
        try:
            inc.evidence_score_detail = evidence_score(inc).as_dict()
        except Exception as e:  # pragma: no cover -- defensive
            inc.evidence_score_detail = {
                "score": 0, "label": "unavailable", "formula": FORMULA_TEXT,
                "caveat": f"evidence score could not be computed: {e}", "components": [],
            }
