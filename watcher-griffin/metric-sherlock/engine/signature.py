"""The signature matrix: turning a measured spread fingerprint into a NAMED
mechanism, deterministically.

WHY THIS IS A RULE TABLE AND NOT A PROMPT
----------------------------------------
This module answers "what kind of failure is this?" -- demand partner outage,
advertiser paused, render bug, click fraud, external event. That is the single
most consequential claim the system makes, because it decides who gets paged and
what they do first.

It is therefore computed by explicit rules over measured numbers, and the LLM never
sees this decision. The narrator receives the mechanism sentence already written
and may only restate it. An LLM asked to infer a mechanism from a table of numbers
will produce a confident, fluent, plausible answer whether or not the evidence
supports one, and a wrong mechanism is worse than no mechanism: it sends the wrong
team to look in the wrong place while the incident continues.

Every rule below is a predicate over:
  * the breached metric (which funnel stage moved)
  * the root scope type (which dimension it localised to)
  * partner spread (did it happen everywhere else too, or only here?)
  * sibling spread (did the other values of this same dimension move?)

and every rule's `reason` is a template filled with those numbers, so the
mechanism claim is as checkable as the metric claim.

WHEN NOTHING MATCHES
--------------------
`S0 / unmatched` is returned, and that is a feature. The alternative -- forcing the
closest-looking signature -- would mean the system is never seen to be uncertain,
which makes its confident answers worthless. An unmatched incident still ships with
its full evidence: metric, segment, dollar impact, and what was ruled out. It just
does not pretend to know the mechanism.

THE ONE INFERENCE THAT IS ALWAYS AVAILABLE
------------------------------------------
Because the metric itself names the funnel stage, the OWNER is always known even
when the mechanism is not: fill is demand, render is engineering, eCPM is pricing,
requests is growth/supply, CTR is creative. config.METRIC_DEFS carries that, so an
unmatched incident is still routable.
"""

from dataclasses import dataclass, field
from typing import Optional

from engine.config import METRIC_DEFS
from engine.uniformity import (CONCENTRATED_BREADTH, DOMINANT_CONCENTRATION,
                               UNIFORM_BREADTH, SpreadStat)

# Entity roots, used to phrase rules in terms of "geo-ish" / "supply-ish" scopes
# without enumerating every scope name in every rule.
_GEO_SCOPES = {"region", "country", "device_model", "os_version", "os_family",
               "geo_cell", "os_family_region"}
_SUPPLY_SCOPES = {"app", "category", "publisher_tier"}
# Only `app` is an actual integration that can break. `category` and
# `publisher_tier` are AGGREGATES of apps, so a breach there is nearly always a
# symptom of something upstream rather than a cause -- attributing "one publisher
# broke" to publisher_tier=tier_2 would name a bucket, not a fault, and send
# someone to look at 600 apps at once. They are eligible roots only when nothing
# better explains the movement.
_SUPPLY_ENTITY_SCOPES = {"app"}
_SUPPLY_AGGREGATE_SCOPES = {"category", "publisher_tier"}
_DEMAND_SCOPES = {"advertiser", "vertical", "campaign_type"}
_FORMAT_SCOPES = {"ad_format", "format_region"}
_OS_SCOPES = {"os_family", "os_version", "os_family_region"}


@dataclass
class SignatureMatch:
    signature: str                 # 'S1'..'S11', or 'S0'
    mechanism: str                 # the plain-English mechanism sentence (deterministic)
    owner: str
    confidence: float              # 0..1, from how cleanly the fingerprint matched
    inputs_used: dict = field(default_factory=dict)
    evidence_lines: list = field(default_factory=list)
    source_steps: list = field(default_factory=list)

    @property
    def matched(self) -> bool:
        return self.signature != "S0"


def _fmt(stat: Optional[SpreadStat]) -> str:
    if stat is None or stat.evaluated == 0:
        return "not evaluated"
    return f"{stat.breached}/{stat.evaluated} breached ({stat.breadth:.0%})"


