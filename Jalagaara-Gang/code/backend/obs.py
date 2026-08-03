"""Observability: the shared Langfuse client singleton.

Neutral module so both `data/` and `narrator/` import the client from one place, with no
cross-lane dependency. Returns None when Langfuse keys are unset, so tracing degrades to a
no-op and the pipeline still runs locally.
"""
from __future__ import annotations

from functools import lru_cache

from config import LANGFUSE


@lru_cache
def langfuse():
    if not LANGFUSE["public_key"]:
        return None
    from langfuse import Langfuse

    return Langfuse(
        public_key=LANGFUSE["public_key"],
        secret_key=LANGFUSE["secret_key"],
        host=LANGFUSE["host"],
    )
