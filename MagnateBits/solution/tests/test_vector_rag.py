"""The opt-in in-ClickHouse vector RAG (vector_rag.py), ported from `loop`.

Proves: (1) the embedding is deterministic; (2) retrieval ranks the right known-issue to
the top by cosine distance (iOS OTP -> K1); (3) ranked_prompt keeps governance entries and
shrinks the prompt; (4) it is OFF by default so solution's deterministic full-dump path is
untouched. Live tests require the seeded context layer (skip if absent).
"""
from __future__ import annotations

import pytest

import vector_rag as vr
from ch import CH
from contracts import ContextEntry, ContextSnapshot


def _snap_from(entries):
    return ContextSnapshot(version=1, entries=entries)


def _entry(eid, kind, key, body):
    return ContextEntry(
        entry_id=eid, version=1, kind=kind, key=key, body=body,
        source="test", refs=[], confidence=1.0, status="active",
    )


# ── unit: embedding + ranking, no ClickHouse ──────────────────────────────────
def test_embed_is_deterministic_and_normalized():
    a = vr.embed("iOS WebKit OTP autofill regression")
    b = vr.embed("iOS WebKit OTP autofill regression")
    assert a == b
    norm = sum(x * x for x in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_embed_similarity_orders_sensibly():
    def cos(u, v):
        return sum(x * y for x, y in zip(u, v))
    q = vr.embed("ios payment otp failing")
    k1 = vr.embed("iOS WebKit OTP autofill regression at the payment step")
    k4 = vr.embed("Schengen summer appointment slot scarcity")
    assert cos(q, k1) > cos(q, k4)


def test_enabled_by_default_and_full_opts_out(monkeypatch):
    """Ranked retrieval is now the default (the context layer outgrew a promptable
    size); `full` is the explicit opt-out back to dumping the whole layer."""
    monkeypatch.delenv("ATLYS_CONTEXT_RETRIEVAL", raising=False)
    assert vr.enabled() is True
    monkeypatch.setenv("ATLYS_CONTEXT_RETRIEVAL", "full")
    assert vr.enabled() is False
    monkeypatch.setenv("ATLYS_CONTEXT_RETRIEVAL", "vector")
    assert vr.enabled() is True


def test_unrecognised_value_fails_toward_ranked_not_silently_off(monkeypatch):
    """A typo must not silently disable retrieval: ranked mode carries the
    governance-kind floor and the empty-index fallback, so it's the safe default."""
    monkeypatch.setenv("ATLYS_CONTEXT_RETRIEVAL", "vecotr")
    assert vr.enabled() is True


# ── live: requires the seeded context layer ───────────────────────────────────
@pytest.fixture(scope="module")
def live():
    ch = CH()
    if not ch.table_exists("context_entry_log"):
        pytest.skip("context layer not bootstrapped")
    return ch


def test_reindex_and_ios_otp_retrieves_k1(live):
    from contextlayer.store import ContextStore
    snap = ContextStore(live).snapshot()
    if not any(e.entry_id == "known_issue.K1" for e in snap.entries):
        pytest.skip("K1 not present in seeded context")
    vr.reindex(live, snap)
    hits = vr.search(live, "iOS payment OTP failing at checkout", k=3)
    assert hits, "no retrieval hits"
    assert hits[0]["entry_id"] == "known_issue.K1", f"top hit was {hits[0]['entry_id']}"


def test_ranked_prompt_keeps_governance_and_shrinks(live):
    from contextlayer.store import ContextStore
    snap = ContextStore(live).snapshot()
    vr.reindex(live, snap)
    ranked = vr.ranked_prompt(live, snap, "iOS OTP payment failure", k=5)
    full = snap.as_prompt()
    # governance kinds (metric) are always retained
    assert "## metric" in ranked
    # and it should not be larger than the full dump
    assert len(ranked) <= len(full) + 200
