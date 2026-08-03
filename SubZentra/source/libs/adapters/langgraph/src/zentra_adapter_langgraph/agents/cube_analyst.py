from __future__ import annotations

from zentra_domain_agent_execution import (
    AgentDescriptor,
    AgentInput,
    AgentOutput,
    AgentRole,
    ConfidenceOutcome,
    ModelMessage,
    ModelPort,
    SemanticLayerPort,
    ToolAccess,
    ToolScope,
    validate_agent_output,
)

from ..constants import MAX_TOKENS
from ..prompts import CUBE_ANALYST_SYSTEM
from ..runtime import AgentRuntime
from ..schemas import ANALYSIS_SCHEMA
from ..skills import SkillRegistry
from ..tools import (
    RawQueryTool,
    SemanticCatalogSearchTool,
    SemanticQueryTool,
    ToolRegistry,
)

AGENT_ID = "cube_analyst_v1"

DESCRIPTOR = AgentDescriptor(
    agent_id=AGENT_ID,
    role=AgentRole.CUBE_ANALYST,
    # Every capability this agent holds, and all of them reach data through
    # the semantic layer. `raw_query` skips ADR-0003's governed-catalog
    # restriction — granted here because this deployment has opted out of it —
    # but still only ever reaches this tenant's own Data Connection.
    tool_permissions=(
        ToolScope(tool_name="semantic_catalog_search", access=ToolAccess.READ),
        ToolScope(tool_name="semantic_query", access=ToolAccess.READ),
        ToolScope(tool_name="raw_query", access=ToolAccess.READ),
    ),
    context_budget_tokens=MAX_TOKENS,
    input_schema={"type": "object", "properties": {"question": {"type": "string"}}},
    output_schema=ANALYSIS_SCHEMA,
    output_fields=frozenset(
        {"query", "reasoning", "result_summary", "metrics", "rows", "sample_size"}
    ),
    eval_suite_ref="evals/cube_analyst",
)


class CubeAnalystAgent:
    """Explores the governed catalog, queries it, and reports what it shows.

    It made exactly two model calls before — plan a query, interpret its rows —
    which is enough when the catalog is one small cube known in advance. Against
    a tenant's own harvested warehouse the right query is not knowable up front,
    so this now runs a tool loop: search the catalog, query, look, narrow, query
    again, then answer.
    """

    def __init__(
        self,
        *,
        model: ModelPort,
        semantic_layer: SemanticLayerPort,
        skills: SkillRegistry | None = None,
        max_steps: int | None = None,
    ) -> None:
        self._model = model
        self._semantic_layer = semantic_layer
        self._skills = skills or SkillRegistry.from_directory()
        self._max_steps = max_steps

    @property
    def descriptor(self) -> AgentDescriptor:
        return DESCRIPTOR

    async def invoke(self, agent_input: AgentInput) -> AgentOutput:
        question = str(agent_input.state["question"])
        execution_id = str(agent_input.state["execution_id"])
        previous_issues = agent_input.state.get("previous_issues") or []

        # Built per invocation, never per agent. The Evaluator loop can run
        # this Agent three times over one Investigation, and each tool
        # remembers the last query it ran — shared across attempts, attempt
        # two would cite attempt one's query if the retry never got as far as
        # querying.
        query_tool = SemanticQueryTool(self._semantic_layer)
        raw_query_tool = RawQueryTool(self._semantic_layer)
        registry = ToolRegistry(
            (
                SemanticCatalogSearchTool(self._semantic_layer),
                query_tool,
                raw_query_tool,
            )
        )
        runtime = AgentRuntime(
            model=self._model,
            tools=registry,
            skills=self._skills,
            **({"max_steps": self._max_steps} if self._max_steps else {}),
        )

        prompt = f"Question: {question}"
        if previous_issues:
            # On a retry the analyst is told what the recheck disagreed with,
            # which is what makes this an optimizer loop rather than a repeat.
            issues = "\n".join(f"- {issue}" for issue in previous_issues)
            prompt = f"{prompt}\n\nA previous attempt was rejected:\n{issues}"

        def _figures_rest_on_a_query(answer: dict[str, object]) -> str | None:
            """Refuse *reported figures* that no query supports.

            Not "always run a query". Some questions are about the catalog
            itself — "what datasets are there?" — and are answered correctly
            without touching a row; demanding a query there made an Agent run
            a pointless `count` and then dress it up as a period comparison
            with `previous_value == current_value`, which is a fabricated
            shape for a real number.

            What must never happen is a *figure* with nothing behind it. So
            the rule is the narrow one: report metrics or a sample size only
            if a query actually ran.
            """
            reports_figures = bool(answer.get("metrics")) or bool(
                answer.get("sample_size")
            )
            ran_a_query = (
                query_tool.last_query is not None
                or raw_query_tool.last_query is not None
            )
            if reports_figures and not ran_a_query:
                return (
                    "You reported figures without running semantic_query or "
                    "raw_query, so they rest on no data. Either run the query "
                    "those figures come from, or answer with no metrics and a "
                    "sample_size of 0 if the question is about the catalog "
                    "rather than the data."
                )
            return None

        result = await runtime.run(
            descriptor=DESCRIPTOR,
            system=CUBE_ANALYST_SYSTEM,
            messages=[ModelMessage(role="user", content=prompt)],
            response_schema=ANALYSIS_SCHEMA,
            accept=_figures_rest_on_a_query,
        )
        analysis = result.output
        # Whichever tool actually ran the query this Citation must name. Both
        # cannot run "first" in a way that matters here — an invocation reaches
        # for one or the other, never a meaningful mix — so the one that has a
        # last_query at all is the one that answered.
        ran_tool = raw_query_tool if raw_query_tool.last_query is not None else query_tool

        return validate_agent_output(
            self,
            AgentOutput(
                fields={
                    # From the tool, not from the model's own account of it.
                    # A Citation has to name the query that actually ran.
                    "query": (
                        ran_tool.last_query.model_dump(mode="json")
                        if ran_tool.last_query is not None
                        else {}
                    ),
                    "reasoning": str(analysis.get("result_summary", "")),
                    "result_summary": analysis["result_summary"],
                    "metrics": analysis["metrics"],
                    "sample_size": int(analysis["sample_size"]),
                    "rows": list(ran_tool.last_rows),
                },
                evidence_refs=(f"artifact://execution/{execution_id}",),
                outcome=ConfidenceOutcome(
                    score=_clamp(analysis["confidence"]),
                    calibration_method="cube_analyst_self_reported",
                ),
                # The model the provider actually served, not the role we
                # asked for — the ledger must record what really ran.
                usage=result.usage,
                fallbacks=result.fallbacks,
                tool_calls=result.tool_calls,
            ),
        )


def _clamp(value: object) -> float:
    return min(1.0, max(0.0, float(value)))  # type: ignore[arg-type]
