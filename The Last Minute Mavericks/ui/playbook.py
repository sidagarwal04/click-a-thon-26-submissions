"""RootCauseOS playbook — deterministic incident classification. NO LLM.

This module is a lookup table, not AI judgment. Each rule below is keyed on
(metric, verdict, culprit dimension) and maps a diagnosed incident shape to:

  origin        internal | external | indeterminate
  controllable  controllable | partially | uncontrollable
  actions       ordered triage steps, each tagged now | today | monitor

Rules table (first match wins, top to bottom):

  rule_id                       metric      verdict              culprit dim
  ----------------------------  ----------  -------------------  -----------
  normal_no_action              *           NORMAL               *
  requests_global_unlocalized   *           GLOBAL_UNLOCALIZED   *
  fill_rate_co_cut              fill_rate   *                    any + co_cut
  fill_rate_os_version          fill_rate   *                    os_version
  ecpm_category_demand          ecpm        *                    *category*
  ecpm_ad_format_mix            ecpm        *                    *ad_format*
  fallback                      *           *                    *

A 2-D culprit arrives from the engine as dimension "region×os_version" with the
pair inside value and co_cut UNSET — so co_cut is derived from the value, and the
action text uses the first pair as the subject and the second as the co-cut.
Without that, every co_cut rule above was unreachable on real engine output.

Metric matching also considers the decomposition's primary_driver factor, so
a revenue incident driven by fill_rate matches the fill_rate rules.

Numbers are NEVER invented here: action text interpolates only the culprit
dimension/value and metric names read from the bundle. Every classification
carries its rule_id + rule_explanation so the UI can show WHY it appeared.
"""
from __future__ import annotations

NOW = "now"
TODAY = "today"
MONITOR = "monitor"


