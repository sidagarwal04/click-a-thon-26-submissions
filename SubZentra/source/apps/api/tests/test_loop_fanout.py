"""Fan-out: the loop asking what else is worth measuring, and deciding by rule.

ADR-0026's Phase 3. The Board stops being a record of one measurement and
becomes the thing the investigation reasons over: follow-ups run against it
concurrently, their Facts land beside the primary one, and a disagreement
between two of them is a Conflict nobody would have seen while each result
lived only inside its own Agent.

The acceptance rules are tested directly against `_accept` rather than through
a run, because they are the part that must not be model output.
"""

from __future__ import annotations

import pytest
from zentra_domain_agent_execution import AgentRole, ConfidenceOutcome
from zentra_domain_investigation import (
    ConflictStatus,
    GapPriority,
    WorkItemStatus,
)

from zentra_api.orchestrator_loop import (
    MAX_FANOUT_WORK_ITEMS,
    UnsettledConflictError,
    _accept,
    _require_settled_conflicts,
)

from .loop_harness import QUESTION, board_store, build_loop, run

BY_REGION = {"role": "cube_analyst", "objective": "Which region drove the rise?"}
BY_CHANNEL = {"role": "cube_analyst", "objective": "Which channel drove the rise?"}


# -- the rules ------------------------------------------------------------


def test_a_proposal_naming_a_role_with_no_runtime_is_rejected() -> None:
    """`forecaster` is a declared role with no implementation. Accepting one
    would queue a Work Item nobody can ever run."""
    proposals = [{"role": "forecaster", "objective": "Project next quarter."}]

    assert _accept(proposals, question=QUESTION, limit=3) == ()


def test_a_proposal_restating_the_question_is_rejected() -> None:
    """It would spend a second measurement re-deriving the answer the primary
    Analyst already has."""
    proposals = [{"role": "cube_analyst", "objective": f"  {QUESTION.upper()}  "}]

    assert _accept(proposals, question=QUESTION, limit=3) == ()


def test_two_proposals_asking_the_same_thing_are_accepted_once() -> None:
    assert _accept([BY_REGION, dict(BY_REGION)], question=QUESTION, limit=3) == (
        BY_REGION["objective"],
    )


def test_a_proposal_with_no_objective_is_rejected() -> None:
    proposals = [{"role": "cube_analyst", "objective": "   "}, BY_REGION]

    assert _accept(proposals, question=QUESTION, limit=3) == (BY_REGION["objective"],)


def test_the_cap_truncates_proposals_that_are_already_legitimate() -> None:
    """The cap is applied last, so a junk proposal arriving first cannot
    consume a slot a real one would have used."""
    junk = {"role": "forecaster", "objective": "Project next quarter."}

    accepted = _accept([junk, BY_REGION, BY_CHANNEL], question=QUESTION, limit=1)

    assert accepted == (BY_REGION["objective"],)


def test_the_default_cap_is_small_enough_to_be_a_budget() -> None:
    """A number nobody chose is not a budget. This is the seam a per-Tenant
    one lands on, so it must stay conspicuous."""
    assert 1 <= MAX_FANOUT_WORK_ITEMS <= 5


# -- fan-out end to end ---------------------------------------------------


@pytest.mark.asyncio
async def test_a_run_with_no_planner_fans_out_to_nothing() -> None:
    """The Phase 1 shape, still reachable: the eval replay harness wires no
    planner, and a run without one must behave exactly as it did."""
    loop, recorder, _ = build_loop(recheck_passed=True)

    await run(loop)

    assert [r.role for r in recorder.records] == [
        AgentRole.CUBE_ANALYST,
        AgentRole.EVALUATOR,
        AgentRole.INSIGHT,
    ]


@pytest.mark.asyncio
async def test_accepted_proposals_become_rechecked_child_measurements() -> None:
    """A follow-up earns the same Evaluator recheck the primary question does.
    Evidence nobody rechecked is not evidence this product will cite."""
    loop, recorder, _ = build_loop(recheck_passed=True, tasks=[BY_REGION, BY_CHANNEL])

    await run(loop)

    analysts = [r for r in recorder.records if r.role is AgentRole.CUBE_ANALYST]
    evaluators = [r for r in recorder.records if r.role is AgentRole.EVALUATOR]
    planners = [r for r in recorder.records if r.role is AgentRole.ORCHESTRATOR]
    assert len(planners) == 1
    # One primary plus two children, each with its own recheck.
    assert len(analysts) == 3
    assert len(evaluators) == 3


@pytest.mark.asyncio
async def test_a_child_work_item_names_the_measurement_it_came_from() -> None:
    """The emergent graph: edges the Board grew, not a DAG drawn in advance."""
    loop, _, _ = build_loop(recheck_passed=True, tasks=[BY_REGION])

    await run(loop)

    items = board_store(loop)["items"].values()
    analysts = [i for i in items if i.role is AgentRole.CUBE_ANALYST]
    primary = next(i for i in analysts if i.parent_work_item_id is None)
    child = next(i for i in analysts if i.parent_work_item_id is not None)

    assert child.parent_work_item_id == primary.work_item_id
    assert primary.work_item_id in child.depends_on
    assert child.objective == BY_REGION["objective"]


