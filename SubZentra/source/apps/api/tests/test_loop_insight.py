"""Insight's place in the loop: after the Evaluator, once, and attributable.

Ported from `libs/adapters/langgraph/tests/test_graph_insight.py`. The graph
enforced the ordering with a conditional edge; `OrchestratorLoop` enforces it by
running Insight only once the retry loop has broken. The property is the same
and matters more than the mechanism, so the tests came with it.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from zentra_adapter_langgraph.constants import MAX_EVALUATION_ATTEMPTS
from zentra_domain_agent_execution import (
    AgentDescriptor,
    AgentInput,
    AgentOutput,
    AgentRole,
)

from .loop_harness import ROLE_MODELS, build_loop, keys, run


class RefusingInsight:
    """An Insight that cannot answer.

    A stub satisfying `AgentPort` rather than a subclass of `InsightAgent`:
    inheriting the real agent only to override its one method binds the test to
    a concrete class it is not testing.
    """

    descriptor = AgentDescriptor(
        agent_id="insight_v1",
        role=AgentRole.INSIGHT,
        tool_permissions=(),
        context_budget_tokens=16000,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        output_fields=frozenset(),
        eval_suite_ref="evals/insight",
    )

    async def invoke(self, agent_input: AgentInput) -> AgentOutput:
        raise RuntimeError("provider chain exhausted")


@pytest.mark.asyncio
async def test_insight_runs_after_the_evaluator_and_only_once() -> None:
    """Order is the whole point. Drafting before the recheck settles would
    conclude from evidence the Evaluator is about to reject."""
    loop, recorder, _ = build_loop(recheck_passed=True)

    result = await run(loop)

    assert [record.role for record in recorder.records] == [
        AgentRole.CUBE_ANALYST,
        AgentRole.EVALUATOR,
        AgentRole.INSIGHT,
    ]
    assert result.draft_finding is not None


@pytest.mark.asyncio
async def test_insight_does_not_draft_from_a_rejected_attempt() -> None:
    """Three failed rechecks, one Insight execution — at the end, on the
    terminal outcome, not once per attempt."""
    loop, recorder, _ = build_loop(recheck_passed=False)

    await run(loop)

    insight_runs = [r for r in recorder.records if r.role is AgentRole.INSIGHT]
    evaluator_runs = [r for r in recorder.records if r.role is AgentRole.EVALUATOR]
    assert len(evaluator_runs) == MAX_EVALUATION_ATTEMPTS
    assert len(insight_runs) == 1
    # And it ran after the last of them.
    assert recorder.records.index(insight_runs[0]) > recorder.records.index(
        evaluator_runs[-1]
    )


@pytest.mark.asyncio
async def test_insight_records_its_own_execution_and_attribution() -> None:
    loop, recorder, _ = build_loop(
        recheck_passed=True,
        fallbacks=("gemini/gemini-3-flash: circuit open",),
    )

    result = await run(loop)

    record = next(r for r in recorder.records if r.role is AgentRole.INSIGHT)
    assert record.agent_id == "insight_v1"
    assert record.usage.model == ROLE_MODELS["insight"]
    assert record.usage.input_tokens == 100
    assert record.usage.cost_usd == Decimal("0.001")
    assert record.latency_ms >= 0
    assert record.fallbacks == ("gemini/gemini-3-flash: circuit open",)
    assert record.status.value == "success"

    # The Draft Finding has to be able to name the execution that produced it,
    # so the id the recorder saw and the id the draft reports must agree.
    assert result.draft_finding is not None
    assert result.draft_finding.produced_by_execution_id == record.execution_id


@pytest.mark.asyncio
async def test_exactly_one_execution_owns_the_draft_finding() -> None:
    """The point of the contraction. One Insight execution, and it draws the
    conclusion — and no Agent plans, because the loop does."""
    loop, recorder, _ = build_loop(recheck_passed=True)

    result = await run(loop)

    drafters = [r for r in recorder.records if r.role is AgentRole.INSIGHT]
    planners = [r for r in recorder.records if r.role is AgentRole.ORCHESTRATOR]

    assert len(drafters) == 1
    assert planners == []
    assert result.draft_finding.produced_by_execution_id == drafters[0].execution_id


@pytest.mark.asyncio
async def test_insight_never_receives_raw_result_rows() -> None:
    """`rows` is the one field that must not travel between agents. Insight is
    downstream of everything, so it is the most likely place to leak."""
    loop, recorder, _ = build_loop(recheck_passed=True)

    await run(loop)

    record = next(r for r in recorder.records if r.role is AgentRole.INSIGHT)

    # A key check, not a substring one: governed measure names like
    # `Commerce.refundAmount` legitimately appear in the query plan, so
    # searching the serialised blob for them would fail on evidence that is
    # meant to be there. What must not appear, at any depth, is `rows`.
    assert keys(record.input).isdisjoint({"rows"})
    # And the aggregate value the analyst measured is present — Insight needs
    # it to check a claim — while the row it came from is not.
    assert "260.00" in json.dumps(record.input)
    # The pointers that lead to the rows are present, which is what makes the
    # evidence reachable without copying it.
    assert "artifact://execution/" in json.dumps(record.input)


@pytest.mark.asyncio
async def test_the_finding_comes_from_the_agent_evaluated_for_writing_it() -> None:
    """The headline a reader sees is the one Insight produced under its own
    evaluation suite, not one an unevaluated second call invented."""
    loop, _, _ = build_loop(recheck_passed=True)

    result = await run(loop)

    assert result.draft_finding is not None
    assert result.finding.headline == result.draft_finding.headline
    assert result.finding.summary == result.draft_finding.summary
    assert result.contradictions == tuple(
        contradiction.detail for contradiction in result.draft_finding.contradictions
    )


@pytest.mark.asyncio
async def test_a_failing_insight_fails_the_run_closed() -> None:
    """Not a degraded finding. A draft that could not be produced must not be
    replaced by one nobody attributed."""
    loop, recorder, _ = build_loop(recheck_passed=True, insight=RefusingInsight())

    with pytest.raises(RuntimeError, match="provider chain exhausted"):
        await run(loop)

    # The failure is recorded before it propagates, so Replay can show it.
    failed = next(r for r in recorder.records if r.role is AgentRole.INSIGHT)
    assert failed.status.value == "failure"
    assert failed.errors == ("RuntimeError: provider chain exhausted",)


@pytest.mark.asyncio
async def test_an_unresolved_root_cause_is_reported_as_unresolved() -> None:
    loop, _, _ = build_loop(recheck_passed=True)

    result = await run(loop)

    assert result.draft_finding.root_cause.value == "unresolved"


@pytest.mark.asyncio
async def test_insight_announces_its_start_before_the_model_call() -> None:
    """A step that hangs, or a process killed mid-call, writes no completion.
    Replay showing nothing there would be indistinguishable from the step never
    having been attempted."""
    loop, recorder, _ = build_loop(recheck_passed=True)

    await run(loop)

    start = next(s for s in recorder.starts if s.role is AgentRole.INSIGHT)
    completion = next(r for r in recorder.records if r.role is AgentRole.INSIGHT)
    assert start.execution_id == completion.execution_id
    assert start.agent_id == "insight_v1"
    assert start.step == completion.step
    # Every step announces itself, not only Insight.
    assert len(recorder.starts) == len(recorder.records)


@pytest.mark.asyncio
async def test_a_failed_insight_still_announced_its_start() -> None:
    """The case the start event exists for: a completion that says `failure`
    is a luxury. A crash gives you only the start."""
    loop, recorder, _ = build_loop(recheck_passed=True, insight=RefusingInsight())

    with pytest.raises(RuntimeError):
        await run(loop)

    assert any(s.role is AgentRole.INSIGHT for s in recorder.starts)


@pytest.mark.asyncio
async def test_no_audit_event_carries_evidence_content() -> None:
    """The surface that is immutable. An Audit Entry with a customer figure in
    it could never be corrected."""
    loop, recorder, _ = build_loop(recheck_passed=True)

    await run(loop)

    # What `PostgresExecutionRecorder` turns into metadata-only DomainEvents.
    from zentra_api.pipeline import _audit_event, _started_event

    for start in recorder.starts:
        payload = json.dumps(_started_event(start).metadata).lower()
        assert "260.00" not in payload
        assert "refund" not in payload

    for record in recorder.records:
        metadata = json.dumps(_audit_event(record).metadata).lower()
        # Process metadata only: identity, timings, usage, fallbacks.
        assert "260.00" not in metadata
        assert "claims" not in metadata
        assert "headline" not in metadata
        for prohibited in ("rows", "prompt", "reasoning", "credential", "secret"):
            assert prohibited not in metadata
