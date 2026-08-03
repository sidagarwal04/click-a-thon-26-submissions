"""The run-to-application adapter.

Everything else mocks the pipeline, so this seam was unguarded: a field renamed
on `PipelineOutcome` still type-checked and still passed every test, and only a
live run found it. These tests cost nothing and close that gap.

`_pipeline_result` is what `OrchestratorLoop.run()` ends on, so calling it
directly tests the same assembly the product uses without standing up a Board,
a Work Item queue and three Agents to reach it.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import (
    AgentExecutionRecord,
    AgentRole,
    ConfidenceOutcome,
    ExecutionStatus,
    LegacyRoleWriteError,
)

from zentra_api.outcomes import PipelineOutcome
from zentra_api.pipeline import (
    PostgresExecutionRecorder,
    _pipeline_result,
)

INVESTIGATION_ID = UUID("11000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("22000000-0000-0000-0000-000000000002")


EVIDENCE = None  # built lazily; see validated_evidence()


def validated_evidence():
    """What the Analyst measured. A claim can only be cited against this, so a
    test that omits it is testing the refusal path whether it meant to or not.
    """
    from uuid import UUID as _UUID

    from zentra_api.outcomes import ValidatedEvidence

    return (
        ValidatedEvidence(
            metric="refund_amount",
            previous_value="20.00",
            current_value="260.00",
            previous_period="June 2026",
            current_period="July 2026",
            filters=(
                {
                    "member": "Commerce.region",
                    "operator": "equals",
                    "values": ["EU"],
                },
            ),
            grain="month",
            producing_execution_id=_UUID("60000000-0000-0000-0000-000000000006"),
        ),
        ValidatedEvidence(
            metric="order_count",
            previous_value="480",
            current_value="486",
            previous_period="June 2026",
            current_period="July 2026",
            filters=(),
            grain="month",
            producing_execution_id=_UUID("60000000-0000-0000-0000-000000000006"),
        ),
    )


def insight_outcome(**overrides: object):
    from zentra_api.outcomes import InsightOutcome

    defaults: dict[str, object] = {
        "execution_id": UUID("70000000-0000-0000-0000-000000000007"),
        "headline": "EU refunds rose $240 in July.",
        "summary": "Governed EU refund amount rose from $20 to $260.",
        "claims": [
            {
                "kind": "observed",
                "text": "EU refund amount rose to $260.00.",
                "metric": "refund_amount",
                "value": "260.00",
                "period": "July 2026",
            },
            {
                "kind": "interpretation",
                "text": "Order volume barely moved.",
                "metric": "order_count",
                "value": None,
                "period": None,
            },
        ],
        "contradictions": ("Recheck counted 8 rows, not 12.",),
        "root_cause": "unresolved",
        "outcome": ConfidenceOutcome(
            score=0.42, calibration_method="insight_bounded_by_evaluator"
        ),
        "model": "nvidia/nemotron-3-ultra-550b-a55b",
        "fallbacks": ("gemini/gemini-3.6-flash: circuit open",),
    }
    return InsightOutcome(**(defaults | overrides))  # type: ignore[arg-type]


def outcome(**overrides: object) -> PipelineOutcome:
    defaults: dict[str, object] = {
        "headline": "EU refunds rose $240 in July.",
        "summary": "Governed EU refund amount rose from $20 to $260.",
        "metrics": [
            {
                "metric": "refund_amount",
                "previous_value": "20.00",
                "current_value": "260.00",
                "unit": "USD",
            }
        ],
        "evidence_refs": ("artifact://execution/abc",),
        "outcome": ConfidenceOutcome(score=0.9, calibration_method="self_reported"),
        "converged": True,
        "contradictions": (),
        "attempts": 1,
        "analyst_model": "gemini/gemini-3.6-flash",
        "evaluator_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "analyst_sample_size": 8,
        "evaluator_sample_size": 8,
        # The graph always produces one now; a fixture that omitted it
        # would be testing a pipeline the product no longer has.
        "insight": insight_outcome(),
        "evidence": validated_evidence(),
    }
    return PipelineOutcome(**(defaults | overrides))  # type: ignore[arg-type]


async def run(**overrides: object):
    return _pipeline_result(
        outcome(**overrides),
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
    )


@pytest.mark.asyncio
async def test_the_evidence_the_ceilings_need_survives_the_adapter() -> None:
    """Dropped silently, the application would grade every recheck as NONE and
    gate everything — or worse, cap nothing at all."""
    result = await run()

    assert result.analyst_model == "gemini/gemini-3.6-flash"
    assert result.evaluator_model == "nvidia/nemotron-3-ultra-550b-a55b"
    assert result.analyst_sample_size == 8
    assert result.evaluator_sample_size == 8


@pytest.mark.asyncio
async def test_the_finding_and_the_convergence_signal_survive_it_too() -> None:
    result = await run(converged=False, contradictions=("Recheck disagreed.",))

    assert result.finding.headline == "EU refunds rose $240 in July."
    assert result.finding.metrics[0].current_value == "260.00"
    assert result.finding.evidence_refs[0].value == "artifact://execution/abc"
    assert result.converged is False
    assert result.contradictions == ("Recheck disagreed.",)


@pytest.mark.asyncio
async def test_the_periods_a_metric_covers_survive_the_adapter() -> None:
    """Without these the UI has no period to render, and the one it invented
    captioned an October-November finding as June-July."""
    result = await run(
        metrics=[
            {
                "metric": "refund_amount",
                "previous_value": "20.00",
                "previous_label": "June 2026",
                "current_value": "260.00",
                "current_label": "July 2026",
                "unit": "USD",
            }
        ]
    )

    assert result.finding.metrics[0].previous_label == "June 2026"
    assert result.finding.metrics[0].current_label == "July 2026"


@pytest.mark.asyncio
@pytest.mark.parametrize("said_nothing", [None, "", "   "])
async def test_a_metric_that_names_no_period_reports_none(
    said_nothing: str | None,
) -> None:
    """A model may legitimately have no period to name. Stringifying its silence
    would caption the metric with an empty one, which is the bug again."""
    result = await run(
        metrics=[
            {
                "metric": "refund_rate",
                "previous_value": "25",
                "previous_label": said_nothing,
                "current_value": "75",
                "current_label": said_nothing,
                "unit": "percent",
            }
        ]
    )

    assert result.finding.metrics[0].previous_label is None
    assert result.finding.metrics[0].current_label is None


@pytest.mark.asyncio
async def test_a_recording_made_before_labels_existed_still_runs() -> None:
    """Cassettes predate the field. Requiring it would turn every old recording
    into a crash."""
    result = await run()

    assert result.finding.metrics[0].previous_label is None


@pytest.mark.asyncio
async def test_unknown_models_pass_through_as_unknown() -> None:
    """The application treats None as no claim of independence, so the adapter
    must not invent a value here."""
    result = await run(analyst_model=None, evaluator_model=None)

    assert result.analyst_model is None
    assert result.evaluator_model is None


def execution(role: AgentRole) -> AgentExecutionRecord:
    moment = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
    return AgentExecutionRecord(
        execution_id=uuid4(),
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        agent_id="insight_v1",
        role=role,
        step=3,
        input={"question": "Why did EU refunds increase?"},
        status=ExecutionStatus.SUCCESS,
        latency_ms=1200,
        started_at=moment,
        completed_at=moment,
    )


class ExplodingUnitOfWorkFactory:
    """Any use at all is a failure: the guard must refuse before the
    transaction opens, not after a partial write."""

    def __call__(self, *_: object) -> object:
        raise AssertionError("A legacy role reached the transaction")


@pytest.mark.asyncio
async def test_the_recorder_refuses_to_write_the_legacy_insight_role() -> None:
    """The role travels into the audit ledger's metadata, and Audit Entries are
    immutable — a legacy value written there could never be corrected."""
    recorder = PostgresExecutionRecorder(ExplodingUnitOfWorkFactory())  # type: ignore[arg-type]

    with pytest.raises(LegacyRoleWriteError, match="insight_root_cause"):
        await recorder.record(execution(AgentRole.INSIGHT_ROOT_CAUSE))


def test_the_audit_event_carries_the_canonical_role() -> None:
    from zentra_api.pipeline import _audit_event

    event = _audit_event(execution(AgentRole.INSIGHT))

    assert event.metadata["role"] == "insight"


@pytest.mark.asyncio
async def test_the_draft_names_the_execution_that_produced_it() -> None:
    """Attribution is the point of running Insight separately. A draft that
    cannot say which Agent Execution wrote it is no better than the
    Orchestrator's unattributed narrative."""
    result = await run()

    draft = result.draft_finding
    assert draft is not None
    assert draft.produced_by_execution_id == UUID(
        "70000000-0000-0000-0000-000000000007"
    )
    assert draft.investigation_id == INVESTIGATION_ID
    assert draft.tenant_id == TENANT_ID


