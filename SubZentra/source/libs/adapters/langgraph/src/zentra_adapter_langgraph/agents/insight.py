"""The Insight Agent: validated evidence in, Draft Finding out.

It reaches nothing. No semantic layer, no tools, no data — its `tool_permissions`
are deliberately empty. The metrics it is handed are the only evidence in the
world as far as it is concerned, which is what makes "did it invent this?" a
question with a decidable answer.

Everything below the model call exists to make that answer enforceable rather
than hoped for. A claim naming a metric the Analyst never returned, a value the
aggregate does not carry, or a resolved root cause fails the whole draft closed
instead of becoming reviewable content. ADR 0011 is explicit that Phase 2 may
report observed changes and validated associations, and must say "root cause
unresolved" otherwise.
"""

from __future__ import annotations

import json
from typing import Any

from zentra_domain_agent_execution import (
    AgentDescriptor,
    AgentInput,
    AgentOutput,
    AgentRole,
    ConfidenceOutcome,
    ModelMessage,
    ModelPort,
    validate_agent_output,
)

from ..constants import INSIGHT_MODEL, MAX_TOKENS
from ..prompts import INSIGHT_DRAFT
from ..schemas import (
    DRAFT_FINDING_SCHEMA,
    MalformedAgentResponseError,
    parse_json_object,
)

AGENT_ID = "insight_v1"

OBSERVED = "observed"
INTERPRETATION = "interpretation"

DESCRIPTOR = AgentDescriptor(
    agent_id=AGENT_ID,
    role=AgentRole.INSIGHT,
    # Empty on purpose. Insight is the one agent that reaches no capability at
    # all: it works only on state two other agents already validated, so it has
    # nothing to be granted.
    tool_permissions=(),
    context_budget_tokens=MAX_TOKENS,
    input_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "analyst": {"type": "object"},
            "evaluator": {"type": "object"},
        },
    },
    output_schema=DRAFT_FINDING_SCHEMA,
    output_fields=frozenset(
        {"headline", "summary", "claims", "contradictions", "root_cause"}
    ),
    eval_suite_ref="evals/insight",
    # `fallback_ref` stays unset. Insight's fallback policy is the role-keyed
    # provider chain in the model-providers adapter, and the rungs that failed
    # before one answered are attributed through `AgentOutput.fallbacks`. That
    # is a real, tested policy; pointing a field no code reads at it would only
    # look like one.
    fallback_ref=None,
)


class UnsupportedCausalClaimError(ValueError):
    """Insight asserted a cause its evidence cannot establish."""


class UngroundedClaimError(ValueError):
    """A claim referenced evidence that is not in the validated upstream state."""


class AbsentEvidenceError(ValueError):
    """There is no validated aggregate to draw a Draft Finding from."""