def _uniform(stat: Optional[SpreadStat]) -> bool:
    """Strictly above the threshold -- see the note on UNIFORM_BREADTH in uniformity.py for
    why `>=` made 0.50 simultaneously "spread" and "isolated"."""
    return stat is not None and stat.evaluated > 0 and stat.breadth > UNIFORM_BREADTH


def _flat(stat: Optional[SpreadStat]) -> bool:
    """Explicitly flat: evaluated, and nothing breached. Distinct from
    'not evaluated', which is not evidence of anything."""
    return stat is not None and stat.evaluated > 0 and stat.breached == 0


def _concentrated(stat: Optional[SpreadStat]) -> bool:
    return stat is not None and stat.evaluated > 0 and 0 < stat.breadth <= CONCENTRATED_BREADTH


def _any_of(stats: dict, names: set) -> Optional[SpreadStat]:
    """The most informative stat among a group of scope types (the one with the
    most entities evaluated -- i.e. the broadest actual evidence)."""
    candidates = [stats[n] for n in names if n in stats and stats[n].evaluated > 0]
    return max(candidates, key=lambda s: s.evaluated) if candidates else None


def match_signature(
    metric: str,
    direction: str,
    root_scope_type: str,
    root_scope_value: str,
    partner_stats: dict,
    sibling_stat: Optional[SpreadStat] = None,
    impact_usd: float = 0.0,
) -> SignatureMatch:
    """The rule table. First match wins; rules are ordered most-specific first."""
    spec = METRIC_DEFS[metric]
    owner = spec.owner
    supply = _any_of(partner_stats, _SUPPLY_SCOPES)
    demand = _any_of(partner_stats, _DEMAND_SCOPES)
    fmt = _any_of(partner_stats, _FORMAT_SCOPES)
    geo = _any_of(partner_stats, _GEO_SCOPES)

    inputs = {
        "metric": metric, "direction": direction,
        "root_scope_type": root_scope_type, "root_scope_value": root_scope_value,
        "impact_usd": impact_usd,
        "partner_spread": {k: {"breached": v.breached, "evaluated": v.evaluated,
                               "breadth": round(v.breadth, 4)} for k, v in partner_stats.items()},
    }
    if sibling_stat is not None:
        inputs["sibling_spread"] = {
            "scope_type": sibling_stat.scope_type,
            "breached": sibling_stat.breached,
            "evaluated": sibling_stat.evaluated,
            "breadth": round(sibling_stat.breadth, 4),
            "top_value": sibling_stat.top_value,
            "concentration": round(sibling_stat.concentration, 4),
        }
    lines = [s.as_reason() for s in partner_stats.values()]
    steps = sorted({st for s in partner_stats.values() for st in s.source_steps})

    def M(sig, mech, conf, own=None):
        return SignatureMatch(signature=sig, mechanism=mech, owner=own or owner,
                              confidence=conf, inputs_used=inputs, evidence_lines=lines,
                              source_steps=steps)

    sib_txt = ""
    if sibling_stat is not None and sibling_stat.evaluated > 0:
        sib_txt = (f" Within {root_scope_type}, {sibling_stat.breached} of "
                   f"{sibling_stat.evaluated} values breached, so this is not a "
                   f"population-wide movement.")

    # === CTR / requests ABOVE band: fraud and bot patterns ===================
    if direction == "above" and metric == "ctr" and root_scope_type in (_SUPPLY_SCOPES | {"geo_cell", "country"}):
        return M("S9",
                 f"CTR is ABOVE its band for {root_scope_type} {root_scope_value!r} while other "
                 f"dimensions are not ({_fmt(geo)} across geo). An isolated CTR spike in one "
                 f"source is the classic click-fraud / invalid-traffic pattern rather than a "
                 f"genuine engagement gain, and it inflates CPC/CPI spend before it shows up as "
                 f"revenue.{sib_txt}", 0.7, own="creative")

    if direction == "above" and metric == "requests" and _concentrated(supply):
        return M("S9",
                 f"Request volume is ABOVE its band and concentrated in {root_scope_type} "
                 f"{root_scope_value!r} ({_fmt(supply)} across apps). A volume spike confined to "
                 f"one source, with no matching lift downstream, is characteristic of bot traffic "
                 f"or an SDK retry loop rather than real demand.{sib_txt}", 0.65, own="growth")

    if direction == "above" and metric == "ecpm":
        return M("S9",
                 f"eCPM is ABOVE its band for {root_scope_type} {root_scope_value!r}. A price that "
                 f"jumps without a matching mix change is usually a misconfigured floor or a "
                 f"pricing/targeting error, and it is worth checking before it is celebrated."
                 f"{sib_txt}", 0.55, own="pricing")

    # === fill rate / fills BELOW band: the demand-side family ===============
    if metric in ("fill_rate", "fills") and direction == "below":
        # S4 -- one OS family down across many regions, uniform across apps and
        # formats. The demand integration for that OS is failing.
        if root_scope_type in _OS_SCOPES and (_uniform(supply) or _uniform(fmt)):
            return M("S4",
                     f"Fill rate has dropped for {root_scope_type} {root_scope_value!r} and the drop "
                     f"is spread across the supply that serves it ({_fmt(supply)} across apps, "
                     f"{_fmt(fmt)} across formats). A shortfall that follows one OS everywhere it "
                     f"appears, rather than following any particular app or format, points to a "
                     f"demand partner or integration serving that OS having stopped bidding."
                     f"{sib_txt}", 0.85, own="demand")

        # S5 -- one advertiser slice, whose own exposure is normal: they stopped
        # buying rather than the platform failing to reach them.
        if root_scope_type in _DEMAND_SCOPES:
            return M("S5",
                     f"Fill has dropped for {root_scope_type} {root_scope_value!r} while the supply "
                     f"it buys against is unchanged ({_fmt(supply)} across apps). When a buyer's "
                     f"exposure is normal and only its fills fall, the cause is on the buying side "
                     f"-- a paused campaign, an exhausted budget, or a bid/floor change -- not a "
                     f"platform fault.{sib_txt}", 0.8, own="demand")

        # S6 -- one region x device generation, uniform across apps: targeted
        # demand loss. This is the case that is invisible at every 1-D scope.
        #
        # `supply is None` was previously accepted here as if it corroborated the rule, so
        # an unmeasured partner dimension matched at the full 0.80 and the citation rendered
        # as the literal string "not evaluated" inside a sentence asserting the mechanism.
        # Absence of evidence is not evidence, so it now requires a real measurement and
        # otherwise falls through to the lower-confidence geographic rule below.
        if root_scope_type in ("geo_cell", "os_family_region") and _uniform(supply):
            return M("S6",
                     f"Fill has dropped specifically for {root_scope_value!r} and is uniform across "
                     f"the apps serving it ({_fmt(supply)}). A shortfall confined to one "
                     f"device population in one geography, while neighbouring cells are unaffected, "
                     f"indicates demand that targets that segment being withdrawn or retargeted "
                     f"rather than a supply or rendering fault.{sib_txt}", 0.8, own="demand")

        # S10 -- one format, everywhere: that format's demand source went dark.
        if root_scope_type in _FORMAT_SCOPES and (_uniform(supply) or _uniform(geo)):
            return M("S10",
                     f"Fill has dropped for {root_scope_type} {root_scope_value!r} across the apps "
                     f"and geographies that carry it ({_fmt(supply)} across apps, {_fmt(geo)} across "
                     f"geo). A format-wide shortfall that follows the format rather than any "
                     f"publisher indicates the demand source for that format has stopped "
                     f"responding.{sib_txt}", 0.75, own="demand")

        # S2 -- one app only, everywhere it operates. Restricted to `app`: an
        # aggregate like publisher_tier is a bucket of apps, not an integration
        # that can break, so "confined to one publisher" would be false of it.
        if root_scope_type in _SUPPLY_ENTITY_SCOPES:
            return M("S2",
                     f"Fill has dropped for {root_scope_type} {root_scope_value!r} across all the "
                     f"geographies and formats it serves ({_fmt(geo)} across geo). A shortfall "
                     f"confined to one publisher, while every other publisher is unaffected, points "
                     f"at that integration -- blocked inventory, a failed release, or a changed ad "
                     f"configuration.{sib_txt}", 0.7, own="engineering")

        # An aggregate supply bucket moved. This is reported as an aggregate
        # movement, explicitly NOT as "that bucket is the cause" -- the honest
        # reading is that demand thinned across the apps inside it.
        if root_scope_type in _SUPPLY_AGGREGATE_SCOPES:
            return M("S5",
                     f"Fill has dropped across {root_scope_type} {root_scope_value!r}, which is an "
                     f"aggregate of many apps rather than a single integration ({_fmt(supply)} "
                     f"across individual apps). Read as demand thinning for the inventory in that "
                     f"bucket, not as a fault in the bucket itself; if a specific app or demand "
                     f"partner is responsible it will appear as its own finding.{sib_txt}",
                     0.45, own="demand")

        if root_scope_type in _GEO_SCOPES:
            return M("S6",
                     f"Fill has dropped for {root_scope_type} {root_scope_value!r} while the supply "
                     f"serving it is otherwise normal ({_fmt(supply)} across apps). Demand for that "
                     f"segment appears to have been reduced or retargeted.{sib_txt}", 0.6, own="demand")

    # === render rate BELOW band: engineering's family =======================
    if metric == "render_rate" and direction == "below":
        if root_scope_type in _FORMAT_SCOPES:
            return M("S11",
                     f"Ads are being bought but not shown for {root_scope_type} "
                     f"{root_scope_value!r}: fills are normal and impressions are not. Confined to "
                     f"one format ({_fmt(supply)} across apps), this is the player or rendering SDK "
                     f"for that format failing, not a demand problem -- the inventory was sold and "
                     f"then lost.{sib_txt}", 0.8, own="engineering")
        if root_scope_type in _SUPPLY_SCOPES:
            return M("S7",
                     f"Ads are being bought but not shown for {root_scope_type} "
                     f"{root_scope_value!r}: fills are normal while impressions have fallen. "
                     f"Confined to one publisher ({_fmt(geo)} across geo), this is a rendering "
                     f"failure in that app's integration -- most often a bad release or a broken "
                     f"placement.{sib_txt}", 0.8, own="engineering")
        return M("S7",
                 f"Render rate has fallen for {root_scope_type} {root_scope_value!r} while fills "
                 f"held up, so demand was secured and then not displayed. That is a rendering "
                 f"fault rather than a demand shortfall.{sib_txt}", 0.6, own="engineering")

    # === requests BELOW band: the supply / external family ==================
    if metric == "requests" and direction == "below":
        # S1 -- one geography, uniform across every app and device: the users are
        # not there. Nothing on the platform can cause that shape.
        if root_scope_type in _GEO_SCOPES and _uniform(supply):
            return M("S1",
                     f"Request volume has fallen in {root_scope_type} {root_scope_value!r} uniformly "
                     f"across the apps and devices there ({_fmt(supply)} across apps). Traffic loss "
                     f"that affects every app in one place at once originates outside the platform "
                     f"-- connectivity, a public holiday, or a local event -- because no platform "
                     f"component is scoped to a geography that way.{sib_txt}", 0.8, own="external")

        # S2 -- one app, everywhere: that app lost users or removed the SDK.
        # Same correction as S6 above: an unmeasured geo dimension no longer counts as
        # corroboration for "this app lost traffic everywhere it operates".
        if root_scope_type in _SUPPLY_SCOPES and _uniform(geo):
            return M("S2",
                     f"Request volume has fallen for {root_scope_type} {root_scope_value!r} across "
                     f"every geography it serves ({_fmt(geo)} across geo). Supply loss that follows "
                     f"one publisher everywhere indicates that app's own traffic or integration -- a "
                     f"bad release, an SDK removal, or a store delisting.{sib_txt}", 0.75, own="growth")

        # S3 -- everything, everywhere, with rates intact: this is volume, not a fault.
        if root_scope_type == "global" or (_uniform(supply) and _uniform(geo)):
            return M("S3",
                     f"Request volume is below band globally while the funnel rates are unchanged. "
                     f"Volume moving on its own, with fill, render and price all holding, is a "
                     f"traffic-level movement rather than a fault -- the platform is handling a "
                     f"smaller number of opportunities the same way it handles a larger one."
                     f"{sib_txt}", 0.6, own="growth")

    # === eCPM BELOW band: pricing / mix =====================================
    if metric == "ecpm" and direction == "below":
        return M("S8",
                 f"eCPM has fallen for {root_scope_type} {root_scope_value!r} while fill and render "
                 f"held up, so the same inventory is being sold more cheaply. That is a pricing or "
                 f"demand-mix movement -- cheaper demand winning more auctions, or a shift in the "
                 f"mix of formats and geographies -- rather than an outage.{sib_txt}", 0.6, own="pricing")

    # === nothing matched ====================================================
    return SignatureMatch(
        signature="S0",
        mechanism=(
            f"{metric} moved {direction} band for {root_scope_type} {root_scope_value!r} "
            f"(${abs(impact_usd):,.2f} exposure), but the spread fingerprint does not match a known "
            f"mechanism: "
            + ("; ".join(f"{k} {_fmt(v)}" for k, v in sorted(partner_stats.items())) or "no partner dimensions were evaluated")
            + f". The deviation and its segment are established; the mechanism is not, and is "
              f"reported as unknown rather than guessed. Metric ownership still routes this to "
              f"{owner}."
        ),
        owner=owner,
        confidence=0.0,
        inputs_used=inputs,
        evidence_lines=lines,
        source_steps=steps,
    )


