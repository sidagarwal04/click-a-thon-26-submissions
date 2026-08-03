"""Agent eval harness.

Each case pins a scripted model response and asserts what the agent does with
it: schema compliance, governed-member enforcement, confidence calibration
bounds, and evidence references. That is the deterministic half of the §3.11
framework — instruction adherence, schema compliance, and edge-case handling.

It deliberately does not score model quality: no live model is called, so a
case passing means the agent's own logic is correct, not that the model was
right. Functional known-answer pairs against a live model are Phase 4 work,
and `agent_registry.eval_status` should be read with that limit in mind.

Usage:
    uv run python tools/evals/run_evals.py
    uv run python tools/evals/run_evals.py --promote   # requires DATABASE_OWNER_URL
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from zentra_adapter_langgraph import (
    CubeAnalystAgent,
    EvaluatorAgent,
    InsightAgent,
    OrchestratorAgent,
)
from zentra_domain_agent_execution import (
    AgentInput,
    AgentRole,
    ConfidenceOutcome,
    ExecutionUsage,
    ModelResponse,
    RegisteredAgent,
    SemanticCatalog,
    SemanticDimension,
    SemanticMeasure,
    SemanticQuery,
    SemanticResult,
    ToolCall,
)

EVALS_ROOT = Path(__file__).resolve().parents[2] / "evals"
INVESTIGATION_ID = UUID("11000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("22000000-0000-0000-0000-000000000002")

# Every agent here is required: the run only succeeds when all of them have a
# suite and every case in it passes. Adding a key is what makes an agent
# ungatable by omission.
AGENT_IDS = {
    "orchestrator": "orchestrator_v1",
    "cube_analyst": "cube_analyst_v1",
    "evaluator": "evaluator_v1",
    "insight": "insight_v1",
}

# The coverage a suite must actually contain before its agent may be promoted.
# "All its cases passed" is not the same claim as "it was tested for the things
# that matter" — a suite stays green while someone deletes the case that hurts.
#
# Only Insight declares this. The Phase 1 agents predate the requirement, and
# retrofitting them is a separate decision rather than a side effect of this one.
REQUIRED_CASES: dict[str, frozenset[str]] = {
    "insight": frozenset(
        {
            "reports_an_observed_change_against_the_validated_aggregate",
            "accepts_a_claim_stating_the_earlier_side_of_the_comparison",
            "refuses_a_value_captioned_with_the_other_periods_label",
            "refuses_a_period_the_aggregate_never_measured",
            "accepts_a_flat_metric_captioned_with_either_period",
            "refuses_an_observed_claim_that_names_no_period",
            "labels_an_association_as_interpretation_not_proof",
            "states_root_cause_unresolved_even_when_the_recheck_agreed",
            "refuses_a_resolved_root_cause",
            "refuses_a_driver_absent_from_the_validated_aggregate",
            "refuses_a_figure_the_aggregate_does_not_carry",
            "preserves_an_evaluator_contradiction_the_model_dropped",
            "refuses_an_observed_claim_that_cites_no_governed_metric",
            "confidence_never_exceeds_the_evaluators_bound",
            "rejects_malformed_model_output",
            "refuses_to_draft_from_absent_evidence",
            "attributes_the_rungs_that_failed_before_one_answered",
        }
    ),
}


def incomplete_suites(by_agent: dict[str, list[CaseResult]]) -> dict[str, set[str]]:
    """Which required cases each suite is missing."""
    gaps: dict[str, set[str]] = {}
    for agent, required in REQUIRED_CASES.items():
        present = {case.name for case in by_agent.get(agent, [])}
        missing = required - present
        if missing:
            gaps[agent] = missing
    return gaps


class ReplayModel:
    """Returns the case's pinned responses in call order.

    `fallbacks` stands in for the rungs a real routed chain burned through
    before one answered, so a case can assert that an agent attributes them
    rather than reporting a clean run.
    """

    def __init__(
        self,
        responses: Sequence[dict[str, Any]],
        fallbacks: Sequence[str] = (),
    ) -> None:
        self._responses = list(responses)
        self._fallbacks = tuple(fallbacks)
        self._index = 0

    async def complete(self, **kwargs: Any) -> ModelResponse:
        # The closing turn — schema enforced, tools withdrawn — asks the agent
        # to restate what it just said as the declared object. It is a reshaping
        # of the previous response, not a new decision, so it replays that
        # response rather than consuming another the case would have to pin.
        closing = (
            kwargs.get("response_schema") is not None
            and not kwargs.get("tools")
            and self._index > 0
        )
        if closing:
            payload = self._responses[self._index - 1]
            return self._respond(payload, kwargs)

        if self._index >= len(self._responses):
            raise AssertionError("Agent made more model calls than the case pins")
        payload = self._responses[self._index]
        self._index += 1
        return self._respond(payload, kwargs)

    def _respond(self, payload: Any, kwargs: dict[str, Any]) -> ModelResponse:
        usage = ExecutionUsage(
            input_tokens=100,
            output_tokens=20,
            cost_usd=Decimal("0.001"),
            model=str(kwargs["model"]),
        )

        # A pinned response carrying a `query` is the agent choosing what to
        # run. Agents that reach data do that by calling a tool now, so it is
        # replayed as one — the case still pins the query the model chose,
        # which is what the case is actually about, rather than the wire shape
        # that happens to carry it.
        if isinstance(payload, dict) and "query" in payload and kwargs.get("tools"):
            return ModelResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        call_id=f"call_{self._index}",
                        name="semantic_query",
                        arguments=payload["query"],
                    ),
                ),
                stop_reason="tool_use",
                usage=usage,
                fallbacks=self._fallbacks,
            )

        return ModelResponse(
            text=json.dumps(payload) if isinstance(payload, dict) else str(payload),
            usage=usage,
            fallbacks=self._fallbacks,
        )


class ReplaySemanticLayer:
    def __init__(self, catalog: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        self._catalog = SemanticCatalog(
            measures=tuple(SemanticMeasure(**m) for m in catalog["measures"]),
            dimensions=tuple(SemanticDimension(**d) for d in catalog["dimensions"]),
        )
        self._rows = rows

    async def catalog(self) -> SemanticCatalog:
        return self._catalog

    async def query(self, request: SemanticQuery) -> SemanticResult:
        self._catalog.reject_ungoverned(request)
        return SemanticResult(query=request, rows=tuple(self._rows))

    async def query_raw(self, request: SemanticQuery) -> SemanticResult:
        return SemanticResult(query=request, rows=tuple(self._rows))


class ReplayRegistry:
    def __init__(self, roles: Sequence[str]) -> None:
        self._roles = roles

    async def enabled_agents(self) -> tuple[RegisteredAgent, ...]:
        return tuple(
            RegisteredAgent(
                # A role with no implemented agent still has to be nameable
                # in a case, or the vocabulary is not actually accepted.
                agent_id=AGENT_IDS.get(role, role),
                role=AgentRole(role),
                version="1",
            )
            for role in self._roles
        )


@dataclass(slots=True)
class CaseResult:
    agent: str
    name: str
    passed: bool
    detail: str = ""


def _build_agent(case: dict[str, Any]) -> Any:
    agent = case["agent"]
    model = ReplayModel(
        case.get("model_responses", []),
        case.get("model_fallbacks", []),
    )
    if agent == "orchestrator":
        return OrchestratorAgent(
            model=model,
            registry=ReplayRegistry(case.get("enabled_roles", [])),
        )
    if agent == "insight":
        # No semantic layer: Insight reaches nothing, and handing it one would
        # make the case weaker than the agent.
        return InsightAgent(model=model)
    layer = ReplaySemanticLayer(case["catalog"], case.get("rows", []))
    if agent == "cube_analyst":
        return CubeAnalystAgent(model=model, semantic_layer=layer)
    if agent == "evaluator":
        return EvaluatorAgent(model=model, semantic_layer=layer)
    raise ValueError(f"Unknown agent in case: {agent}")


async def _run_case(path: Path) -> CaseResult:
    case = json.loads(path.read_text())
    agent_name = case["agent"]
    expect = case["expect"]
    state = {**case["state"], "execution_id": str(INVESTIGATION_ID)}

    try:
        output = await _build_agent(case).invoke(
            AgentInput(
                investigation_id=INVESTIGATION_ID,
                tenant_id=TENANT_ID,
                state=state,
            )
        )
    except Exception as error:  # noqa: BLE001 - a refusal can be the expectation
        expected = expect.get("raises")
        if expected and type(error).__name__ == expected:
            return CaseResult(agent_name, case["name"], True)
        return CaseResult(
            agent_name,
            case["name"],
            False,
            f"unexpected {type(error).__name__}: {error}",
        )

    if expect.get("raises"):
        return CaseResult(
            agent_name,
            case["name"],
            False,
            f"expected {expect['raises']} but the agent returned a result",
        )

    problems: list[str] = []
    if "outcome_kind" in expect and output.outcome.kind != expect["outcome_kind"]:
        problems.append(f"outcome kind {output.outcome.kind}")
    if isinstance(output.outcome, ConfidenceOutcome):
        score = output.outcome.score
        if "min_score" in expect and score < expect["min_score"]:
            problems.append(f"score {score} below {expect['min_score']}")
        if "max_score" in expect and score > expect["max_score"]:
            problems.append(f"score {score} above {expect['max_score']}")
    if "evidence_refs" in expect and len(output.evidence_refs) != expect["evidence_refs"]:
        problems.append(f"{len(output.evidence_refs)} evidence refs")
    for key, value in expect.get("fields", {}).items():
        if output.fields.get(key) != value:
            # Names the field, never its content. Insight's fields carry
            # customer-derived narrative and figures, and this line reaches
            # CI logs.
            problems.append(f"field {key} does not match the expected value")
    for key in expect.get("field_present", []):
        if key not in output.fields:
            problems.append(f"missing field {key}")
    # The other direction. Without it a case named for what must be absent
    # cannot fail, and its name is a claim nothing backs.
    for key in expect.get("field_absent", []):
        if key in output.fields:
            problems.append(f"field {key} should not be present")
    if "fallbacks" in expect and list(output.fallbacks) != expect["fallbacks"]:
        problems.append(
            f"{len(output.fallbacks)} fallback rungs attributed, "
            f"expected {len(expect['fallbacks'])}"
        )

    return CaseResult(agent_name, case["name"], not problems, "; ".join(problems))


async def _promote(passing: set[str]) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    url = os.environ.get("DATABASE_OWNER_URL")
    if not url:
        raise SystemExit("--promote requires DATABASE_OWNER_URL")
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        for agent, agent_id in AGENT_IDS.items():
            status = "passing" if agent in passing else "failing"
            await connection.execute(
                text(
                    "UPDATE agent_registry SET eval_status = :status, "
                    "enabled = :enabled WHERE agent_id = :agent_id"
                ),
                {
                    "status": status,
                    "enabled": status == "passing",
                    "agent_id": agent_id,
                },
            )
    await engine.dispose()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()

    results = [await _run_case(path) for path in sorted(EVALS_ROOT.glob("*/*.json"))]
    if not results:
        raise SystemExit(f"No eval cases found under {EVALS_ROOT}")

    by_agent: dict[str, list[CaseResult]] = {}
    for result in results:
        by_agent.setdefault(result.agent, []).append(result)

    passing: set[str] = set()
    for agent, cases in sorted(by_agent.items()):
        failed = [case for case in cases if not case.passed]
        for case in failed:
            print(f"FAIL {agent}/{case.name}: {case.detail}", file=sys.stderr)
        if not failed:
            passing.add(agent)
        print(f"{agent}: {len(cases) - len(failed)}/{len(cases)} passed")

    missing = set(AGENT_IDS) - set(by_agent)
    if missing:
        print(f"No cases for: {', '.join(sorted(missing))}", file=sys.stderr)

    # A suite that passes but does not cover what it must is not a suite that
    # earned a promotion, so an incomplete one is demoted alongside a failing
    # one rather than quietly enabling the agent.
    for agent, gaps in sorted(incomplete_suites(by_agent).items()):
        print(
            f"Suite for {agent} is missing required cases: "
            f"{', '.join(sorted(gaps))}",
            file=sys.stderr,
        )
        passing.discard(agent)

    if args.promote:
        await _promote(passing)
        print(f"Promoted to enabled: {', '.join(sorted(passing)) or 'none'}")

    return 0 if passing == set(AGENT_IDS) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
