"""The diagnosis as one because-ladder, for a reader who is not an analyst.

WHY THIS EXISTS
The incident page already contains the whole argument, but it is spread across seven
charts and tables, and assembling it is left to the reader:

    revenue fell -> because fill rate fell -> because it is concentrated on Android
    -> and it is NOT concentrated by app, category or format, so the cause is upstream
    -> and only one of two OS families moved, so it is not seasonal
    -> which is the fingerprint of a demand-partner failure
    -> costing $24.42 a day

Every one of those steps is already computed and already persisted. What was missing is
the word "because" between them. Somebody fluent in band statistics can reconstruct the
chain from a spread-bar chart; somebody who owns the ad stack and has ninety seconds
cannot, and they are the person the diagnosis is for.

WHAT THIS MODULE MAY AND MAY NOT DO
It may ONLY re-order and re-word facts the incident already carries. It runs no query,
does no arithmetic, and adds no number. Every `numbers` value on every link is copied
from the incident dict by key, and `_num()` is the only way a figure gets in -- so a
field the incident does not have becomes an omitted link, never an estimated one. That
is the same guardrail the narrator works under, applied to a deterministic renderer:
this is a re-presentation of the evidence, so if the chain and the charts could ever
disagree, the chain would be worthless.

Wording is derived from the data, not from the language model. The chain is therefore
available whether or not an LLM is reachable, which matters because it now carries the
top of the page.

CERTAINTY IS MARKED, NEVER IMPLIED
Each link states how strongly it is held:

    measured    a figure read from a band comparison
    ruled_out   an alternative that was tested and cleared, with its numbers
    derived     a deterministic rule-table conclusion over measured spread (the
                mechanism) -- sound, but a classification rather than an observation
    unknown     the check could not be run, or the pattern matched no known mechanism

`unknown` links are RENDERED, not dropped. A missing rung reads as a chain that never
had a gap in it, which is exactly the overstatement the rest of the system is built to
avoid.
"""

from dataclasses import asdict, dataclass, field
from typing import Optional

from engine.impact import ENGAGEMENT_ZERO_EXPOSURE_BASIS, ENGAGEMENT_ZERO_EXPOSURE_REASON

MEASURED = "measured"
RULED_OUT = "ruled_out"
DERIVED = "derived"
UNKNOWN = "unknown"

# Plain-language names. The incident stores column names; a reader should not have to
# know that `os_family` is a column or that `rpr` is revenue per request.
_SCOPE_WORDS = {
    "global": "everywhere", "region": "region", "country": "country",
    "device_model": "device model", "os_version": "OS version", "os_family": "OS",
    "ad_format": "ad format", "app": "app", "category": "app category",
    "publisher_tier": "publisher tier", "advertiser": "advertiser",
    "vertical": "advertiser vertical", "campaign_type": "campaign type",
    "geo_cell": "region and device", "os_family_region": "OS and region",
    "format_region": "ad format and region",
}

_METRIC_WORDS = {
    "requests": "ad requests", "fills": "fills", "fill_rate": "fill rate",
    "impressions": "impressions", "render_rate": "show rate", "clicks": "clicks",
    "ctr": "click-through rate", "revenue": "revenue", "ecpm": "eCPM",
    "rpr": "revenue per request",
}

_OWNER_ACTIONS = {
    "demand": "the demand team — an advertiser or demand partner is not bidding",
    "supply": "the supply team — publisher or app inventory is behaving differently",
    "delivery": "the delivery team — something in serving or rendering changed",
    "pricing": "the pricing team — floors or bid values moved",
}


def scope_word(scope_type: str) -> str:
    return _SCOPE_WORDS.get(scope_type, (scope_type or "").replace("_", " "))


def metric_word(metric: str) -> str:
    return _METRIC_WORDS.get(metric, (metric or "").replace("_", " "))


@dataclass
class ChainLink:
    """One rung. `claim` is what to believe, `because` is why, `numbers` is the proof."""

    step: int
    title: str                                  # the short label, e.g. "What moved"
    claim: str                                  # plain English, no column names
    because: str = ""                           # the supporting reason
    numbers: dict = field(default_factory=dict)  # copied from the incident, never computed
    source_steps: list = field(default_factory=list)
    certainty: str = MEASURED


