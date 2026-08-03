"""Live chat progress side-channel + per-series tool budget.

LibreChat's Agents API often buffers the whole agent loop (tool calls + final
text) until a step finishes — the browser then sees 30–40s of silence followed
by a dump. MCP tools run inside our FastAPI process much earlier, so we publish
tool start/done events here and the chat proxy injects them into the SSE stream
while upstream is still silent.

Tool budget: each user-initiated chat turn gets a capped number of MCP tool
calls (default 50). Silent auto-continues share the same series. Saying
"continue" (a new user turn) starts a fresh allowance.

Concurrency: events and budgets are scoped to one conversation_id. MCP calls
should pass the id from ``X-Atlys-Conversation-Id`` (LibreChat fills
``{{LIBRECHAT_BODY_CONVERSATIONID}}``). Without an id, a single active stream
is used as a fallback; with several active streams and no id, tools still run
but progress is not published (avoids crosstalk).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any


log = logging.getLogger("atlys.chat_progress")

DEFAULT_MAX_TOOL_CALLS = 50

# Header LibreChat sends on MCP POSTs (see librechat.yaml mcpServers.headers).
CONVERSATION_ID_HEADER = "x-atlys-conversation-id"


class ChatProgressHub:
    """Thread-safe ring buffer of progress events for active chat streams."""

    def __init__(self, maxlen: int = 400) -> None:
        self._lock = threading.Lock()
        # conversation_id → activation refcount (overlapping same-cid streams)
        self._active: dict[str, int] = {}
        self._events: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._seq = 0
        # conversation_id → {used, limit}
        self._budget: dict[str, dict[str, int]] = {}

    def activate(self, conversation_id: str) -> int:
        """Mark a conversation as streaming; return current seq cursor."""
        with self._lock:
            self._active[conversation_id] = self._active.get(conversation_id, 0) + 1
            return self._seq

    def deactivate(self, conversation_id: str) -> None:
        with self._lock:
            n = self._active.get(conversation_id, 0) - 1
            if n <= 0:
                self._active.pop(conversation_id, None)
            else:
                self._active[conversation_id] = n

    def active_ids(self) -> list[str]:
        with self._lock:
            return list(self._active)

    def begin_series(
        self,
        conversation_id: str,
        *,
        limit: int = DEFAULT_MAX_TOOL_CALLS,
        extend: bool = False,
    ) -> dict[str, int]:
        """Start or continue a tool-call series for a conversation.

        ``extend=True`` keeps the running count (silent auto-continue).
        Otherwise the counter resets (new user message / "continue").
        """
        lim = max(1, int(limit))
        with self._lock:
            prev = self._budget.get(conversation_id) or {"used": 0, "limit": lim}
            if extend:
                self._budget[conversation_id] = {
                    "used": int(prev.get("used", 0)),
                    "limit": lim,
                }
            else:
                self._budget[conversation_id] = {"used": 0, "limit": lim}
            return dict(self._budget[conversation_id])

    def _resolve_owner(self, conversation_id: str | None) -> str | None:
        """Pick the conversation that owns this tool call (caller holds lock)."""
        if conversation_id:
            return conversation_id
        if len(self._active) == 1:
            return next(iter(self._active))
        return None

    def try_consume_tool(
        self, conversation_id: str | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Charge one tool against a single conversation's series budget.

        Returns ``(allowed, info)``. When nothing is streaming and no id is
        given (e.g. MCP called outside chat), tools are allowed without charging.
        """
        with self._lock:
            owner = self._resolve_owner(conversation_id)
            if owner is None:
                if not self._active:
                    return True, {"used": 0, "limit": 0, "unscoped": True}
                # Multiple streams, no attribution — do not couple budgets.
                log.warning(
                    "tool consume unscoped with %d active streams; skipping budget",
                    len(self._active),
                )
                return True, {
                    "used": 0,
                    "limit": 0,
                    "unscoped": True,
                    "ambiguous": True,
                }

            bud = self._budget.get(owner)
            if bud is None:
                bud = {"used": 0, "limit": DEFAULT_MAX_TOOL_CALLS}
                self._budget[owner] = bud
            if bud["used"] >= bud["limit"]:
                return False, {
                    "conversation_id": owner,
                    "used": bud["used"],
                    "limit": bud["limit"],
                }
            bud["used"] += 1
            return True, {
                "conversation_id": owner,
                "used": bud["used"],
                "limit": bud["limit"],
            }

    def publish(
        self,
        event: dict[str, Any],
        conversation_id: str | None = None,
    ) -> None:
        """Publish a progress event to one conversation only."""
        with self._lock:
            owner = self._resolve_owner(conversation_id)
            if owner is None:
                if self._active:
                    log.warning(
                        "progress publish dropped (ambiguous; %d active streams)",
                        len(self._active),
                    )
                return
            self._seq += 1
            self._events.append({
                **event,
                "seq": self._seq,
                "ts": time.time(),
                "targets": [owner],
                "conversation_id": owner,
            })

    def poll_since(self, conversation_id: str, since_seq: int) -> tuple[list[dict[str, Any]], int]:
        with self._lock:
            out = [
                e for e in self._events
                if e["seq"] > since_seq and conversation_id in e.get("targets", ())
            ]
            return out, self._seq


def conversation_id_from_mcp_request(server) -> str | None:
    """Read ``X-Atlys-Conversation-Id`` from the MCP request context, if any."""
    try:
        ctx = server.request_context
    except LookupError:
        return None
    request = getattr(ctx, "request", None)
    if request is None:
        return None
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    raw = headers.get(CONVERSATION_ID_HEADER) or headers.get("X-Atlys-Conversation-Id")
    if not raw or not isinstance(raw, str):
        return None
    cid = raw.strip()
    return cid or None


# Process-wide singleton — MCP handlers and the chat proxy share one hub.
progress_hub = ChatProgressHub()