@pytest.mark.asyncio
async def test_every_accepted_proposal_opens_a_knowledge_gap() -> None:
    """A follow-up is something the Board does not yet know, and only the
    question the user asked is allowed to be HIGH."""
    loop, _, _ = build_loop(recheck_passed=True, tasks=[BY_REGION, BY_CHANNEL])

    await run(loop)

    gaps = board_store(loop)["gaps"].values()
    priorities = sorted(gap.priority for gap in gaps)
    assert len(gaps) == 3
    assert priorities == sorted(
        [GapPriority.HIGH, GapPriority.MEDIUM, GapPriority.MEDIUM]
    )
    assert all(gap.resolved for gap in gaps)


@pytest.mark.asyncio
async def test_the_cap_bounds_what_one_investigation_may_spend() -> None:
    loop, recorder, _ = build_loop(
        recheck_passed=True,
        tasks=[BY_REGION, BY_CHANNEL],
        max_fanout=1,
    )

    await run(loop)

    analysts = [r for r in recorder.records if r.role is AgentRole.CUBE_ANALYST]
    assert len(analysts) == 2


@pytest.mark.asyncio
async def test_a_cap_of_zero_turns_fan_out_off_without_skipping_the_answer() -> None:
    loop, recorder, _ = build_loop(recheck_passed=True, tasks=[BY_REGION], max_fanout=0)

    result = await run(loop)

    assert [r.role for r in recorder.records] == [
        AgentRole.CUBE_ANALYST,
        AgentRole.EVALUATOR,
        AgentRole.INSIGHT,
    ]
    assert result.finding.headline == "EU refunds rose $240 in July."


@pytest.mark.asyncio
async def test_every_step_in_a_fanned_out_run_has_a_distinct_ledger_position() -> None:
    """Concurrent branches share one counter. Two Work Items landing on the
    same step would make Replay's ordering a lie."""
    loop, recorder, _ = build_loop(recheck_passed=True, tasks=[BY_REGION, BY_CHANNEL])

    await run(loop)

    steps = [record.step for record in recorder.records]
    assert len(steps) == len(set(steps))


@pytest.mark.asyncio
async def test_a_failing_follow_up_does_not_sink_the_primary_answer() -> None:
    """The user asked one question. A follow-up nobody asked for failing must
    not cost them the answer to it."""
    loop, recorder, _ = build_loop(
        recheck_passed=True,
        tasks=[BY_REGION],
        # The primary Analyst interprets first; the provider then falls over
        # inside the child's branch and only there.
        failing_analysis=1,
    )

    result = await run(loop)

    assert result.draft_finding is not None
    assert result.finding.headline == "EU refunds rose $240 in July."
    assert any(r.role is AgentRole.INSIGHT for r in recorder.records)
    # And the gap it was meant to close stays open, because it did not close
    # it. A Board that marked it resolved would agree with itself by
    # construction.
    unanswered = [g for g in board_store(loop)["gaps"].values() if not g.resolved]
    assert [gap.description for gap in unanswered] == [BY_REGION["objective"]]


# -- the registry gate ----------------------------------------------------


@pytest.mark.asyncio
async def test_a_run_refuses_when_a_required_role_is_not_promoted() -> None:
    """The fail-closed property Phase 2 left unenforced. Nothing but Insight
    writes a Finding, so a deployment whose registry has not promoted one must
    refuse rather than reach the end with nothing to draft."""
    from zentra_adapter_langgraph import NoEnabledAgentError

    loop, recorder, _ = build_loop(
        recheck_passed=True,
        tasks=[BY_REGION],
        promoted=(AgentRole.CUBE_ANALYST, AgentRole.EVALUATOR),
    )

    with pytest.raises(NoEnabledAgentError, match="insight"):
        await run(loop)

    # And it refused before spending: no measurement was taken.
    assert [r.role for r in recorder.records] == [AgentRole.ORCHESTRATOR]
    assert recorder.records[0].status.value == "failure"


# -- conflicts ------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_follow_up_disagreeing_with_the_primary_opens_a_conflict() -> None:
    """The whole point of a shared Board. Two measurements of the same metric
    over the same period that disagree is a contradiction, and it is only
    visible because both landed in one place."""
    loop, _, _ = build_loop(
        recheck_passed=True,
        tasks=[BY_REGION],
        measured_values=("260.00", "98000.00"),
    )

    await run(loop)

    conflicts = list(board_store(loop)["conflicts"].values())
    assert len(conflicts) == 1
    assert "260.00" in conflicts[0].description
    assert "98000.00" in conflicts[0].description


