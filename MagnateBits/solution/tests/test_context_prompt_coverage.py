"""Two silent-omission bugs found by auditing the design PRDs against live code.

1. `ContextSnapshot.as_prompt()` iterated 8 kinds while `ContextKind` defines 9 --
   `column_doc` was absent from EVERY LLM prompt, unconditionally. It was 342 of 459
   live entries (74% of the layer). The Instrumentation Agent generates column
   documentation that nothing ever read. The disk renderer (`context_agent._KIND_ORDER`)
   had all nine, so the two lists had quietly diverged.

   Fixing it by dumping all 342 would crowd out governance context, so the render is
   capped per kind and the truncation is stated in the prompt itself -- visible, not
   silent -- with ranked retrieval as the mechanism that surfaces the relevant ones.

2. `tracing._real()` was supposed to treat `.env.example` placeholders as absent and did
   the opposite: `"pk-lf-...".rstrip(".")` is `"pk-lf-"`, which does not end with
   `"pk-lf"` (the dash), so every stub read as a REAL key. Since `make setup` copies
   `.env.example` to `.env`, a fresh clone got `tracing_enabled() == True`, every span
   401'd, and a dead trace_url was still written -- quietly breaking "no trace, no
   credit" for anyone reproducing the work.
"""

from __future__ import annotations

import typing
from datetime import datetime

import pytest

import tracing
from contracts import ContextEntry, ContextKind, ContextSnapshot


# ── 1. every context kind must be renderable ─────────────────────────────────


def test_prompt_render_order_covers_every_context_kind() -> None:
    """The guard that would have caught the original bug: an omission here is
    invisible at runtime and silently drops that kind from every prompt."""
    declared = set(typing.get_args(ContextKind))
    rendered = set(ContextSnapshot.PROMPT_KIND_ORDER)
    assert declared - rendered == set(), f"kinds never rendered into a prompt: {declared - rendered}"
    assert rendered - declared == set(), f"render order names unknown kinds: {rendered - declared}"


def _entry(i: int, kind: str) -> ContextEntry:
    return ContextEntry(
        entry_id=f"{kind}.e{i:03d}", version=1, kind=kind, key=f"k{i}",
        body=f"body {i}", source="test", refs=[], confidence=1.0, status="active",
        created_at=datetime(2026, 1, 1), run_id="t",
    )


def test_column_doc_reaches_the_prompt() -> None:
    snap = ContextSnapshot(version=1, entries=[_entry(0, "column_doc")])
    assert "## column_doc" in snap.as_prompt()


def test_high_volume_kind_is_capped_and_says_so() -> None:
    """Capping is fine; capping silently is not -- a reader must be able to tell that
    entries were withheld."""
    cap = ContextSnapshot.PROMPT_KIND_CAP["column_doc"]
    snap = ContextSnapshot(version=1, entries=[_entry(i, "column_doc") for i in range(cap + 40)])
    out = snap.as_prompt()
    assert out.count("- [column_doc.") == cap, "cap not applied"
    assert "40 more column_doc entries not shown" in out, "truncation must be stated"


def test_capping_never_hides_governance_kinds() -> None:
    """Contradictions/gaps/metrics must never be truncated -- they are the whole point
    of having a context layer that argues with the data."""
    for kind in ("contradiction", "gap", "metric", "known_issue"):
        assert kind not in ContextSnapshot.PROMPT_KIND_CAP, f"{kind} must not be capped"
        snap = ContextSnapshot(version=1, entries=[_entry(i, kind) for i in range(60)])
        assert snap.as_prompt().count(f"- [{kind}.") == 60


# ── 2. placeholder credentials must not enable tracing ───────────────────────


@pytest.mark.parametrize(
    "stub", ["pk-lf-...", "sk-lf-...", "pk-lf-", "sk-lf-", "", "   ", "...", None]
)
def test_placeholder_keys_are_treated_as_absent(stub) -> None:
    """Each of these returned True before the fix, silently enabling a 401'ing exporter."""
    assert tracing._real(stub) is False, f"{stub!r} must not count as a real key"


@pytest.mark.parametrize(
    "key",
    [
        "pk-lf-1a2b3c4d-5e6f-7788-99aa-bbccddeeff00",
        "sk-lf-1a2b3c4d-5e6f-7788-99aa-bbccddeeff00",
    ],
)
def test_realistic_keys_still_enable_tracing(key: str) -> None:
    """The fix must not over-correct into rejecting genuine credentials."""
    assert tracing._real(key) is True
