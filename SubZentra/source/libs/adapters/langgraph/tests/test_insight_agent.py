"""The Insight Agent's refusals, and what its error messages may carry.

Already a standalone test when it lived in `test_graph_insight.py` — it built
the agent directly and never touched the graph — so ADR-0026's deletion moved
the file it sat in, not the test. Insight's behaviour inside the loop is
covered by `apps/api/tests/test_loop_insight.py`.
"""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID

import pytest
from zentra_domain_agent_execution import (
    AgentInput,
    ExecutionUsage,
    ModelResponse,
)

from zentra_adapter_langgraph import InsightAgent

INVESTIGATION_ID = UUID("11000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("22000000-0000-0000-0000-000000000002")
QUESTION = "Why did EU refunds increase from June to July 2026?"

REVEALING = {
    "headline": "EU refunds rose $240 in July.",
    "summary": "Governed EU refund amount rose from $20 to $260.",
    "claims": [
        {
            "kind": "observed",
            # Both of these must stay out of any error message: the text is
            # customer-derived narrative, the value a customer figure.
            "text": "A pricing change in the Nordics drove refunds to $998.71.",
            "metric": "invented_pricing_driver",
            "value": "998.71",
            "period": "Q3 2026",
        }
    ],
    "contradictions": [],
    "root_cause_resolved": False,
    "confidence": 0.9,
}


class OneShotModel:
    """Serves a single pinned payload, whatever is asked."""

    def __init__(self, payload: object) -> None:
        self._payload = payload

    async def complete(self, **_: object) -> ModelResponse:
        return ModelResponse(
            text=json.dumps(self._payload)
            if isinstance(self._payload, dict)
            else str(self._payload),
            usage=ExecutionUsage(
                input_tokens=1, output_tokens=1, cost_usd=Decimal("0"), model="stub"
            ),
        )


UPSTREAM = {
    "question": QUESTION,
    "analyst": {
        "metrics": [
            {
                "metric": "refund_amount",
                "previous_value": "20.00",
                "current_value": "260.00",
                "unit": "USD",
                "previous_label": "June 2026",
                "current_label": "July 2026",
            }
        ],
        "result_summary": "EU refunds rose from $20 to $260.",
        "evidence_refs": ["artifact://execution/1"],
    },
    "evaluator": {
        "recheck_passed": True,
        "issues": [],
        "outcome": {
            "kind": "confidence",
            "score": 0.8,
            "calibration_method": "evaluator_independent_recheck",
        },
    },
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        REVEALING,
        {**REVEALING, "root_cause_resolved": True},
        {**REVEALING, "claims": [{**REVEALING["claims"][0], "metric": None}]},
        "not json at all",
    ],
    ids=["invented-metric", "causal-overclaim", "uncited", "malformed"],
)
async def test_a_refusal_never_carries_the_content_it_refused(payload: object) -> None:
    """ "Fail closed with sanitized errors" is only worth anything if the error
    itself is safe. These messages reach logs, audit metadata and, through the
    failure path, an API response — so they may name a position and a governed
    metric, and nothing else.
    """
    agent = InsightAgent(model=OneShotModel(payload))

    with pytest.raises(Exception) as raised:  # noqa: PT011 - four distinct types
        await agent.invoke(
            AgentInput(
                investigation_id=INVESTIGATION_ID,
                tenant_id=TENANT_ID,
                state=UPSTREAM,
            )
        )

    message = str(raised.value)
    assert "998.71" not in message, "a customer figure reached the error"
    assert "Nordics" not in message, "claim narrative reached the error"
    assert "pricing change" not in message.lower()
    # An unrecognised metric name is model output too — it can carry prose.
    assert "invented_pricing_driver" not in message


