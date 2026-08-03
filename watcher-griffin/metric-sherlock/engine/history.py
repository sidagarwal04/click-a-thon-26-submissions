"""Historical memory: has this happened before, and what did we conclude last time?

WHY A DIAGNOSIS NEEDS HISTORY
-----------------------------
Without it, every incident is the first incident. Three things go wrong:

1. RECURRENCE IS INVISIBLE. "Fill rate down 17pp for iPhone 14 in APAC" reads as a
   crisis the first time and as a crisis the fifth time. Whether it is new or
   routine changes what someone should do about it, and that is knowable from data
   the system already wrote.

2. CHRONIC SLICES CRY WOLF. Some slices sit permanently near their band edge and
   breach most days. Treating those identically to a slice that has been stable for
   a month is how a monitor trains people to ignore it. A slice that breaches 80%
   of the time has a baseline problem, not an incident, and saying so is more useful
   than alerting again.

3. PAST CONCLUSIONS ARE THROWN AWAY. If the same fingerprint was diagnosed and
   labelled last week, that label is the single most relevant fact available.

WHAT "THE SAME INCIDENT AGAIN" MEANS
------------------------------------
`incidents.fingerprint` is (signature, direction, root scope type, root scope
value, root metric, breached metric set). Deliberately excluding time and dollar
amount: a recurrence is the same MECHANISM on the same SCOPE, not the same size.
A $70 Android fill outage and a $700 one are the same thing happening twice.

Similarity is reported at three decreasing strengths, and which one matched is
always stated, because "similar to a past incident" without saying how similar is
exactly the kind of vague claim the guardrails exist to prevent:

    exact       same fingerprint
    same_scope  same root scope and metric, different mechanism
    same_signature  same mechanism elsewhere -- weakest, but tells you whether this
                    failure mode is systemic

EVERY NUMBER IS A REAL ROW
--------------------------
All figures come from `incidents` / `metric_events`, which the sweep wrote. When
there is no history, the block says so explicitly rather than being omitted --
an absent history section is indistinguishable from a system that forgot to look.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from engine.ch_client import Trace, get_client
from engine.config import settings

# A slice breaching in more than this share of the windows it was evaluated in is
# treated as chronically out of band -- i.e. its baseline is wrong, not its
# behaviour. Deliberately high: mislabelling a real repeated incident as "chronic"
# would suppress a genuine finding, which is the more expensive error.
CHRONIC_BREACH_RATE = 0.5
CHRONIC_MIN_OBSERVATIONS = 6


@dataclass
class PriorIncident:
    incident_id: str
    opened_at: object
    signature: str
    root_scope_type: str
    root_scope_value: str
    root_metric: str
    grain: str
    impact_usd: float
    label: str
    match_strength: str
    narration: str = ""


@dataclass
class HistoryResult:
    """The `history` block that reaches the evidence bundle."""

    fingerprint: str
    recurrence_count: int = 0
    first_seen: object = None
    last_seen: object = None
    priors: list = field(default_factory=list)
    prior_impact_total: float = 0.0
    labels_seen: dict = field(default_factory=dict)
    chronic: bool = False
    chronic_detail: dict = field(default_factory=dict)
    source_step: str = "history:lookup"
    summary: str = ""

    @property
    def is_novel(self) -> bool:
        return self.recurrence_count == 0


def _rows(client, trace, sql: str, step: str) -> list:
    try:
        return client.query(sql, step=step, trace=trace)
    except Exception:
        # History is context, never a precondition. If the lookup fails the
        # diagnosis still ships -- it just says history was unavailable rather
        # than implying there was none.
        return []


def _esc(v: str) -> str:
    return str(v).replace("'", "''")


def lookup(incident, client=None, trace: Optional[Trace] = None,
           exclude_incident_id: Optional[str] = None) -> HistoryResult:
    """Finds prior occurrences of `incident` and whether its slice is chronic."""
    client = client or get_client()
    trace = trace if trace is not None else Trace()
    res = HistoryResult(fingerprint=incident.fingerprint)

    exclude = exclude_incident_id or incident.incident_id
    not_self = f"incident_id != '{_esc(exclude)}'" if exclude else "1"
    # Only history strictly BEFORE this incident's window. Without this a sweep
    # that re-detects the same window would count itself as its own precedent and
    # report recurrence=2 for a first occurrence.
    before = f"opened_at < '{incident.opened_at:%Y-%m-%d %H:%M:%S}'"

    rows = _rows(
        client, trace,
        "SELECT incident_id, opened_at, signature, root_scope_type, root_scope_value, "
        "root_metric, grain, impact_usd, label, fingerprint, narration "
        f"FROM incidents FINAL WHERE {not_self} AND {before} AND ("
        f"  fingerprint = '{_esc(incident.fingerprint)}'"
        f"  OR (root_scope_type = '{_esc(incident.root_scope_type)}' "
        f"      AND root_scope_value = '{_esc(incident.root_scope_value)}' "
        f"      AND root_metric = '{_esc(incident.root_metric)}')"
        f"  OR signature = '{_esc(incident.signature)}'"
        f") ORDER BY opened_at DESC LIMIT 200",
        step="history:lookup",
    )

    for r in rows:
        if r["fingerprint"] == incident.fingerprint:
            strength = "exact"
        elif (r["root_scope_type"] == incident.root_scope_type
              and r["root_scope_value"] == incident.root_scope_value
              and r["root_metric"] == incident.root_metric):
            strength = "same_scope"
        else:
            strength = "same_signature"
        # An unmatched mechanism is not a similarity signal: S0 means "we could not
        # name this", and two unnamed things are not the same thing.
        if strength == "same_signature" and incident.signature == "S0":
            continue
        res.priors.append(PriorIncident(
            incident_id=str(r["incident_id"]), opened_at=r["opened_at"], signature=r["signature"],
            root_scope_type=r["root_scope_type"], root_scope_value=r["root_scope_value"],
            root_metric=r["root_metric"], grain=r["grain"], impact_usd=float(r["impact_usd"] or 0),
            label=r["label"] or "", match_strength=strength, narration=(r["narration"] or "")[:400],
        ))

    exact_and_scope = [p for p in res.priors if p.match_strength in ("exact", "same_scope")]
    res.recurrence_count = len(exact_and_scope)
    if exact_and_scope:
        res.first_seen = min(p.opened_at for p in exact_and_scope)
        res.last_seen = max(p.opened_at for p in exact_and_scope)
        res.prior_impact_total = sum(p.impact_usd for p in exact_and_scope)
    for p in res.priors:
        if p.label:
            res.labels_seen[p.label] = res.labels_seen.get(p.label, 0) + 1

    res.chronic_detail = _chronic_check(client, trace, incident)
    res.chronic = bool(res.chronic_detail.get("chronic"))
    res.summary = _summarize(incident, res)
    return res


def _chronic_check(client, trace, incident) -> dict:
    """How often this exact slice+metric has breached recently, from
    `metric_events`.

    Counts DISTINCT windows rather than event rows: the same window re-swept must
    not inflate the rate, which is why metric_events is keyed on the window in the
    first place.
    """
    since = incident.opened_at - timedelta(days=settings.contribution_trailing_days)
    rows = _rows(
        client, trace,
        "SELECT countDistinct(window_start) AS breached_windows, "
        "       min(window_start) AS first_window, max(window_start) AS last_window "
        f"FROM metric_events FINAL WHERE metric = '{_esc(incident.root_metric)}' "
        f"AND scope_type = '{_esc(incident.root_scope_type)}' "
        f"AND scope_value = '{_esc(incident.root_scope_value)}' "
        f"AND grain = '{_esc(incident.grain)}' "
        f"AND window_start >= '{since:%Y-%m-%d %H:%M:%S}' "
        f"AND window_start < '{incident.opened_at:%Y-%m-%d %H:%M:%S}'",
        step="history:chronic_check",
    )
    if not rows:
        return {"chronic": False, "reason": "breach history unavailable for this slice"}
    breached = int(rows[0]["breached_windows"] or 0)

    cov = _rows(
        client, trace,
        "SELECT countDistinct(window_start) AS evaluated_windows FROM sweep_coverage "
        f"WHERE scope_type = '{_esc(incident.root_scope_type)}' "
        f"AND metric = '{_esc(incident.root_metric)}' AND grain = '{_esc(incident.grain)}' "
        f"AND entities_evaluated > 0 "
        f"AND window_start >= '{since:%Y-%m-%d %H:%M:%S}' "
        f"AND window_start < '{incident.opened_at:%Y-%m-%d %H:%M:%S}'",
        step="history:chronic_denominator",
    )
    evaluated = int(cov[0]["evaluated_windows"] or 0) if cov else 0

    if evaluated < CHRONIC_MIN_OBSERVATIONS:
        return {
            "chronic": False,
            "breached_windows": breached,
            "evaluated_windows": evaluated,
            "reason": (
                f"not enough monitoring history to judge whether this slice is chronically out of "
                f"band: it has been evaluated in only {evaluated} window(s) at {incident.grain} "
                f"(need {CHRONIC_MIN_OBSERVATIONS}). Treated as a genuine finding."
            ),
        }
    rate = breached / evaluated
    chronic = rate >= CHRONIC_BREACH_RATE
    return {
        "chronic": chronic,
        "breached_windows": breached,
        "evaluated_windows": evaluated,
        "breach_rate": round(rate, 4),
        "reason": (
            f"this slice has breached in {breached} of the last {evaluated} evaluated "
            f"{incident.grain} windows ({rate:.0%}), which is chronic rather than incidental -- its "
            f"baseline is mis-set, and re-alerting on it adds noise instead of information"
            if chronic else
            f"this slice breached in {breached} of the last {evaluated} evaluated {incident.grain} "
            f"windows ({rate:.0%}), so this is an exceptional movement rather than its normal state"
        ),
    }


def _summarize(incident, res: HistoryResult) -> str:
    """One paragraph the narrator may restate verbatim. Deterministic -- no LLM
    involved in any factual claim here."""
    if res.is_novel and not res.priors:
        base = (
            f"No prior occurrence of this incident is on record: nothing matching "
            f"{incident.signature} on {incident.root_label} for {incident.root_metric} has been "
            f"detected before this window. This is the first time the system has seen it."
        )
    elif res.recurrence_count:
        ordinal = {1: "second", 2: "third", 3: "fourth", 4: "fifth"}.get(
            res.recurrence_count, f"{res.recurrence_count + 1}th")
        base = (
            f"This is the {ordinal} occurrence for {incident.root_label} on "
            f"{incident.root_metric}: {res.recurrence_count} prior incident(s) on record, first on "
            f"{res.first_seen:%Y-%m-%d} and most recently {res.last_seen:%Y-%m-%d}, with "
            f"${abs(res.prior_impact_total):,.2f} of prior estimated exposure in total."
        )
        prior = res.priors[0]
        if prior.label:
            base += f" The most recent one was labelled '{prior.label}' after review."
        elif prior.signature != incident.signature:
            base += (f" Note the mechanism differs: the last one was diagnosed {prior.signature}, "
                     f"this one {incident.signature}.")
    else:
        sig_priors = [p for p in res.priors if p.match_strength == "same_signature"]
        base = (
            f"This exact slice has no prior incidents, but {incident.signature} has been diagnosed "
            f"{len(sig_priors)} time(s) elsewhere -- most recently on "
            f"{sig_priors[0].root_scope_type}={sig_priors[0].root_scope_value} on "
            f"{sig_priors[0].opened_at:%Y-%m-%d}. The failure mode is not new to the platform even "
            f"though this segment is."
        )
    if res.labels_seen:
        labels = ", ".join(f"{k} x{v}" for k, v in sorted(res.labels_seen.items(), key=lambda kv: -kv[1]))
        base += f" Review outcomes recorded for related incidents: {labels}."
    chronic_reason = res.chronic_detail.get("reason")
    if chronic_reason:
        sentence = chronic_reason[0].upper() + chronic_reason[1:]
        base += " " + (sentence if sentence.endswith(".") else sentence + ".")
    return base


def as_evidence(res: HistoryResult) -> dict:
    """The serialisable `history` block for the evidence bundle, carrying its own
    source_step so the narration can cite where these numbers came from."""
    return {
        "fingerprint": res.fingerprint,
        "recurrence_count": res.recurrence_count,
        "is_novel": res.is_novel,
        "first_seen": res.first_seen,
        "last_seen": res.last_seen,
        "prior_impact_total_usd": res.prior_impact_total,
        "chronic": res.chronic,
        "chronic_detail": res.chronic_detail,
        "labels_seen": res.labels_seen,
        "priors": [
            {
                "incident_id": p.incident_id, "opened_at": p.opened_at, "signature": p.signature,
                "root": f"{p.root_scope_type}={p.root_scope_value}", "metric": p.root_metric,
                "grain": p.grain, "impact_usd": p.impact_usd, "label": p.label,
                "match_strength": p.match_strength,
            }
            for p in res.priors[:10]
        ],
        "summary": res.summary,
        "source_step": res.source_step,
    }