class _Ctx(dict):
    """format_map context that leaves unknown placeholders visible."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        return "{" + key + "}"


RULES: tuple[dict, ...] = (
    {
        "rule_id": "normal_no_action",
        "when": {"metric": "*", "verdict": "NORMAL", "dimension": "*", "co_cut": None},
        "origin": "indeterminate",
        "controllable": "controllable",
        "explanation": (
            "no action needed — the movement is inside the expected band and "
            "seasonality is absorbed by the baseline"
        ),
        "actions": (),
    },
    {
        # The signature here is the verdict, not the metric: a uniform move
        # across EVERY dimension (classically seen on requests) cannot be
        # localized, so the bundle cannot distinguish an internal pipeline
        # fault from an upstream outage.
        "rule_id": "requests_global_unlocalized",
        "when": {"metric": "*", "verdict": "GLOBAL_UNLOCALIZED", "dimension": "*", "co_cut": None},
        "origin": "indeterminate",
        "controllable": "partially",
        "explanation": (
            "a uniform move across every dimension with no localizable culprit "
            "means internal pipeline OR upstream outage — the bundle cannot "
            "distinguish them"
        ),
        "actions": (
            {
                "urgency": NOW,
                "title": "Check event ingestion + SDK heartbeat",
                "detail": (
                    "A uniform {metric} drop of the same magnitude across every "
                    "dimension usually means the pipeline, not the market — verify "
                    "ingestion lag and SDK heartbeat before treating this as demand."
                ),
            },
            {
                "urgency": NOW,
                "title": "Check status pages of exchange/mediation partners",
                "detail": (
                    "If a major exchange or mediation partner is down, every "
                    "dimension drops together — rule an upstream outage out before "
                    "touching internal systems."
                ),
            },
            {
                "urgency": TODAY,
                "title": "Annotate the incident window so forecasts exclude it",
                "detail": (
                    "Mark the window in the metrics warehouse so baselines and "
                    "pacing forecasts do not learn from the outage."
                ),
            },
        ),
    },
    {
        # 2-D culprit: neither dimension alone explains the collapse.
        "rule_id": "fill_rate_co_cut",
        "when": {"metric": "fill_rate", "verdict": "*", "dimension": "*", "co_cut": True},
        "origin": "external",
        "controllable": "partially",
        "explanation": (
            "a fill-rate collapse confined to the {dimension} × {co_dimension} "
            "intersection points at a regional SDK rollout, regulatory change or "
            "network-level cause — external, partially mitigable"
        ),
        "actions": (
            {
                "urgency": NOW,
                "title": "Check SDK / regulatory / network changes for {value} in {co_value}",
                "detail": (
                    "Neither {dimension} nor {co_dimension} alone explains the drop "
                    "— look for a change specific to {value} within {co_value}: a "
                    "staged SDK rollout, consent/regulatory enforcement, or a "
                    "carrier/network issue."
                ),
            },
            {
                "urgency": TODAY,
                "title": "Contact demand partners about {value} × {co_value} fill",
                "detail": (
                    "Escalate the measured intersection ({dimension} = {value}, "
                    "{co_dimension} = {co_value}) so partners can check bidding and "
                    "delivery on exactly that slice."
                ),
            },
            {
                "urgency": TODAY,
                "title": "Exclude the {value} × {co_value} slice from pacing forecasts",
                "detail": (
                    "Keep the affected {dimension} × {co_dimension} slice out of "
                    "pacing and revenue forecasts until it recovers."
                ),
            },
            {
                "urgency": MONITOR,
                "title": "Alert if fill on {value} × {co_value} stays below band 24h",
                "detail": (
                    "If the intersection does not recover inside a day, escalate "
                    "from monitoring to a partner incident."
                ),
            },
        ),
    },
    {
        "rule_id": "fill_rate_os_version",
        "when": {"metric": "fill_rate", "verdict": "*", "dimension": "os_version", "co_cut": False},
        "origin": "external",
        "controllable": "partially",
        "explanation": (
            "a fill-rate collapse isolated to one os_version is a platform/SDK "
            "behaviour change — external origin, partially controllable via "
            "mediation config and partner escalation"
        ),
        "actions": (
            {
                "urgency": NOW,
                "title": "Check ad-SDK release notes / mediation config for {value}",
                "detail": (
                    "Platform and SDK behaviour changes ship with the OS — confirm "
                    "whether the current ad-SDK build and mediation config are "
                    "certified for {value}."
                ),
            },
            {
                "urgency": TODAY,
                "title": "Contact demand partners about {value} fill",
                "detail": (
                    "Demand partners may have paused or throttled bidding on "
                    "{value} inventory — escalate with the measured segment so they "
                    "can check their side."
                ),
            },
            {
                "urgency": TODAY,
                "title": "Exclude segment from pacing forecasts until recovered",
                "detail": (
                    "Keep {value} traffic out of pacing and revenue forecasts so "
                    "the collapse does not drag projections down."
                ),
            },
            {
                "urgency": MONITOR,
                "title": "Alert if fill on {value} stays below band 24h",
                "detail": (
                    "If the segment does not recover inside a day, escalate from "
                    "monitoring to a partner incident."
                ),
            },
        ),
    },
    {
        "rule_id": "ecpm_category_demand",
        "when": {"metric": "ecpm", "verdict": "*", "dimension": "~category", "co_cut": None},
        "origin": "external",
        "controllable": "uncontrollable",
        "explanation": (
            "an eCPM move concentrated in one category is demand-side — "
            "advertiser budgets or auction dynamics — mostly outside supply-side "
            "control"
        ),
        "actions": (
            {
                "urgency": TODAY,
                "title": "Notify sellers of {value} inventory softness",
                "detail": (
                    "Demand for {value} inventory has softened — sellers can adjust "
                    "floors and expectations, but they cannot restore advertiser "
                    "budgets."
                ),
            },
            {
                "urgency": MONITOR,
                "title": "Watch for recovery; no supply-side action indicated",
                "detail": (
                    "Budget-driven eCPM moves resolve on the demand side — track "
                    "the band and avoid supply-side changes that would not address "
                    "the cause."
                ),
            },
        ),
    },
    {
        # An eCPM move confined to ONE ad format is the classic mix-shift signature:
        # inventory reallocated between formats moves each format's price sharply while
        # total revenue barely moves. Treating it as lost demand is the expensive
        # mistake, so the first action is to check the sibling format before acting.
        # This rule states what to CHECK; it never asserts the sibling moved.
        "rule_id": "ecpm_ad_format_mix",
        "when": {"metric": "ecpm", "verdict": "*", "dimension": "~ad_format", "co_cut": None},
        "origin": "indeterminate",
        "controllable": "partially",
        "explanation": (
            "an eCPM move confined to a single ad format is usually a mix shift or a "
            "pricing/config change for that format, not a market-wide demand move — "
            "internal config and external demand both produce this shape, so the "
            "sibling formats and the net revenue effect decide which"
        ),
        "actions": (
            {
                "urgency": NOW,
                "title": "Compare the other ad formats over the same days",
                "detail": (
                    "If another format moved the opposite way, inventory shifted "
                    "between formats — {metric} per format changes sharply while total "
                    "revenue barely moves. That is a mix shift, not lost demand, and it "
                    "needs no recovery action."
                ),
            },
            {
                "urgency": NOW,
                "title": "Check floor prices and waterfall config for {value}",
                "detail": (
                    "A step change in one format's {metric} usually follows a config "
                    "change: floor prices, ad-unit mapping, or a reordered "
                    "waterfall/bidding setup for {value}."
                ),
            },
            {
                "urgency": TODAY,
                "title": "Confirm the net revenue effect before escalating",
                "detail": (
                    "Read the revenue-per-day change in the decomposition. A format "
                    "swap can move {metric} sharply while revenue stays flat — escalate "
                    "on the revenue number, not on the {metric} number."
                ),
            },
            {
                "urgency": MONITOR,
                "title": "Alert if {value} stays outside its band for 48h",
                "detail": (
                    "A genuine demand change persists; a one-off config or mix change "
                    "settles into a new steady level."
                ),
            },
        ),
    },
    {
        "rule_id": "fallback",
        "when": {"metric": "*", "verdict": "*", "dimension": "*", "co_cut": None},
        "origin": "indeterminate",
        "controllable": "partially",
        "explanation": (
            "no playbook rule matches this (metric, verdict, culprit) "
            "combination — generic triage applies"
        ),
        "actions": (
            {
                "urgency": NOW,
                "title": "Confirm the incident is real",
                "detail": (
                    "Re-run the headline query for {metric} and check ingestion "
                    "freshness before acting on the number."
                ),
            },
            {
                "urgency": NOW,
                "title": "Review the evidence bundle by hand",
                "detail": (
                    "Walk the decomposition and hypothesis ledger — the culprit "
                    "fields a specific playbook rule needs are missing or "
                    "unmatched."
                ),
            },
            {
                "urgency": TODAY,
                "title": "Annotate the incident window",
                "detail": (
                    "Mark the window so baselines and forecasts exclude it while "
                    "triage continues."
                ),
            },
        ),
    },
)


# ---------------------------------------------------------------- matching

def _effective_metrics(bundle: dict) -> set[str]:
    """The bundle metric plus the decomposition's primary driver.

    A revenue incident whose decomposition names fill_rate as primary_driver
    should match the fill_rate rules — the driver is the actionable metric.
    """
    mets: set[str] = set()
    m = str(bundle.get("metric") or "").strip().lower()
    if m:
        mets.add(m)
    # Tolerate BOTH shapes: the §8 golden fixture nests factors under a dict
    # ({"method":..., "factors":[...]}), while the engine's §8.1 scan bundle emits
    # `decomposition` as the factor LIST directly. Without this, chat/playbook crash
    # ('list' object has no attribute 'get') on real engine output.
    decomp = bundle.get("decomposition")
    factors = (decomp.get("factors") if isinstance(decomp, dict) else decomp) or []
    for f in factors:
        # the normalizer now carries the engine's RAW verdict ("driver") on `verdict`
        # and the legacy mapped value ("primary_driver") on `verdict_norm` — accept
        # either spelling from either field, or a playbook rule silently stops
        # matching its driver metric
        _DRIVER = {"driver", "primary_driver"}
        if f.get("factor") and (_DRIVER & {str(f.get("verdict", "")),
                                           str(f.get("verdict_norm", ""))}):
            mets.add(str(f["factor"]).strip().lower())
    return mets


def _co_cut_parts(culprit: dict) -> tuple[str, str] | None:
    """Normalise a co_cut (2nd culprit dimension) into (dimension, value)."""
    co = culprit.get("co_cut")
    if not co:
        # The engine does NOT populate co_cut. It encodes a 2-D culprit entirely in the
        # value — dimension "region×os_version", value "region=APAC × os_version=iOS 18.1".
        # Without this, every engine-produced 2-D incident looked 1-D and the co_cut rules
        # (the most specific ones we have) could never fire. Derive the 2nd pair from the
        # value; the 1st pair stays the primary culprit.
        pairs = [p.strip() for p in str(culprit.get("value") or "").replace("∩", "×").split("×")]
        kv = [tuple(x.strip() for x in p.split("=", 1)) for p in pairs if "=" in p]
        if len(kv) >= 2:
            return (kv[1][0], kv[1][1])
        return None
    if isinstance(co, dict):
        return (
            str(co.get("dimension") or co.get("dim") or "co-dimension"),
            str(co.get("value") or co.get("val") or "co-segment"),
        )
    if isinstance(co, (list, tuple)) and len(co) >= 2:
        return (str(co[0]), str(co[1]))
    s = str(co)
    if "=" in s:
        d, v = s.split("=", 1)
        return (d.strip(), v.strip())
    return (s, s)


try:  # shared vocabulary; playbook still works standalone if it is absent
    from ui import explain as _X
except Exception:  # noqa: BLE001
    _X = None


def _kv_pairs(value: str) -> list[tuple[str, str]]:
    out = []
    for part in str(value or "").replace("∩", "×").split("×"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            out.append((k.strip(), v.strip()))
        elif part:
            out.append(("", part))
    return out


def _culprit_text_parts(dim: str, val: str, co) -> tuple[str, str, str, str]:
    """(primary_dim, primary_val, co_dim, co_val) for ACTION TEXT only.

    Strips the `key=` noise and unpacks a compound 2-D culprit so a template reads
    "APAC in iOS 18.1" instead of "region=APAC × os_version=iOS 18.1 in iOS 18.1".
    """
    pairs = _kv_pairs(val)
    dims = [d.strip() for d in str(dim or "").replace("∩", "×").split("×") if d.strip()]
    p_dim = (pairs[0][0] if pairs and pairs[0][0] else (dims[0] if dims else dim)) or ""
    p_val = pairs[0][1] if pairs else val
    if len(pairs) >= 2:
        c_dim, c_val = pairs[1][0] or (dims[1] if len(dims) > 1 else ""), pairs[1][1]
    else:
        c_dim, c_val = (co[0], co[1]) if co else ("", "")
    return p_dim.replace("_", " "), p_val, c_dim.replace("_", " "), c_val


def _matches(rule: dict, mets: set[str], verdict: str, dim: str,
             co: tuple[str, str] | None) -> bool:
    w = rule["when"]
    if w["verdict"] != "*" and verdict != w["verdict"]:
        return False
    if w["metric"] != "*" and w["metric"] not in mets:
        return False
    dm = w["dimension"]
    if dm != "*":
        if dm.startswith("~"):
            if dm[1:] not in dim.lower():
                return False
        elif dim.lower() != dm:
            return False
    if w["co_cut"] is True and co is None:
        return False
    if w["co_cut"] is False and co is not None:
        return False
    return True


def _confidence_note(bundle: dict, rule: dict, ctx: _Ctx) -> str:
    culprit_key = ctx["dimension"] if bundle.get("culprit") else "—"
    key = (
        f"(metric={ctx['metric']}, verdict={bundle.get('verdict') or '—'}, "
        f"culprit={culprit_key})"
    )
    note = f"Deterministic playbook lookup on {key} → rule '{rule['rule_id']}'."
    lc = (bundle.get("scores") or {}).get("localization_confidence")
    if lc is not None:
        note += (
            f" Pipeline localization confidence {lc} is reported from the "
            "bundle; the classification itself is a static rule, not a model "
            "output."
        )
    else:
        note += " The classification is a static rule, not a model output."
    return note


# ---------------------------------------------------------------- public API

def classify(bundle: dict) -> dict:
    """Classify an incident bundle against the deterministic rules table.

    Returns origin/controllability, ordered actions, and the matched rule
    (rule_id + rule_explanation) so the UI can show why. Pure lookup — no LLM.
    """
    bundle = bundle or {}
    verdict = str(bundle.get("verdict") or "").strip().upper()
    culprit = bundle.get("culprit") or {}
    dim = str(culprit.get("dimension") or "").strip()
    val = str(culprit.get("value") or "").strip()
    co = _co_cut_parts(culprit)
    mets = _effective_metrics(bundle)

    chosen = RULES[-1]  # fallback matches everything anyway
    for rule in RULES:
        if _matches(rule, mets, verdict, dim, co):
            chosen = rule
            break

    # A 2-D culprit arrives as compounds: dimension "region×os_version", value
    # "region=APAC × os_version=iOS 18.1". Templates say "{value} in {co_value}", so
    # feeding them the WHOLE pair as {value} produced "region=APAC × os_version=iOS 18.1
    # in iOS 18.1". Split for the TEXT; `dim` above stays compound for rule MATCHING.
    p_dim, p_val, c_dim, c_val = _culprit_text_parts(dim, val, co)
    ctx = _Ctx(
        metric=_X.metric_name(bundle.get("metric")) if _X else str(bundle.get("metric") or "the metric"),
        dimension=p_dim or "the culprit dimension",
        value=p_val or "the culprit segment",
        co_dimension=c_dim or "the co-dimension",
        co_value=c_val or "the co-segment",
    )
    actions = [
        {
            "title": a["title"].format_map(ctx),
            "detail": a["detail"].format_map(ctx),
            "urgency": a["urgency"],
        }
        for a in chosen["actions"]
    ]
    return {
        "origin": chosen["origin"],
        "controllable": chosen["controllable"],
        "confidence_note": _confidence_note(bundle, chosen, ctx),
        "actions": actions,
        "rule_id": chosen["rule_id"],
        "rule_explanation": chosen["explanation"].format_map(ctx),
    }


def demo() -> None:
    """Self-check for the 2-D culprit handling — both bugs it fixes were silent.

        python -m ui.playbook
    """
    # The engine encodes a 2-D culprit in dimension/value and leaves co_cut None.
    # Before the fix this looked 1-D, so every co_cut rule was unreachable.
    c2 = {"dimension": "region×os_version",
          "value": "region=APAC × os_version=iOS 18.1", "co_cut": None}
    assert _co_cut_parts(c2) == ("os_version", "iOS 18.1")
    assert _co_cut_parts({"dimension": "category", "value": "finance"}) is None
    assert _co_cut_parts({"co_cut": {"dimension": "region", "value": "EU"}}) == ("region", "EU")

    # Action text takes the FIRST pair as the subject, the SECOND as the co-cut —
    # feeding it the whole compound produced "APAC × iOS 18.1 in iOS 18.1".
    assert _culprit_text_parts("region×os_version", "region=APAC × os_version=iOS 18.1",
                               ("os_version", "iOS 18.1")) == ("region", "APAC",
                                                               "os version", "iOS 18.1")
    assert _culprit_text_parts("category", "finance", None) == ("category", "finance", "", "")

    # A 2-D fill_rate incident must reach the co_cut rule, not the generic fallback.
    assert classify({"metric": "fill_rate", "verdict": "LOCALIZED_2D",
                     "culprit": c2})["rule_id"] == "fill_rate_co_cut"
    # An eCPM move inside one ad format is a mix shift, not demand loss.
    assert classify({"metric": "ecpm", "verdict": "LOCALIZED_2D",
                     "culprit": {"dimension": "ad_format×region",
                                 "value": "ad_format=native × region=EU"}
                     })["rule_id"] == "ecpm_ad_format_mix"
    # Degenerate input must still classify rather than raise.
    for bad in ({}, {"culprit": None}, {"metric": "ecpm", "culprit": {}}):
        assert classify(bad)["rule_id"]
    print("playbook.py OK")


if __name__ == "__main__":
    demo()