@pytest.mark.asyncio
async def test_no_metrics_with_a_summary_drafts_an_informational_finding() -> None:
    """A catalog/schema question has no aggregate to draft a metric claim from,
    but the Analyst's own validated summary is not nothing — relaying it is
    the answer, not a fabricated finding.
    """
    agent = InsightAgent(model=OneShotModel({}))  # never called; no metrics path

    output = await agent.invoke(
        AgentInput(
            investigation_id=INVESTIGATION_ID,
            tenant_id=TENANT_ID,
            state={
                "question": "What tables are available in the catalog?",
                "analyst": {
                    "metrics": [],
                    "result_summary": "8 datasets are available: application_started, "
                    "auth_completed, ...",
                    "evidence_refs": ["artifact://execution/1"],
                },
                "evaluator": {
                    "recheck_passed": True,
                    "issues": [],
                    "outcome": {
                        "kind": "confidence",
                        "score": 0.7,
                        "calibration_method": "evaluator_independent_recheck",
                    },
                },
            },
        )
    )

    assert output.fields["summary"].startswith("8 datasets are available")
    assert output.fields["headline"] == output.fields["summary"]
    assert output.fields["claims"] == []
    assert output.fields["root_cause"] == "unresolved"
    # Bounded by the Evaluator's score, never above it.
    assert output.outcome.score == 0.7


@pytest.mark.asyncio
async def test_a_long_summary_yields_a_headline_within_the_brief_bound() -> None:
    """`VisualizationBriefV1.headline` caps at 240 chars; the Analyst's own
    summary text was never written to that bound, so relaying it verbatim into
    both fields is how this 500s downstream — observed live.
    """
    agent = InsightAgent(model=OneShotModel({}))
    long_summary = (
        "The catalog lists 8 tables: application_started, auth_completed, "
        "destination_card_clicked, document_uploaded, landing_page_scrolled, "
        "pay_now_clicked, purchase_completed, and search_typed, totaling 356 "
        "members across dimensions and measures; no metrics are reported "
        "because this is a schema question, not a data query."
    )
    assert len(long_summary) > 240

    output = await agent.invoke(
        AgentInput(
            investigation_id=INVESTIGATION_ID,
            tenant_id=TENANT_ID,
            state={
                "question": "What tables are available in the catalog?",
                "analyst": {
                    "metrics": [],
                    "result_summary": long_summary,
                    "evidence_refs": [],
                },
                "evaluator": {"recheck_passed": True, "issues": []},
            },
        )
    )

    assert len(output.fields["headline"]) <= 240
    assert output.fields["summary"] == long_summary
    assert long_summary.startswith(output.fields["headline"].rstrip("…"))


@pytest.mark.asyncio
async def test_no_metrics_and_no_summary_still_refuses() -> None:
    agent = InsightAgent(model=OneShotModel({}))

    with pytest.raises(Exception, match="No validated aggregate"):  # noqa: PT011
        await agent.invoke(
            AgentInput(
                investigation_id=INVESTIGATION_ID,
                tenant_id=TENANT_ID,
                state={
                    "question": QUESTION,
                    "analyst": {"metrics": [], "result_summary": ""},
                    "evaluator": {"recheck_passed": True, "issues": []},
                },
            )
        )


@pytest.mark.asyncio
async def test_a_claim_citing_an_earlier_point_in_a_breakdown_is_not_ungrounded() -> (
    None
):
    """A breakdown-by-date question reports many points under one metric name,
    one per day — observed live with 30 `"Started applications"` entries for a
    June daily count. Indexing them by name alone kept only the last one
    (June 30), so a claim about any earlier day was refused as citing a value
    "the validated aggregate does not carry" even though it plainly did.
    """
    daily = [
        {
            "metric": "Started applications",
            "previous_value": "N/A",
            "previous_label": None,
            "current_value": str(1000 + day),
            "current_label": f"June {day}, 2026",
            "unit": "count",
        }
        for day in range(1, 31)
    ]
    draft = {
        "headline": "Started applications rose through June.",
        "summary": "Daily started-application counts trended upward in June 2026.",
        "claims": [
            {
                "kind": "observed",
                "text": "797 applications started on June 3, 2026.",
                "metric": "Started applications",
                "value": "1003",
                "period": "June 3, 2026",
            }
        ],
        "contradictions": [],
        "root_cause_resolved": False,
        "confidence": 0.9,
    }
    agent = InsightAgent(model=OneShotModel(draft))

    output = await agent.invoke(
        AgentInput(
            investigation_id=INVESTIGATION_ID,
            tenant_id=TENANT_ID,
            state={
                "question": "What is the count of started applications by date "
                "for the last month?",
                "analyst": {"metrics": daily, "result_summary": "", "evidence_refs": []},
                "evaluator": {"recheck_passed": True, "issues": []},
            },
        )
    )

    assert output.fields["claims"][0]["value"] == "1003"
    assert output.fields["claims"][0]["period"] == "June 3, 2026"