@dataclass
class CausalChain:
    incident_id: str
    links: list = field(default_factory=list)
    headline: str = ""
    # True when every rung is measured or ruled_out -- i.e. nothing in the chain rests on
    # an unmatched pattern or an untestable check. Surfaced so the UI can say so rather
    # than leaving the reader to audit the certainty markers themselves.
    complete: bool = False

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "headline": self.headline,
            "complete": self.complete,
            "links": [asdict(link) for link in self.links],
        }


def _num(src: dict, *keys) -> dict:
    """Copy named figures out of `src`, skipping any that are absent.

    The ONLY way a number reaches a link. An absent key produces an absent entry, so a
    chain can be short but never invented -- there is no code path here that computes,
    defaults or interpolates a value.
    """
    return {k: src[k] for k in keys if src.get(k) is not None}


def _find_ruled_out(incident: dict, prefix: str) -> list:
    return [r for r in (incident.get("ruled_out") or []) if str(r.get("check", "")).startswith(prefix)]


# ---------------------------------------------------------------------------
# The rungs
# ---------------------------------------------------------------------------
def _link_symptom(incident: dict, step: int) -> ChainLink:
    metric = metric_word(incident.get("root_metric", ""))
    value = incident.get("root_scope_value") or ""
    scope_type = incident.get("root_scope_type", "")
    direction = "higher than normal" if incident.get("direction") == "above" else "lower than normal"
    where = "across the whole platform" if scope_type == "global" or not value else f"for {value}"

    return ChainLink(
        step=step,
        title="What moved",
        claim=f"{metric.capitalize()} is {direction} {where}.",
        because=(
            f"Measured over a {incident.get('grain', '')} window against what this slice "
            f"normally does at the same hour and on the same weekday."
        ),
        numbers=_num(incident, "root_metric", "grain", "direction", "member_event_count"),
        certainty=MEASURED,
    )


def _link_factor(incident: dict, step: int) -> Optional[ChainLink]:
    """Which term of Revenue = Requests x Fill rate x Show rate x eCPM moved.

    Only present when the incident was investigated through the revenue identity, which
    is the minority of them. Omitted rather than guessed at otherwise.
    """
    evidence = incident.get("evidence") or {}
    primary = evidence.get("primary_factor")
    factors = evidence.get("factor_breakdown") or []
    if not primary or not factors:
        return None

    return ChainLink(
        step=step,
        title="Which part of the funnel",
        claim=f"The money moved through {metric_word(primary)}, not the other stages.",
        because=(
            "Revenue is requests × fill rate × show rate × eCPM, and that identity holds "
            "exactly — so the stage that moved is the stage that moved the money. The other "
            "three were checked and were within their normal range."
        ),
        numbers={"primary_factor": primary,
                 "factors": [f.get("factor") for f in factors if f.get("factor")]},
        source_steps=["decompose:revenue"],
        certainty=MEASURED,
    )


def _link_localisation(incident: dict, step: int) -> ChainLink:
    scope_type = incident.get("root_scope_type", "")
    value = incident.get("root_scope_value") or ""

    if scope_type == "global" or not value:
        return ChainLink(
            step=step,
            title="Where it is concentrated",
            claim="It is not concentrated anywhere — the whole platform moved together.",
            because=(
                "No single segment carried the deviation, so the cause is not one app, "
                "region, device or advertiser."
            ),
            numbers=_num(incident, "root_scope_type"),
            certainty=MEASURED,
        )

    return ChainLink(
        step=step,
        title="Where it is concentrated",
        claim=f"It is concentrated on one {scope_word(scope_type)}: {value}.",
        because=(
            f"Of everything measured, {value} is where the shortfall sits. Its siblings — the "
            f"other {scope_word(scope_type)} values — were measured at the same time and held."
        ),
        numbers=_num(incident, "root_scope_type", "root_scope_value", "member_event_count"),
        certainty=MEASURED,
    )