@pytest.mark.asyncio
async def test_a_conflict_is_documented_rather_than_silently_resolved() -> None:
    """The loop has no evidence to say which measurement was right — a third
    query would be a third opinion, not an arbiter. Picking a side silently
    is the failure this records instead."""
    loop, _, _ = build_loop(
        recheck_passed=True,
        tasks=[BY_REGION],
        measured_values=("260.00", "98000.00"),
    )

    await run(loop)

    conflict = next(iter(board_store(loop)["conflicts"].values()))
    assert conflict.status is ConflictStatus.DOCUMENTED
    assert conflict.resolution
    # Not RESOLVED: that would claim the disagreement was settled.
    assert conflict.status is not ConflictStatus.RESOLVED


@pytest.mark.asyncio
async def test_a_documented_conflict_reaches_the_reader() -> None:
    """Insight drafts from the primary measurement alone and never saw the
    follow-up. A contradiction discovered and then filed where nobody reads
    would be worse than not having looked."""
    loop, _, _ = build_loop(
        recheck_passed=True,
        tasks=[BY_REGION],
        measured_values=("260.00", "98000.00"),
    )

    result = await run(loop)

    assert any("98000.00" in detail for detail in result.contradictions)


@pytest.mark.asyncio
async def test_a_follow_up_agreeing_is_corroboration_not_a_conflict() -> None:
    loop, _, _ = build_loop(recheck_passed=True, tasks=[BY_REGION])

    result = await run(loop)

    assert board_store(loop)["conflicts"] == {}
    assert result.contradictions == ()


@pytest.mark.asyncio
async def test_both_measurements_survive_a_disagreement() -> None:
    """A Fact is immutable. The loser of a conflict is not deleted, or Replay
    could never show what the Board believed."""
    loop, _, _ = build_loop(
        recheck_passed=True,
        tasks=[BY_REGION],
        measured_values=("260.00", "98000.00"),
    )

    await run(loop)

    values = {fact.value for fact in board_store(loop)["facts"]}
    assert values == {"260.00", "98000.00"}


def test_insight_may_not_be_reached_with_an_open_contradiction() -> None:
    """`_document_conflicts` settles everything immediately before this runs,
    so today it cannot fire — it guards the path that does not exist yet."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from zentra_domain_investigation import Conflict, InvestigationBoard

    board = InvestigationBoard.create(
        board_id=uuid4(),
        investigation_id=uuid4(),
        tenant_id=uuid4(),
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )
    board.open_conflict(
        Conflict(conflict_id=uuid4(), description="two values"),
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )

    with pytest.raises(UnsettledConflictError):
        _require_settled_conflicts(board)


@pytest.mark.asyncio
async def test_a_fanned_out_run_still_completes_every_work_item() -> None:
    loop, _, _ = build_loop(recheck_passed=True, tasks=[BY_REGION, BY_CHANNEL])

    await run(loop)

    items = board_store(loop)["items"].values()
    # One planner, three Analysts (primary + two children), a recheck each,
    # and one Insight.
    assert len(items) == 8
    assert all(item.status is WorkItemStatus.COMPLETED for item in items)


# -- completion (Phase 4) -------------------------------------------------


@pytest.mark.asyncio
async def test_a_converged_run_records_itself_complete_on_the_board() -> None:
    """The Board was created and then never updated: its confidence and
    narrative columns were written once at insert and never again."""
    loop, _, _ = build_loop(recheck_passed=True)

    await run(loop)

    board = next(iter(board_store(loop)["boards"].values()))
    assert board.confidence is not None
    assert board.confidence.threshold == 0.7
    assert board.narrative.startswith("Complete")


@pytest.mark.asyncio
async def test_an_unconverged_run_says_it_stopped_rather_than_finished() -> None:
    """Three failed rechecks still produce a Draft Finding — publication
    policy decides whether it may be shown. What must not happen is the Board
    presenting that run as a finished investigation."""
    loop, _, _ = build_loop(recheck_passed=False)

    result = await run(loop)

    board = next(iter(board_store(loop)["boards"].values()))
    assert result.draft_finding is not None
    assert "evidence_unvalidated" in board.narrative
    assert "budget exhausted" in board.narrative


@pytest.mark.asyncio
async def test_the_board_never_records_a_higher_confidence_than_the_finding() -> None:
    """The Evaluator's score is capped at the Analyst's but not by sample size
    or by how independent the recheck was. Recording it raw would leave the
    Board more confident than the Finding built from it."""
    loop, _, _ = build_loop(recheck_passed=True)

    result = await run(loop)

    board = next(iter(board_store(loop)["boards"].values()))
    assert isinstance(result.outcome, ConfidenceOutcome)
    assert board.confidence.score <= result.outcome.score


@pytest.mark.asyncio
async def test_the_narrative_carries_no_evidence() -> None:
    """It is persisted and shown to operators. Blocker names only."""
    loop, _, _ = build_loop(
        recheck_passed=True,
        tasks=[BY_REGION],
        measured_values=("260.00", "98000.00"),
    )

    await run(loop)

    board = next(iter(board_store(loop)["boards"].values()))
    assert "260.00" not in board.narrative
    assert "98000.00" not in board.narrative
    assert "refund" not in board.narrative.lower()