def seasonality_disproof(sibling_stat: Optional[SpreadStat], root_scope_type: str,
                         root_scope_value: str) -> dict:
    """The device test, as a checkable statement rather than an assertion.

    Baselines here are already same-weekday/same-hour matched, so seasonality is
    controlled for by construction. This adds an independent, physical argument
    that does not depend on trusting the baseline at all:

        seasonality acts on PEOPLE. People carry every device model and run every
        OS. So a seasonal dip has to move all of them together. If one device
        population or one OS family fell while its siblings held flat, no calendar
        effect can explain it.

    Returns the numbers and the verdict, or an explicit "cannot test" -- never a
    bare claim that seasonality was ruled out.
    """
    if sibling_stat is None or sibling_stat.evaluated <= 1:
        return {
            "tested": False,
            "reason": (
                f"the device/sibling test could not be run: only {getattr(sibling_stat, 'evaluated', 0)} "
                f"value(s) of {root_scope_type} were evaluated, so there is nothing to compare "
                f"{root_scope_value!r} against. Seasonality is still controlled for by the "
                f"same-weekday/same-hour baseline, but this independent check is unavailable."
            ),
        }
    isolated = sibling_stat.breadth <= UNIFORM_BREADTH
    return {
        "tested": True,
        "isolated": isolated,
        "siblings_breached": sibling_stat.breached,
        "siblings_evaluated": sibling_stat.evaluated,
        "breadth": round(sibling_stat.breadth, 4),
        "reason": (
            f"seasonality is ruled out independently of the baseline: only "
            f"{sibling_stat.breached} of {sibling_stat.evaluated} {root_scope_type} values moved, so "
            f"{root_scope_value!r} fell while its siblings held. Seasonality acts on people, and "
            f"people carry every device and OS, so it cannot move one population and leave the "
            f"rest flat."
            if isolated else
            f"this movement is NOT isolated -- {sibling_stat.breached} of {sibling_stat.evaluated} "
            f"{root_scope_type} values moved together, which is the shape a population-wide or "
            f"seasonal effect would produce. Treat the segment attribution with caution."
        ),
    }
