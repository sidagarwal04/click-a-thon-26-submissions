"""What the real Agents do when the Orchestrator Loop drives them.

Ported from `libs/adapters/langgraph/tests/test_graph.py`, which asserted the
same things through `InvestigationGraph`. ADR-0026 replaced the mechanism; the
Agents and the properties below are unchanged, so the tests moved rather than
went away.
"""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from zentra_adapter_langgraph.constants import MAX_EVALUATION_ATTEMPTS
from zentra_domain_agent_execution import AgentRole, ConfidenceOutcome

from .loop_harness import METRICS, build_loop, keys, run


@pytest.mark.asyncio
async def test_cancellation_is_checked_before_and_after_every_agent_call() -> None:
    """The capability the LangGraph deletion nearly took with it: without a
    checkpoint between Work Items, a cancelled run keeps paying for Agents
    until the whole three-attempt trust loop has finished."""
    checks = 0

    async def checkpoint(_: UUID, __: UUID) -> None:
        nonlocal checks
        checks += 1
        if checks == 2:
            raise RuntimeError("cancelled at safe checkpoint")

    loop, recorder, _ = build_loop(
        recheck_passed=True, cancellation_checkpoint=checkpoint
    )

    with pytest.raises(RuntimeError, match="safe checkpoint"):
        await run(loop)

    assert checks == 2
    # The Analyst's step is durable before the cancellation lands, so Replay
    # still shows exactly what had run.
    assert len(recorder.records) == 1


@pytest.mark.asyncio
async def test_converged_run_produces_a_confidence_capped_by_the_recheck() -> None:
    loop, recorder, _ = build_loop(recheck_passed=True)

    result = await run(loop)

    assert result.converged is True
    assert isinstance(result.outcome, ConfidenceOutcome)
    # 0.86 recheck, capped at the analyst's own 0.88 — the cap does not bite here.
    assert result.outcome.score == pytest.approx(0.86)
    assert result.contradictions == ()
    measured = result.finding.metrics[0]
    assert measured.metric == METRICS[0]["metric"]
    assert measured.previous_value == METRICS[0]["previous_value"]
    assert measured.current_value == METRICS[0]["current_value"]
    # Analyze, evaluate, draft. There is no planning execution any more: the
    # loop owns sequencing, so nothing asks a model what to do next.
    assert [record.role for record in recorder.records] == [
        AgentRole.CUBE_ANALYST,
        AgentRole.EVALUATOR,
        AgentRole.INSIGHT,
    ]


@pytest.mark.asyncio
async def test_failing_recheck_exits_at_exactly_three_attempts() -> None:
    loop, recorder, _ = build_loop(recheck_passed=False)

    result = await run(loop)

    assert result.converged is False
    # The Evaluator's own issues, preserved by Insight rather than restated
    # by a second model.
    assert result.contradictions == ("Figures disagree.",)
    assert isinstance(result.outcome, ConfidenceOutcome)
    assert result.outcome.score < 0.5
    evaluations = [
        record for record in recorder.records if record.role is AgentRole.EVALUATOR
    ]
    assert len(evaluations) == MAX_EVALUATION_ATTEMPTS


@pytest.mark.asyncio
async def test_evidence_pointers_reference_the_recorded_executions() -> None:
    loop, recorder, _ = build_loop(recheck_passed=True)

    result = await run(loop)

    recorded = {f"artifact://execution/{r.execution_id}" for r in recorder.records}
    references = {reference.value for reference in result.finding.evidence_refs}
    assert references <= recorded
    assert len(references) == 2


@pytest.mark.asyncio
async def test_result_rows_never_leave_the_execution_record() -> None:
    loop, recorder, _ = build_loop(recheck_passed=True)

    await run(loop)

    analyst = next(r for r in recorder.records if r.role is AgentRole.CUBE_ANALYST)
    assert analyst.output is not None
    assert analyst.output["rows"] == [{"Commerce.refundAmount": "260.00"}]
    # The Agent downstream of it is handed the state object; rows are absent.
    insight = recorder.records[-1]
    assert "rows" not in json.dumps(insight.input)


@pytest.mark.asyncio
async def test_the_analyst_only_ever_reaches_the_governed_catalog() -> None:
    """`StubSemanticLayer` rejects an ungoverned member before it runs, so a
    query reaching it at all is a query the catalog defines."""
    loop, _, layer = build_loop(recheck_passed=True)

    await run(loop)

    assert layer.queries
    for query in layer.queries:
        assert query.measures == ("Commerce.refundAmount",)


@pytest.mark.asyncio
async def test_the_retried_analyst_is_told_what_the_recheck_disagreed_with() -> None:
    """What makes this an optimizer loop rather than a plain repeat."""
    loop, recorder, _ = build_loop(recheck_passed=False)

    await run(loop)

    retries = [
        record
        for record in recorder.records
        if record.role is AgentRole.CUBE_ANALYST and "previous_issues" in record.input
    ]
    assert len(retries) == MAX_EVALUATION_ATTEMPTS - 1
    assert retries[0].input["previous_issues"] == ["Figures disagree."]


@pytest.mark.asyncio
async def test_executions_carry_token_and_cost_attribution() -> None:
    loop, recorder, _ = build_loop(recheck_passed=True)

    await run(loop)

    analyst = next(r for r in recorder.records if r.role is AgentRole.CUBE_ANALYST)
    assert analyst.usage.input_tokens == 200
    assert analyst.usage.output_tokens == 40
    assert analyst.usage.cost_usd > 0
    assert analyst.usage.model == "cerebras/zai-glm-4.7"
    evaluator = next(r for r in recorder.records if r.role is AgentRole.EVALUATOR)
    # Evaluator deliberately runs a different model family from the analyst, so
    # the recheck cannot inherit the same blind spots.
    assert evaluator.usage.model != analyst.usage.model


@pytest.mark.asyncio
async def test_every_execution_record_carries_the_rungs_that_failed() -> None:
    """Without this the ledger shows only the provider that answered, and the
    live run's three-deep fall-through had to be reconstructed by hand."""
    loop, recorder, _ = build_loop(
        recheck_passed=True,
        fallbacks=("cerebras:zai-glm-4.7: returned 402",),
    )

    await run(loop)

    assert recorder.records
    for record in recorder.records:
        assert record.fallbacks == ("cerebras:zai-glm-4.7: returned 402",)


@pytest.mark.asyncio
async def test_no_agent_state_carries_result_rows_at_any_depth() -> None:
    """`rows` is the one field that must not travel between Agents, and the
    check is on keys rather than substrings: governed measure names legitimately
    appear in a query plan."""
    loop, recorder, _ = build_loop(recheck_passed=True)

    await run(loop)

    for record in recorder.records:
        assert keys(record.input).isdisjoint({"rows"})