@pytest.mark.asyncio
async def test_claim_order_and_kind_survive_the_adapter() -> None:
    result = await run()

    claims = result.draft_finding.claims
    assert [c.position for c in claims] == [0, 1]
    assert [c.kind.value for c in claims] == ["observed", "interpretation"]
    assert claims[0].text == "EU refund amount rose to $260.00."
    # The observed claim cites its measurement; the interpretation cites none
    # of its own, because it is a reading of someone else's.
    assert len(claims[0].citation_ids) == 1
    assert claims[1].citation_ids == ()


@pytest.mark.asyncio
async def test_contradictions_and_unresolved_root_cause_survive_the_adapter() -> None:
    result = await run()

    draft = result.draft_finding
    assert draft.root_cause.value == "unresolved"
    assert [c.detail for c in draft.contradictions] == [
        "Recheck counted 8 rows, not 12."
    ]
    assert draft.contradictions[0].resolved is False


@pytest.mark.asyncio
async def test_the_bounded_confidence_carries_its_calibration_reason() -> None:
    result = await run()

    confidence = result.draft_finding.confidence
    assert confidence is not None
    assert confidence.score == 0.42
    assert confidence.calibration_method == "insight_bounded_by_evaluator"


@pytest.mark.asyncio
async def test_every_run_produces_a_draft_finding() -> None:
    """There is no path left that does not. The Orchestrator no longer writes
    a conclusion, so a run reaching the end without a draft would be a Finding
    nobody was evaluated for."""
    result = await run()

    assert result.draft_finding is not None
    assert result.finding.headline == result.draft_finding.headline