def _link_not_elsewhere(incident: dict, step: int) -> Optional[ChainLink]:
    """The localisation argument: which dimensions were UNIFORMLY affected.

    A dimension where everything moved together cannot be the cause -- it is the cause
    seen from another angle. This is the rung that turns "Android is worst" into
    "Android is responsible", and without it the chain would be a ranking, not a
    diagnosis.
    """
    checks = _find_ruled_out(incident, "dimension:")
    if not checks:
        return None

    # Three outcomes, not two, and the third is the one a two-way split gets wrong.
    #
    #   untouched  0 of N moved -- the strongest ruling-out there is. "0/170 breached
    #              across apps" is exactly how INC-0628 was shown not to be a supply
    #              problem, and calling it "concentrated" would invert its meaning.
    #   uniform    all N moved -- also ruled out, for the opposite reason: a dimension
    #              affected everywhere is the same problem seen from another angle, so
    #              the cause sits upstream of it.
    #   partial    some moved -- genuinely concentrated, and NOT a ruling-out.
    untouched, uniform, partial = [], [], []
    for c in checks:
        n = c.get("numbers") or {}
        breached, evaluated = n.get("breached"), n.get("evaluated")
        if breached is None or evaluated is None:
            continue
        label = f"{scope_word(str(c.get('check', '')).split(':', 1)[-1])} ({breached}/{evaluated})"
        if breached == 0:
            untouched.append(label)
        elif breached >= evaluated:
            uniform.append(label)
        else:
            partial.append(label)

    if not (untouched or uniform or partial):
        return None

    clauses, reasons = [], []
    if untouched:
        clauses.append(f"not {', '.join(untouched[:3])} — nothing there moved at all")
        reasons.append(
            "Where no value of a dimension moved, that dimension cannot be carrying the "
            "shortfall."
        )
    if uniform:
        clauses.append(f"not {', '.join(uniform[:3])} — everything there moved together")
        reasons.append(
            "Where every value moved equally, the dimension is not the cause — it is the "
            "same problem seen from another angle, so the cause sits upstream of it."
        )

    if clauses:
        claim = f"It is {'; and '.join(clauses)}."
    else:
        claim = f"Within {', '.join(partial[:3])} the shortfall is uneven."
        reasons.append(
            "Those dimensions were checked and neither cleared nor uniformly affected, so "
            "they narrow the cause without explaining it."
        )

    return ChainLink(
        step=step,
        title="Why not somewhere else",
        claim=claim,
        because=" ".join(reasons),
        numbers={"untouched": untouched, "uniformly_affected": uniform,
                 "partially_affected": partial},
        source_steps=sorted({s for c in checks for s in (c.get("source_steps") or [])}),
        # Only a ruling-out when something was actually cleared. A purely partial result
        # narrows the search; it does not eliminate anything, and marking it `ruled_out`
        # would overstate what the check achieved.
        certainty=RULED_OUT if (untouched or uniform) else MEASURED,
    )


def _link_seasonality(incident: dict, step: int) -> ChainLink:
    """The independent physical argument, kept separate from the baseline.

    The baselines are already same-weekday/same-hour matched, so seasonality is
    controlled for by construction -- but that requires trusting the baseline. The
    sibling test does not: seasonality acts on people, people carry every device and
    every OS, so a calendar effect has to move them all together.
    """
    season = incident.get("seasonality") or {}
    if not season.get("tested"):
        return ChainLink(
            step=step,
            title="Could it just be seasonality",
            claim="The independent seasonality check could not be run here.",
            because=(
                season.get("reason")
                or "There were not enough comparable siblings to test against."
            ) + " Seasonality is still controlled for by comparing against the same weekday "
                "and the same hour, but that check rests on the baseline rather than being "
                "independent of it.",
            numbers=_num(season, "siblings_breached", "siblings_evaluated", "breadth"),
            certainty=UNKNOWN,
        )

    isolated = bool(season.get("isolated"))
    scope_type = scope_word(incident.get("root_scope_type", ""))
    return ChainLink(
        step=step,
        title="Could it just be seasonality",
        claim=(
            "No. This is not a calendar effect." if isolated
            else "Possibly — the movement is broad enough that seasonality is not excluded."
        ),
        because=(
            f"Seasonality acts on people, and people carry every device and every OS. A quiet "
            f"weekend moves all of them together. Here only some {scope_type} values moved "
            f"while the rest held, and no calendar effect can do that."
            if isolated else
            f"Most {scope_type} values moved together, which is the pattern a calendar effect "
            f"would also produce, so this check does not separate the two."
        ),
        numbers=_num(season, "siblings_breached", "siblings_evaluated", "breadth", "isolated"),
        certainty=RULED_OUT if isolated else UNKNOWN,
    )


