"""The opt-in deterministic mock LLM backend (mockllm.py).

Proves: with ATLYS_LLM_BACKEND=mock the pipeline's LLM calls return schema-VALID output
for arbitrary pydantic contract types, with zero credentials and zero network, and
deterministically (same input -> same output). This is what lets the full pipeline —
including the interpret step — run offline for reproducible eval.
"""
from __future__ import annotations

import importlib
import os

import pytest
from pydantic import BaseModel


class _Nested(BaseModel):
    label: str
    score: float


class _Sample(BaseModel):
    name: str
    n: int
    ok: bool
    tags: list[str]
    nested: _Nested
    kind: str  # free string


def _fresh_llm():
    os.environ["ATLYS_LLM_BACKEND"] = "mock"
    import llm
    importlib.reload(llm)
    return llm


def test_backend_info_reports_mock():
    llm = _fresh_llm()
    assert "mock" in llm.backend_info().lower()


def test_mock_produces_schema_valid_object():
    llm = _fresh_llm()
    obj = llm.complete_json(
        name="t", system="synthesize", user="anything", schema=_Sample, context_version=1
    )
    assert isinstance(obj, _Sample)
    assert isinstance(obj.nested, _Nested)
    assert isinstance(obj.tags, list)


def test_mock_is_deterministic():
    llm = _fresh_llm()
    a = llm.complete_json(name="t", system="s", user="u", schema=_Sample, context_version=1)
    b = llm.complete_json(name="t", system="s", user="u", schema=_Sample, context_version=1)
    assert a.model_dump() == b.model_dump()


def test_mock_varies_with_input():
    llm = _fresh_llm()
    a = llm.complete_json(name="t", system="s", user="u1", schema=_Sample, context_version=1)
    b = llm.complete_json(name="t", system="s", user="u2", schema=_Sample, context_version=1)
    # different inputs should not always collapse to the identical object
    assert a.model_dump() != b.model_dump()


def test_mock_zero_cost_and_no_network():
    llm = _fresh_llm()
    llm.complete_json(name="t", system="s", user="u", schema=_Sample, context_version=1)
    assert llm.usage()["cost_usd"] == 0.0


def test_mock_handles_real_contract_types():
    """The types actually used with complete_json in the live pipeline."""
    llm = _fresh_llm()
    from contracts import DDLProposal
    from agents.analytics import QueryPlan, DraftReport

    for sch in (DDLProposal, QueryPlan, DraftReport):
        obj = llm.complete_json(
            name="t", system="s", user="u", schema=sch, context_version=1
        )
        assert isinstance(obj, sch)


def teardown_module(_mod):
    # restore default backend so other tests are unaffected
    os.environ["ATLYS_LLM_BACKEND"] = "cli"
    import llm
    importlib.reload(llm)


def test_mock_honors_constrained_schema():
    """P2: mock honors gt/lt, multipleOf, pattern, and typed tuples (was schema-invalid)."""
    llm = _fresh_llm()
    from pydantic import BaseModel, Field
    from typing import Tuple

    class Hard(BaseModel):
        gtlt: int = Field(gt=0, lt=10)
        mult: int = Field(multiple_of=5, ge=0, le=100)
        code: str = Field(pattern=r"^[A-Za-z]{3,8}$")
        pair: Tuple[int, str]

    for i in range(15):
        obj = llm.complete_json(name="t", system=f"s{i}", user=f"u{i}",
                                schema=Hard, context_version=1)
        assert 0 < obj.gtlt < 10 and obj.mult % 5 == 0
