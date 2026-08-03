"""The registration gate itself.

`run_evals.py` decides whether an Agent may reach a Tenant. That decision has
three ways to say no — the suite is absent, the suite is incomplete, or a case
failed — and until now none of them had a test. A gate nobody tests is a gate
that silently opens.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from run_evals import (
    AGENT_IDS,
    REQUIRED_CASES,
    CaseResult,
    _run_case,
    incomplete_suites,
)

EVALS_ROOT = Path(__file__).resolve().parents[2] / "evals"


def results(agent: str, names: list[str]) -> dict[str, list[CaseResult]]:
    return {agent: [CaseResult(agent, name, True) for name in names]}


def test_insight_is_a_required_agent() -> None:
    """Omission is the quietest way for an Agent to escape gating: an agent
    absent from this map is never checked and never demoted."""
    assert "insight" in AGENT_IDS
    assert AGENT_IDS["insight"] == "insight_v1"


def test_the_phase_1_agents_remain_required() -> None:
    assert {"orchestrator", "cube_analyst", "evaluator"} <= set(AGENT_IDS)


def test_an_absent_suite_leaves_insight_out_of_the_passing_set() -> None:
    assert incomplete_suites({})["insight"] == REQUIRED_CASES["insight"]


def test_an_incomplete_suite_is_reported_case_by_case() -> None:
    """A suite can be entirely green and still not have tested the thing that
    matters, because someone deleted the case that hurt."""
    kept = sorted(REQUIRED_CASES["insight"])[1:]
    dropped = sorted(REQUIRED_CASES["insight"])[0]

    gaps = incomplete_suites(results("insight", kept))

    assert gaps["insight"] == {dropped}


def test_a_complete_suite_reports_no_gaps() -> None:
    complete = sorted(REQUIRED_CASES["insight"])

    assert incomplete_suites(results("insight", complete)) == {}


def test_the_required_cases_all_exist_on_disk() -> None:
    """Otherwise the completeness gate would demote Insight forever, and the
    failure would look like a bug in the agent rather than a missing file."""
    present = {path.stem for path in (EVALS_ROOT / "insight").glob("*.json")}

    assert REQUIRED_CASES["insight"] <= present


@pytest.mark.parametrize(
    "case_path",
    sorted((EVALS_ROOT / "insight").glob("*.json")),
    ids=lambda path: path.stem,
)
def test_every_insight_case_passes(case_path: Path) -> None:
    result = asyncio.run(_run_case(case_path))

    assert result.passed, result.detail


def test_no_case_pins_a_live_model_call() -> None:
    """The suite must stay free to run. A case without pinned responses would
    reach a provider, which makes CI cost money and makes the gate flaky."""
    for path in (EVALS_ROOT / "insight").glob("*.json"):
        case = json.loads(path.read_text())
        assert case.get("model_responses"), f"{path.stem} pins no model response"
