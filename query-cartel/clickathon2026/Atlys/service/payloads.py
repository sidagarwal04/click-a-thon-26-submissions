"""MCP / chat payload size guards.

Tool results flow LibreChat → Z.ai; huge evidence arrays (esp. per-user
timing rows) blow the context window. Slim nested lists/strings first, then
hard-cap serialized JSON bytes.
"""
from __future__ import annotations

import json
from typing import Any

# Defaults sized for a hackathon demo chat turn — keep aggregates, drop dumps.
# list_limit matches db_read.AGGREGATE_MAX_LIMIT so CH rows aren't re-clipped.
DEFAULT_MAX_BYTES = 65_536
DEFAULT_LIST_LIMIT = 100
DEFAULT_STR_LIMIT = 4_000
# Context snapshots / saved markdown must keep known-issues & metric defs intact.
# base_context.md alone is ~7.6k; evolved snapshots are larger.
DEFAULT_LONG_STR_LIMIT = 120_000

# Keys that commonly carry row dumps — apply list_limit (aligned with aggregate max).
_ROWISH_KEYS = frozenset({
    "rows", "evidence", "insights", "entries", "findings", "gaps",
})

# Keys that are whole documents — do not clip at DEFAULT_STR_LIMIT.
_LONG_TEXT_KEYS = frozenset({
    "content", "markdown", "body", "document", "text", "report",
})


def truncate_for_mcp(
    result: Any,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    list_limit: int = DEFAULT_LIST_LIMIT,
    str_limit: int = DEFAULT_STR_LIMIT,
    long_str_limit: int = DEFAULT_LONG_STR_LIMIT,
) -> Any:
    """Return a JSON-serializable value safe to send through MCP → chat.

    Always returns a value that `json.dumps(..., default=str)` fits in
    `max_bytes` (UTF-8). Sets `truncated: true` when anything was cut.
    Document-shaped keys (`content`, `markdown`, …) use `long_str_limit`.
    """
    slimmed, cut = _slim(
        result,
        list_limit=list_limit,
        str_limit=str_limit,
        long_str_limit=long_str_limit,
        depth=0,
    )
    if cut:
        slimmed = _with_truncated_flag(slimmed)

    text = json.dumps(slimmed, default=str)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return slimmed

    # Still too large — keep a compact preview the model can narrate from.
    preview_budget = max(256, max_bytes - 180)
    preview = encoded[:preview_budget].decode("utf-8", errors="ignore").rstrip()
    return {
        "truncated": True,
        "original_bytes": len(encoded),
        "max_bytes": max_bytes,
        "preview": preview,
        "message": "Tool result exceeded size cap — summarize from preview only; "
                   "do not invent missing numbers.",
    }


def _with_truncated_flag(obj: Any) -> Any:
    if isinstance(obj, dict):
        if obj.get("truncated") is True:
            return obj
        return {**obj, "truncated": True}
    return {"truncated": True, "data": obj}


def _slim(
    obj: Any,
    *,
    list_limit: int,
    str_limit: int,
    long_str_limit: int,
    depth: int,
) -> tuple[Any, bool]:
    if depth > 24:
        return "...", True

    if isinstance(obj, str):
        if len(obj) > str_limit:
            return obj[:str_limit] + "…", True
        return obj, False

    if isinstance(obj, (bytes, bytearray)):
        return _slim(
            obj.decode("utf-8", errors="replace"),
            list_limit=list_limit,
            str_limit=str_limit,
            long_str_limit=long_str_limit,
            depth=depth,
        )

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        cut = False
        for key, value in obj.items():
            if key in _ROWISH_KEYS and isinstance(value, list):
                slim_list, list_cut = _slim_sequence(
                    value,
                    limit=list_limit,
                    list_limit=list_limit,
                    str_limit=str_limit,
                    long_str_limit=long_str_limit,
                    depth=depth + 1,
                )
                out[key] = slim_list
                if list_cut:
                    cut = True
                    out[f"{key}_total"] = len(value)
            elif key in _LONG_TEXT_KEYS and isinstance(value, str):
                if len(value) > long_str_limit:
                    out[key] = value[:long_str_limit] + "…"
                    cut = True
                else:
                    out[key] = value
            else:
                slim_v, v_cut = _slim(
                    value,
                    list_limit=list_limit,
                    str_limit=str_limit,
                    long_str_limit=long_str_limit,
                    depth=depth + 1,
                )
                out[key] = slim_v
                cut = cut or v_cut
        return out, cut

    if isinstance(obj, (list, tuple)):
        return _slim_sequence(
            list(obj),
            limit=list_limit,
            list_limit=list_limit,
            str_limit=str_limit,
            long_str_limit=long_str_limit,
            depth=depth,
        )

    return obj, False


def _slim_sequence(
    items: list[Any],
    *,
    limit: int,
    list_limit: int,
    str_limit: int,
    long_str_limit: int,
    depth: int,
) -> tuple[list[Any], bool]:
    cut = len(items) > limit
    kept = items[:limit]
    out: list[Any] = []
    for item in kept:
        slim_item, item_cut = _slim(
            item,
            list_limit=list_limit,
            str_limit=str_limit,
            long_str_limit=long_str_limit,
            depth=depth + 1,
        )
        out.append(slim_item)
        cut = cut or item_cut
    return out, cut
