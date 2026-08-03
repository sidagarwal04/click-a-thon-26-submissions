"""Q1 (hybrid retrieval-⨝-analytics query) and G6 (human-instructions channel).

Q1: `vector_rag.hybrid_issue_funnel` runs semantic issue-retrieval CROSS JOIN a per-segment
    windowFunnel in ONE ClickHouse statement — the "query no other DB can run".
G6: `instrumentation._build_user_prompt(..., instructions=...)` injects operator guidance as
    authoritative-but-lint-bounded constraints, and only when instructions are supplied.
"""
from __future__ import annotations

import pytest

import profile as profile_mod
from agents.instrumentation import _build_user_prompt
from contracts import ContextSnapshot


# ── G6: human-instructions channel (unit, no ClickHouse) ──────────────────────
def _prof():
    return profile_mod.profile_spec(
        "../specs/01_express_checkout/spec.md",
        "../specs/01_express_checkout/events.ndjson",
    )


def test_instructions_absent_by_default():
    p = _build_user_prompt(_prof(), ContextSnapshot(version=1, entries=[]), "legacy")
    assert "OPERATOR INSTRUCTIONS" not in p  # zero change when not supplied


def test_instructions_injected_when_given():
    p = _build_user_prompt(
        _prof(), ContextSnapshot(version=1, entries=[]), "legacy",
        "retain 24 months; treat plan as the primary cut",
    )
    assert "OPERATOR INSTRUCTIONS" in p
    assert "retain 24 months" in p
    # must be framed as bounded, not a licence for invalid DDL
    assert "house rules" in p.lower() and "id-leading" in p.lower()


def test_instructions_are_length_bounded():
    huge = "Z" * 5000
    p = _build_user_prompt(_prof(), ContextSnapshot(version=1, entries=[]), "legacy", huge)
    # the injected instruction text is capped at 2000 chars (a few stray Z's may appear
    # elsewhere in the template, so assert the cap held, not an exact count)
    assert 1990 <= p.count("Z") <= 2005 and p.count("Z") < 5000


def test_propose_ddl_accepts_instructions_kwarg():
    import inspect
    from agents.instrumentation import propose_ddl
    assert "instructions" in inspect.signature(propose_ddl).parameters


# ── Q1: hybrid query (live; needs a feature table + the embedding index) ──────
@pytest.fixture(scope="module")
def live():
    from ch import CH
    ch = CH()
    import vector_rag as vr
    if not ch.table_exists(vr.TABLE) or not ch.table_exists("f_express_checkout_events"):
        pytest.skip("needs a feature table + context_embeddings (run a vector pipeline first)")
    return ch


def test_hybrid_query_pairs_segment_with_nearest_issue(live):
    import vector_rag as vr
    rows = vr.hybrid_issue_funnel(
        live, "f_express_checkout_events",
        "iOS WebKit OTP autofill fails at payment step",
        first_event="express_checkout_shown", last_event="express_payment_confirmed",
    )
    assert rows, "hybrid query returned no rows"
    # every row carries BOTH a real funnel metric AND a retrieved issue — the whole point
    r0 = rows[0]
    assert "conversion" in r0 and "nearest_issue_id" in r0 and "issue_distance" in r0
    # worst-converting segment is first (ORDER BY conversion ASC)
    convs = [x["conversion"] for x in rows if x.get("conversion") is not None]
    assert convs == sorted(convs)
    # the payment-OTP query should retrieve K1 as the paired issue
    assert any(x.get("nearest_issue_id") == "known_issue.K1" for x in rows)


def test_hybrid_query_empty_when_no_index():
    """No embedding table -> [] rather than an exception (graceful)."""
    import vector_rag as vr
    from ch import CH

    class _NoTable(CH):
        def table_exists(self, name):  # noqa: D401
            return False

    assert vr.hybrid_issue_funnel(_NoTable(), "whatever", "q") == []


def test_hybrid_rejects_bad_identifier_gracefully():
    """P6: an unsafe identifier returns [] rather than injecting or crashing."""
    import vector_rag as vr
    from ch import CH
    assert vr.hybrid_issue_funnel(CH(), "f_express_checkout_events", "q",
                                  segment_col="x; DROP TABLE y") == []


def test_lit_escapes_backslash_and_quote():
    from vector_rag import _lit
    assert _lit("x\\") == "'x\\\\'"      # trailing backslash escaped, can't escape the quote
    assert _lit("a'b") == "'a\\'b'"
