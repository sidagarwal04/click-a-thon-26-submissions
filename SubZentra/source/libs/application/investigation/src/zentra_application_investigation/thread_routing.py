"""A deterministic title for a Thread, without a model call.

Routing a Thread's first message to a question used to live here — first a
keyword table matching two governed scenarios, then a passthrough once the
whitelist was removed. Both are gone: an `IntakeAgent` now reads the question
against the Tenant's live Analytical Scope (ADR-0027) and makes a judgement
this module has no way to make. What is left is the one piece that was never
about routing: a title derived from the message text alone.
"""

from __future__ import annotations


def deterministic_thread_title(value: str) -> str:
    title = " ".join(value.split())
    return title if len(title) <= 80 else f"{title[:79].rstrip()}…"
