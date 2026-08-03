from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from zentra_domain_agent_execution import (
    CANONICAL_ROLES,
    LEGACY_ROLES,
    AgentDescriptor,
    AgentExecutionRecord,
    AgentInput,
    AgentOutput,
    AgentRole,
    ConfidenceOutcome,
    ExecutionStatus,
    ExecutionUsage,
    LegacyRoleWriteError,
    RegisteredAgent,
    ToolAccess,
    ToolScope,
    ValidationOutcome,
    reject_legacy_role,
    validate_agent_output,
)


class StubAgent:
    descriptor = AgentDescriptor(
        agent_id="cube_analyst_v1",
        role=AgentRole.CUBE_ANALYST,
        tool_permissions=(
            ToolScope(tool_name="semantic_layer_query", access=ToolAccess.READ),
        ),
        context_budget_tokens=4_000,
        input_schema=AgentInput.model_json_schema(),
        output_schema=AgentOutput.model_json_schema(),
        output_fields=frozenset({"sql", "result_summary"}),
        eval_suite_ref="evals/cube_analyst_v1.yaml",
    )

    async def invoke(self, agent_input: AgentInput) -> AgentOutput:
        return AgentOutput(
            fields={"sql": "SELECT 1", "result_summary": "one"},
            outcome=ConfidenceOutcome(
                score=0.9,
                calibration_method="schema_and_execution_agreement",
            ),
        )


def test_contract_generates_discriminated_json_schema() -> None:
    schema = AgentOutput.model_json_schema()

    assert "discriminator" in str(schema)
    assert "confidence" in str(schema)
    assert "validation" in str(schema)


def test_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ConfidenceOutcome(score=1.01, calibration_method="test")


def test_validation_outcome_does_not_fabricate_confidence() -> None:
    output = AgentOutput(
        fields={"task_ledger_valid": True},
        outcome=ValidationOutcome(passed=True, checks=("task_schema",)),
    )

    assert output.outcome.kind == "validation"
    assert not hasattr(output.outcome, "score")


def test_evidence_references_are_metadata_only_artifact_pointers() -> None:
    output = AgentOutput(
        fields={"claim": "Refunds increased"},
        evidence_refs=("artifact://query/q_123",),
        outcome=ConfidenceOutcome(score=0.8, calibration_method="test"),
    )
    assert output.evidence_refs == ("artifact://query/q_123",)

    with pytest.raises(ValidationError, match="artifact://"):
        AgentOutput(
            fields={"claim": "Refunds increased"},
            evidence_refs=("raw customer row",),
            outcome=ConfidenceOutcome(score=0.8, calibration_method="test"),
        )


def test_input_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AgentInput(
            investigation_id=uuid4(),
            tenant_id=uuid4(),
            state={},
            caller_tenant_id=uuid4(),
        )


def test_output_rejects_undeclared_fields() -> None:
    output = AgentOutput(
        fields={"sql": "SELECT 1", "raw_credentials": "not allowed"},
        outcome=ConfidenceOutcome(score=0.8, calibration_method="test"),
    )

    with pytest.raises(ValueError, match="raw_credentials"):
        validate_agent_output(StubAgent(), output)


@pytest.mark.asyncio
async def test_agent_port_shape_is_usable() -> None:
    agent = StubAgent()
    output = await agent.invoke(
        AgentInput(
            investigation_id=uuid4(),
            tenant_id=uuid4(),
            state={"question": "Why did refunds increase?"},
        )
    )

    assert validate_agent_output(agent, output) == output


def _legacy_execution() -> dict[str, object]:
    """A Phase 1 execution row, as it was written before the Insight Agent
    existed as an implementation."""
    moment = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    return {
        "execution_id": str(uuid4()),
        "investigation_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "agent_id": "orchestrator_v1",
        "role": "insight_root_cause",
        "step": 3,
        "input": {"question": "Why did refunds increase?"},
        "output": {"headline": "Refunds rose 18%"},
        "outcome": {
            "kind": "confidence",
            "score": 0.72,
            "calibration_method": "evaluator_independent_recheck",
        },
        "status": "success",
        "latency_ms": 4120,
        "started_at": moment.isoformat(),
        "completed_at": moment.isoformat(),
    }