@pytest.mark.asyncio
async def test_a_citation_is_built_from_upstream_state_not_from_insight() -> None:
    """The whole reason a Citation is evidence rather than a second account of
    the claim. Every field here comes from what the Analyst actually ran."""
    result = await run()

    citation = result.evidence_citations[0]
    assert citation.metric == "refund_amount"
    assert citation.grain == "month"
    assert citation.filters[0].member == "Commerce.region"
    assert citation.filters[0].values == ("EU",)
    assert citation.producing_execution_id == UUID(
        "60000000-0000-0000-0000-000000000006"
    )
    # Copied from the validated aggregate, not restated by the model. A
    # citation whose figure could differ from the claim's would be worse than
    # no citation: it would look like corroboration.
    assert citation.aggregate_value == "260.00"
    assert citation.evaluator_outcome is not None


@pytest.mark.asyncio
async def test_two_claims_about_the_same_measurement_share_one_citation() -> None:
    """Duplicating it would let the two drift."""
    twice = insight_outcome(
        claims=[
            {
                "kind": "observed",
                "text": "EU refunds reached $260.00.",
                "metric": "refund_amount",
                "value": "260.00",
                "period": "July 2026",
            },
            {
                "kind": "observed",
                "text": "That is a $240 rise.",
                "metric": "refund_amount",
                "value": "260.00",
                "period": "July 2026",
            },
        ]
    )

    result = await run(insight=twice, evidence=validated_evidence())

    assert len(result.evidence_citations) == 1
    first, second = result.draft_finding.claims
    assert first.citation_ids == second.citation_ids


@pytest.mark.asyncio
async def test_the_two_sides_of_a_comparison_are_separate_citations() -> None:
    """Different measurements, so different evidence — and each carries the
    figure for its own period."""
    both = insight_outcome(
        claims=[
            {
                "kind": "observed",
                "text": "EU refunds were $20.00 in June.",
                "metric": "refund_amount",
                "value": "20.00",
                "period": "June 2026",
            },
            {
                "kind": "observed",
                "text": "EU refunds were $260.00 in July.",
                "metric": "refund_amount",
                "value": "260.00",
                "period": "July 2026",
            },
        ]
    )

    result = await run(insight=both, evidence=validated_evidence())

    by_period = {c.period: c.aggregate_value for c in result.evidence_citations}
    assert by_period == {"June 2026": "20.00", "July 2026": "260.00"}


@pytest.mark.asyncio
async def test_a_claim_with_no_validated_evidence_cannot_be_cited() -> None:
    """Upstream state and the draft disagreeing is not something to paper over
    with an empty citation list."""
    from zentra_api.pipeline import UncitableClaimError

    with pytest.raises(UncitableClaimError):
        await run(insight=insight_outcome(), evidence=())


@pytest.mark.asyncio
async def test_no_citation_carries_a_prohibited_payload() -> None:
    """Rows, prompts, credentials and hidden reasoning must be absent from
    citation metadata. This is the regression that stops a future field from
    quietly widening what a citation exposes."""
    import json

    result = await run()

    # The dataclass itself, not a hand-built projection of it: a projection
    # cannot catch a field somebody widens the citation with later.
    serialised = json.dumps(
        [asdict(citation) for citation in result.evidence_citations],
        default=str,
    ).lower()

    for prohibited in (
        "rows",
        "prompt",
        "system",
        "api_key",
        "secret",
        "credential",
        "token",
        "reasoning",
    ):
        assert prohibited not in serialised, f"{prohibited} reached a citation"