def _link_mechanism(incident: dict, step: int) -> ChainLink:
    signature = incident.get("signature") or "S0"
    owner = incident.get("owner") or ""
    confidence = incident.get("signature_confidence")

    if signature == "S0":
        return ChainLink(
            step=step,
            title="What this pattern means",
            claim="The pattern does not match any known failure mode.",
            because=(
                "The measurements above stand — what moved, where, and what was ruled out are "
                "all still measured facts. What is missing is a named mechanism: this "
                "combination of metric, scope and spread matched none of the rules, so the "
                "system will not assert a cause it cannot support. Someone should look at the "
                "evidence below directly."
            ),
            numbers=_num(incident, "signature", "signature_confidence"),
            certainty=UNKNOWN,
        )

    return ChainLink(
        step=step,
        title="What this pattern means",
        claim=incident.get("mechanism") or f"Matched failure mode {signature}.",
        because=(
            f"That conclusion comes from a fixed rule table over the measured spread — rule "
            f"{signature}, matched with confidence {confidence:.2f}. It is not the language "
            f"model's opinion; the same numbers always produce the same verdict."
            if confidence is not None else
            f"That conclusion comes from a fixed rule table over the measured spread (rule "
            f"{signature}), not from the language model."
        ) + (f" It belongs to {_OWNER_ACTIONS[owner]}." if owner in _OWNER_ACTIONS else ""),
        numbers=_num(incident, "signature", "signature_confidence", "owner"),
        certainty=DERIVED,
    )


def _link_cost(incident: dict, step: int) -> ChainLink:
    per_day = incident.get("impact_usd_per_day")
    total = incident.get("impact_usd")
    spanned = incident.get("windows_spanned") or 1
    grain = incident.get("grain", "")
    metric = incident.get("root_metric", "")

    # A click-rate move books $0, and the reason must be stated in the same words the
    # estimator used -- otherwise the chain and the impact block explain it differently.
    if metric in ("ctr", "clicks") and not per_day:
        return ChainLink(
            step=step,
            title="What it costs",
            claim="Nothing, in revenue terms.",
            because=ENGAGEMENT_ZERO_EXPOSURE_REASON,
            numbers={"impact_usd_per_day": 0.0, "basis": ENGAGEMENT_ZERO_EXPOSURE_BASIS},
            certainty=MEASURED,
        )

    if per_day is None:
        return ChainLink(
            step=step,
            title="What it costs",
            claim="No dollar exposure could be estimated for this incident.",
            because="The estimator had no observed revenue rate for this slice and window, "
                    "and a figure was not invented in its place.",
            numbers={},
            certainty=UNKNOWN,
        )

    # A negative figure is money ARRIVING. Saying "costing" there would invert the sign
    # in the only sentence most readers will take away from the page.
    verb = "gaining" if per_day < 0 else "costing"
    window_phrase = (
        f"{spanned} consecutive {grain} windows" if spanned > 1 else f"the {grain} window"
    )
    return ChainLink(
        step=step,
        title="What it costs",
        claim=f"It is {verb} about ${abs(per_day):,.2f} a day.",
        because=(
            f"Priced from the shortfall this slice actually shows against its own normal, "
            f"totalling ${abs(total):,.2f} over {window_phrase}."
            if total is not None else
            f"Priced from the shortfall this slice actually shows against its own normal."
        ),
        numbers=_num(incident, "impact_usd_per_day", "impact_usd", "windows_spanned", "grain"),
        certainty=MEASURED,
    )


def build_chain(incident: dict) -> CausalChain:
    """The incident's own evidence, re-ordered into the sequence a person asks it in.

    Links are numbered after assembly rather than at construction, so a rung that does
    not apply (no revenue decomposition, no partner dimensions) simply does not appear
    and the remaining numbering stays contiguous.
    """
    builders = [
        _link_symptom, _link_factor, _link_localisation,
        _link_not_elsewhere, _link_seasonality, _link_mechanism, _link_cost,
    ]
    links = []
    for build in builders:
        link = build(incident, 0)
        if link is not None:
            link.step = len(links) + 1
            links.append(link)

    chain = CausalChain(incident_id=str(incident.get("incident_id") or ""), links=links)
    chain.complete = all(link.certainty != UNKNOWN for link in links)

    metric = metric_word(incident.get("root_metric", ""))
    value = incident.get("root_scope_value") or "the platform overall"
    per_day = incident.get("impact_usd_per_day")
    chain.headline = (
        f"{metric.capitalize()} moved for {value}"
        + (f", costing about ${abs(per_day):,.2f} a day" if per_day else "")
        + "."
    )
    return chain