class InsightAgent:
    """Turns validated upstream results into a bounded, non-causal draft."""

    def __init__(self, *, model: ModelPort) -> None:
        self._model = model

    @property
    def descriptor(self) -> AgentDescriptor:
        return DESCRIPTOR

    async def invoke(self, agent_input: AgentInput) -> AgentOutput:
        question = str(agent_input.state.get("question", ""))
        analyst = _mapping(agent_input.state.get("analyst"))
        evaluator = _mapping(agent_input.state.get("evaluator"))

        metrics = [_mapping(metric) for metric in analyst.get("metrics", [])]
        if not metrics:
            summary = analyst.get("result_summary")
            if not isinstance(summary, str) or not summary.strip():
                # Drafting from nothing is how a confident, groundless finding
                # gets written. There is no draft to be had here.
                raise AbsentEvidenceError(
                    "No validated aggregate is available to draft a finding from"
                )
            # A catalog/schema question genuinely has no metric to report —
            # the Analyst already said so by returning none. Relaying its own
            # validated summary is not drafting a finding from nothing; it is
            # the answer, with no claim to ground because none was asked for.
            return validate_agent_output(
                self,
                AgentOutput(
                    fields={
                        # `headline` is a distinct, short field downstream
                        # (`VisualizationBriefV1.headline`, max 240 chars) —
                        # the Analyst's summary is not written to that bound.
                        "headline": _headline_from(summary),
                        "summary": summary,
                        "claims": [],
                        "contradictions": _preserved_contradictions({}, evaluator),
                        "root_cause": "unresolved",
                    },
                    evidence_refs=_upstream_evidence(analyst, evaluator),
                    outcome=ConfidenceOutcome(
                        score=_bounded_confidence({"confidence": 1.0}, evaluator),
                        calibration_method="insight_bounded_by_evaluator",
                    ),
                ),
            )

        response = await self._model.complete(
            model=INSIGHT_MODEL,
            system=INSIGHT_DRAFT,
            messages=[
                ModelMessage(
                    role="user",
                    content=(
                        f"Question: {question}\n\n"
                        f"Validated metrics: {json.dumps(metrics)}\n"
                        f"Analyst summary: {analyst.get('result_summary', '')}\n\n"
                        f"Evaluator recheck passed: "
                        f"{evaluator.get('recheck_passed')}\n"
                        f"Evaluator issues: "
                        f"{json.dumps(evaluator.get('issues', []))}"
                    ),
                )
            ],
            max_tokens=MAX_TOKENS,
            response_schema=DRAFT_FINDING_SCHEMA,
        )
        draft = parse_json_object(response.text)

        if draft.get("root_cause_resolved"):
            raise UnsupportedCausalClaimError(
                "Insight reported a resolved root cause; Phase 2 admits no "
                "Root Cause Claim"
            )

        claims = _validated_claims(draft, metrics)
        contradictions = _preserved_contradictions(draft, evaluator)

        return validate_agent_output(
            self,
            AgentOutput(
                fields={
                    "headline": _required_text(draft, "headline"),
                    "summary": _required_text(draft, "summary"),
                    "claims": claims,
                    "contradictions": contradictions,
                    "root_cause": "unresolved",
                },
                # Pass upstream pointers through unchanged. Insight produces no
                # evidence of its own; it is downstream of everything that did.
                evidence_refs=_upstream_evidence(analyst, evaluator),
                outcome=ConfidenceOutcome(
                    score=_bounded_confidence(draft, evaluator),
                    calibration_method="insight_bounded_by_evaluator",
                ),
                usage=response.usage,
                fallbacks=response.fallbacks,
            ),
        )


#: Must not exceed `VisualizationBriefV1.headline`'s `max_length` (240) —
#: duplicated rather than imported, since this package has no dependency on
#: the domain investigation model that field lives on.
_HEADLINE_MAX_LENGTH = 240


def _headline_from(summary: str) -> str:
    """A short headline from a summary that was never written to that bound.

    Cuts at a word boundary rather than mid-word, and never invents text the
    summary did not already say.
    """
    stripped = summary.strip()
    if len(stripped) <= _HEADLINE_MAX_LENGTH:
        return stripped
    ellipsis = "…"
    limit = _HEADLINE_MAX_LENGTH - len(ellipsis)
    truncated = stripped[:limit].rsplit(" ", 1)[0]
    return f"{truncated}{ellipsis}"


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _required_text(draft: dict[str, Any], key: str) -> str:
    value = draft.get(key)
    if not isinstance(value, str) or not value.strip():
        # A missing required field is malformed output, not an ungrounded
        # claim. Names the field and nothing else — the offending content is
        # model output derived from customer evidence.
        raise MalformedAgentResponseError(f"Draft finding is missing {key}")
    return value