def test_the_canonical_insight_role_does_not_claim_causality() -> None:
    """ADR 0011 forbids naming the Agent for a promise its evidence cannot
    keep. The wire value is what leaks the promise, so it is what is pinned."""
    assert AgentRole.INSIGHT.value == "insight"
    assert "root_cause" not in AgentRole.INSIGHT.value


def test_the_legacy_insight_role_stays_readable() -> None:
    assert AgentRole("insight_root_cause") is AgentRole.INSIGHT_ROOT_CAUSE
    assert AgentRole.INSIGHT_ROOT_CAUSE in LEGACY_ROLES
    assert AgentRole.INSIGHT not in LEGACY_ROLES


def test_the_legacy_sql_analyst_role_stays_readable() -> None:
    """Agent Executions that ran before ADR-0025 named the role `sql_analyst`.

    Replay must keep rendering them, so the value stays deserialisable and is
    refused at the write seams instead.
    """
    assert AgentRole("sql_analyst") is AgentRole.SQL_ANALYST
    assert AgentRole.SQL_ANALYST in LEGACY_ROLES
    assert AgentRole.CUBE_ANALYST not in LEGACY_ROLES
    assert AgentRole.CUBE_ANALYST in CANONICAL_ROLES


def test_each_legacy_role_names_its_own_replacement() -> None:
    """One shared message pointed every legacy role at `insight`, which was
    right while there was one of them and misleading the moment there were
    two."""
    for legacy, replacement in (
        (AgentRole.INSIGHT_ROOT_CAUSE, AgentRole.INSIGHT),
        (AgentRole.SQL_ANALYST, AgentRole.CUBE_ANALYST),
    ):
        with pytest.raises(LegacyRoleWriteError) as raised:
            reject_legacy_role(legacy)
        assert replacement.value in str(raised.value)


def test_a_phase_1_execution_record_still_deserialises() -> None:
    """Replay has to keep rendering investigations that ran before the rename.
    Dropping the value would make them unreadable, not merely mislabelled."""
    record = AgentExecutionRecord.model_validate(_legacy_execution())

    assert record.role is AgentRole.INSIGHT_ROOT_CAUSE
    assert record.status is ExecutionStatus.SUCCESS
    assert record.confidence == 0.72

    # And it survives a full round trip, which is what Replay actually does.
    assert (
        AgentExecutionRecord.model_validate(record.model_dump(mode="json")) == record
    )


def test_a_legacy_registry_row_still_deserialises() -> None:
    agent = RegisteredAgent.model_validate(
        {"agent_id": "insight_v0", "role": "insight_root_cause", "version": "0"}
    )

    assert agent.role is AgentRole.INSIGHT_ROOT_CAUSE


def test_reject_legacy_role_refuses_only_the_legacy_value() -> None:
    """The expand step changes what may be written, not what may be read."""
    for role in CANONICAL_ROLES:
        reject_legacy_role(role)

    with pytest.raises(LegacyRoleWriteError, match="insight_root_cause"):
        reject_legacy_role(AgentRole.INSIGHT_ROOT_CAUSE)


def test_adding_usage_drops_the_model_rather_than_guessing() -> None:
    """A live free-tier run planned on Nemotron and rechecked on Opus. Keeping
    the first call's model recorded a free provider as the checker, under-graded
    the independence, and hid the Anthropic spend."""
    plan = ExecutionUsage(input_tokens=10, cost_usd=Decimal("0"), model="nemotron")
    recheck = ExecutionUsage(
        input_tokens=5, cost_usd=Decimal("0.08"), model="claude-opus-5"
    )

    total = plan + recheck

    assert total.input_tokens == 15
    assert total.cost_usd == Decimal("0.08")
    assert total.model is None