def _validated_claims(
    draft: dict[str, Any],
    metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Every observed claim must be traceable to a validated aggregate.

    Errors name the claim's position, and a metric name only when that name
    came from the governed aggregate. An *unrecognised* metric name is model
    output — a model can put prose in that field — so it is never echoed. None
    of these messages carry claim text or figures; they reach CI logs.
    """
    # A list per name, not a single entry: a breakdown-by-date question
    # legitimately reports many points under the same metric name, one per
    # period, and a dict keyed by name alone would keep only the last one —
    # silently discarding every earlier day as if the Analyst never reported
    # it, and refusing a claim that cites one as "ungrounded" even though it
    # is right there in `metrics`. Observed live against a 30-day breakdown.
    by_name: dict[str, list[dict[str, Any]]] = {}
    for metric in metrics:
        by_name.setdefault(str(metric.get("metric")), []).append(metric)
    validated: list[dict[str, Any]] = []

    for position, raw in enumerate(draft.get("claims", [])):
        claim = _mapping(raw)
        kind = claim.get("kind")
        if kind not in {OBSERVED, INTERPRETATION}:
            raise UngroundedClaimError(
                f"Claim {position} does not state whether it is observed or "
                f"interpreted"
            )
        text = claim.get("text")
        if not isinstance(text, str) or not text.strip():
            raise UngroundedClaimError(f"Claim {position} has no text")

        metric_name = claim.get("metric")
        if metric_name and metric_name not in by_name:
            raise UngroundedClaimError(
                f"Claim {position} cites a metric the validated aggregate "
                f"does not contain"
            )
        if kind == OBSERVED:
            if not metric_name:
                raise UngroundedClaimError(
                    f"Claim {position} is observed but cites no governed metric"
                )
            # Either side of the comparison is a legitimate thing to state —
            # "refunds were $20 in June" is as observed as "$260 in July" —
            # but the value and the period must be the *same* side. Reporting
            # July's figure under June's label is the one way to be precisely
            # wrong while every individual token is real. Checked against every
            # metric reported under this name, not just one: a breakdown-by-date
            # question reports one entry per period, all sharing the name.
            _require_matching_side(position, metric_name, by_name[metric_name], claim)

        validated.append(
            {
                "kind": kind,
                "text": text,
                "metric": metric_name or None,
                "value": claim.get("value") if kind == OBSERVED else None,
                "period": claim.get("period") if kind == OBSERVED else None,
            }
        )

    return validated


def _require_matching_side(
    position: int,
    metric_name: str,
    candidates: list[dict[str, Any]],
    claim: dict[str, Any],
) -> None:
    """The claimed value and period must be the same side of some comparison.

    Checking them separately would accept July's figure captioned June, which
    is worse than an obvious invention: every token in it is real.

    `candidates` is every metric reported under this name, not one — a
    breakdown-by-date question reports many entries sharing a name, one per
    period, and the claim only has to match one of them.
    """
    value = str(claim.get("value"))
    period = claim.get("period")

    # Every side of every candidate is tried before anything is refused. A
    # genuinely flat metric carries the same value on both its own sides, and
    # the first side to match by value is not necessarily the side (or the
    # candidate) the claim meant — refusing there would reject a true claim
    # for citing the period it actually held.
    matched_value = False
    for metric in candidates:
        sides = (
            (str(metric.get("previous_value")), metric.get("previous_label")),
            (str(metric.get("current_value")), metric.get("current_label")),
        )
        for side_value, side_label in sides:
            if value != side_value:
                continue
            matched_value = True
            if side_label is None:
                # The aggregate named no period for this side, so the claim
                # cannot be held to one.
                return
            if period == side_label:
                return

    if not matched_value:
        raise UngroundedClaimError(
            f"Claim {position} states a value for {metric_name!r} that the "
            f"validated aggregate does not carry"
        )
    if period is None:
        raise UngroundedClaimError(
            f"Claim {position} states a value for {metric_name!r} without the "
            f"period it covers, which the aggregate names"
        )
    raise UngroundedClaimError(
        f"Claim {position} captions its value for {metric_name!r} with a "
        f"period the aggregate does not give that value"
    )


def _preserved_contradictions(
    draft: dict[str, Any],
    evaluator: dict[str, Any],
) -> list[str]:
    """Union, not replacement.

    A model that simply omits the Evaluator's concerns would otherwise produce
    a cleaner-looking draft than the evidence earned, and nothing downstream
    would know a disagreement had been dropped.
    """
    reported = [str(item) for item in draft.get("contradictions", [])]
    issues = [str(item) for item in evaluator.get("issues", [])]
    merged = list(reported)
    for issue in issues:
        if issue not in merged:
            merged.append(issue)
    return merged


def _bounded_confidence(draft: dict[str, Any], evaluator: dict[str, Any]) -> float:
    """Insight may be less sure than the recheck earned, never more."""
    claimed = draft.get("confidence")
    score = float(claimed) if isinstance(claimed, int | float) else 0.0
    score = min(max(score, 0.0), 1.0)

    outcome = _mapping(evaluator.get("outcome"))
    upstream = outcome.get("score")
    if isinstance(upstream, int | float):
        score = min(score, float(upstream))
    return score


def _upstream_evidence(
    analyst: dict[str, Any],
    evaluator: dict[str, Any],
) -> tuple[str, ...]:
    refs: list[str] = []
    for source in (analyst, evaluator):
        for ref in source.get("evidence_refs", []):
            if isinstance(ref, str) and ref not in refs:
                refs.append(ref)
    return tuple(refs)
