# Chat Concurrency Analysis

> **Verdict (updated 2026-08-02):** Two tabs on **different** chats can stream without progress/budget crosstalk.
> Fix: LibreChat sends `X-Atlys-Conversation-Id` (`{{LIBRECHAT_BODY_CONVERSATIONID}}`) on MCP tool POSTs; `progress_hub` scopes consume/publish to that id.
> Still unsafe / out of scope: same `conversationId` overlapping writers (409 from `chat_runs` helps), multi-user ACL, last-write-wins transcript across tabs on the **same** chat.

> **Audience:** Anyone evaluating multi-chat UX, multi-tab use, or scaling the demo beyond a single operator.
> **Scope:** Atlys FastAPI service + React shell (`Atlys/service/**`, `Atlys/ui/**`). LibreChat internals are noted only where they affect isolation.
> **Date:** 2026-08-02

---

## 0. Short answer

| Question | Answer |
|---|---|
| Is the code concurrency-safe for 2 chats at once? | **No** — not for overlapping streams |
| Can the UI run 2 chats at once in one tab? | **No** — one `ChatPanel`, one `AbortController`, send blocked while loading |
| Can I use two chats sequentially? | **Yes** — intended path |
| Can I open two browser tabs and stream both? | **Unsafe** — progress crosstalk + coupled tool budgets |
| Same chat, two overlapping sends? | **Unsafe** — deactivate race + last-write-wins transcript |

---

## 1. Request lifecycle

```
Browser ChatPanel (one conversationId in React state)
  → POST /api/proxy/chat  { messages, conversationId, stream, extendSeries }
  → FastAPI proxy_chat:
       • ChatStore.create(conversationId)
       • progress_hub.begin_series(cid)
       • httpx stream → LibreChat /api/agents/v1/chat/completions
       • progress_hub.activate(cid) while SSE is open
  → LibreChat agent loop calls MCP tools on FastAPI (/mcp/sse)
  → MCP call_tool → progress_hub.try_consume_tool / publish
  → Proxy injects `atlys_progress` SSE into the browser stream
  → UI onDone / stop → PUT /api/conversations/{id}/messages (full replace)
```

No WebSocket for chat. Transport is SSE (proxy + MCP). There is no Redis and no per-user auth on conversation APIs. Pipeline agents and the progress hub are process-lifetime singletons.

---

## 2. Shared vs isolated

| Component | Scope | Concurrent chats? |
|---|---|---|
| `ChatPanel` messages / `loading` / `AbortController` | Per browser tab, one active chat | UI never opens two panes |
| `conversationId` (`?chat=` + `localStorage`) | Per tab | One active id; switch aborts prior stream |
| `POST /api/proxy/chat` generator + `asyncio.Queue` | Per HTTP request | Own pump/queue — fine |
| `progress_hub` (`chat_progress.py`) | **Process singleton** | **Not isolated** — main hazard |
| `ChatStore` + module `_lock` | Process-wide file store | File integrity OK; semantic merge **not** OK |
| Agents (`instrumentation`, `context`, `analytics`) | App-lifetime singletons | Shared across MCP + REST |
| `pipeline_locks` | Keyed by table/feature | Serializes DDL/approve; **not** chat-scoped |
| `ClickHouseStore._client_lock` | Per store instance | Correctness OK; throughput bottleneck |
| Auth / session | Absent for chat history | Shared Agents API key |
| Redis / distributed lock | None | N/A |

---

## 3. Critical findings

### 3.1 Progress hub broadcasts to every active stream (critical)

`ChatProgressHub` is explicitly demo-shaped for “usually one” active conversation:

```69:117:Atlys/service/chat_progress.py
    def try_consume_tool(self) -> tuple[bool, dict[str, Any]]:
        """Charge one tool against every currently streaming conversation.
        ...
            # Demo is single-user; charge the first active conversation (usually one).
            # If several are active, require all to have remaining budget.
            ...
            for cid in list(self._active):
                self._budget[cid]["used"] += 1
        ...
    def publish(self, event: dict[str, Any]) -> None:
        """Broadcast to every conversation currently streaming (demo: usually one)."""
        with self._lock:
            ...
            self._events.append({
                **event,
                ...
                "targets": list(self._active),
            })
```

MCP tools do **not** know which conversation triggered them. On each tool call they charge and publish against the global hub:

```504:555:Atlys/service/mcp_server.py
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            call_id = str(uuid.uuid4())
            allowed, budget = progress_hub.try_consume_tool()
            ...
            progress_hub.publish({
                "type": "tool_call",
                "id": call_id,
                "name": name,
                ...
            })
```

**If chat A and chat B both stream in the same FastAPI process:**

1. A’s tool chips appear in B’s SSE (and vice versa) — `poll_since` filters by `targets`, but each event’s `targets` is **all** active cids.
2. One tool call increments **both** budgets.
3. Either chat hitting its tool limit can block tools for the other.
4. Unit tests (`tests/test_chat_progress.py`) only cover a single conversation id.

This is the primary reason two concurrent chats are unsafe.

### 3.2 Same `conversationId`, overlapping streams (critical)

`activate` / `deactivate` use a **set**, not a refcount:

```35:43:Atlys/service/chat_progress.py
    def activate(self, conversation_id: str) -> int:
        with self._lock:
            self._active.add(conversation_id)
            return self._seq

    def deactivate(self, conversation_id: str) -> None:
        with self._lock:
            self._active.discard(conversation_id)
```

Proxy lifecycle (`api.py`):

1. `begin_series(cid)` at request start (may **reset** budget unless `extendSeries`)
2. `activate(cid)` when the SSE generator starts
3. `deactivate(cid)` in `finally` when that request ends

If two requests share the same cid:

- Request 1 finishing first **deactivates** while request 2 is still live → progress side-channel and budget scoping break for the survivor.
- A new user turn on one request can `begin_series(..., extend=False)` and wipe the other’s tool budget mid-turn.

There is **no** HTTP 409 / “already streaming” guard on `/proxy/chat`.

### 3.3 Transcript persistence is last-write-wins (high)

```134:196:Atlys/service/chat_store.py
    def save_messages(self, conversation_id: str, messages: list[dict[str, Any]]) -> dict:
        """Replace transcript. Creates the conversation if missing."""
        ...
        with _lock:
            data = self._read(conversation_id)
            ...
            data["messages"] = cleaned
            ...
            self._write(data)
```

- Full replace of the message array — no merge, version, or etag.
- Module `_lock` serializes JSON I/O (no torn files; atomic `tmp → path` rename).
- The lock does **not** prevent lost updates: two clients each read → edit → write; last writer wins.
- **Different** conversations = different files → writes do not clobber each other (only contend on the global lock for latency).
- **Same** conversation from two tabs → one transcript is silently discarded.

Conversation CRUD has **no auth**. Any client that knows a UUID can read/overwrite it.

### 3.4 UI: one stream per tab, residual switch races (medium)

Guards that help:

- `if (loadingRef.current && !isAutoContinue) return` — no second send while loading.
- `onSelectChat` / `startNewChat` / `popstate` call `stopGenerating()` (abort).
- Single `ChatPanel` in the shell — cannot open two panes.
- On abort after switch, if `conversationIdRef.current !== cid`, the handler skips `finishStopped` and returns early (avoids writing stopped state into the new chat’s UI).

Residual races:

1. **Stale `requestAnimationFrame` publish** — `publish()` queues `setMessages(messagesRef.current)`. Abort stops new events, but a already-queued rAF can still paint the old stream’s transcript after `loadConversation` painted another chat.
2. **`loadConversation` has no generation / epoch token** — after `await getConversationMessages(id)`, there is no check that the user is still on that id. A slow load for A can finish after the user switched to B and overwrite B’s UI.
3. **Persist after navigation** — `persistMessages(cid, …)` uses the send-time `cid`. Abort-on-switch usually skips `onDone`, but error / tool-limit finish paths can still write the old cid after the user navigated. (Writing the *old* file is often correct; the risk is surprising history updates / races with another tab.)
4. History sidebar is `disabled={false}` — switching mid-stream is allowed by design (abort + load).

### 3.5 Shared pipeline / MCP under concurrent tool use (medium)

Not chat-transport bugs, but relevant if two chats both drive the agent:

| Area | Behavior under overlap |
|---|---|
| Different feature tables + `pipeline_locks` | Mostly OK — DDL/approve serialized per key |
| Same feature table rebuild | Last-writer-wins on DROP/CREATE (documented in SETUP) |
| `ContextAgent.next_version()` | Read-max-then-insert TOCTOU if two schema paths race |
| Insights inserts | Append-style — concurrent analytics can duplicate cards |
| `db_read` / CH client | Serialized by `_client_lock` — correct, slower under load |
| `save_document` | Shared `generated/` paths — same filename overwrites |

### 3.6 What *is* concurrency-safe

- Proxy per-request `asyncio.Queue` and httpx stream lifecycle.
- `ChatStore` atomic rename — no half-written JSON.
- Event bus concurrent emits across aggregates (no global emit lock required for correctness of unrelated events).
- ClickHouse client serialization (intentional; covered by `tests/test_store_concurrency.py`).
- Sequential use in one tab: send → wait/stop → new chat or switch.

---

## 4. Scenario matrix

| Scenario | Safe? | Why |
|---|---|---|
| One tab, sequential chats (finish/stop, then new or switch) | **Yes** | Intended path |
| One tab, send while already loading | Blocked | `loadingRef` guard |
| One tab, switch/new while streaming | Mostly OK | Abort + load; small UI/persist races possible |
| Two tabs, **different** cids, both streaming | **No** | Hub broadcast + coupled budgets |
| Two tabs, **same** cid, both streaming | **No** | Deactivate race + LWW transcript + hub |
| Two API clients overlapping `/proxy/chat` | **No** | Same hub issues |
| Two tabs, neither streaming — just browsing history | **Yes** | Independent reads; writes still LWW if both persist |
| Overlapping MCP tools on same feature table | Partial | Locks help approve; rebuilds still racey |

**Partial safety summary:** Different conversation **files** can be written safely when streams do **not** overlap. The moment two streams are active in one FastAPI process, the progress hub makes them unsafe. The UI never intentionally runs two streams; multi-tab or scripted concurrency does.

---

## 5. Design intent

This matches existing product docs:

- `docs/chat-history-plan.md` — single-operator demo; multi-user ACL out of scope.
- Inline comments in `chat_progress.py` — “Demo is single-user”; “usually one”.
- Process-wide singleton: `# Process-wide singleton — MCP handlers and the chat proxy share one hub.`

The architecture optimized for **live tool chips while LibreChat buffers**, not for isolated multi-chat. MCP runs in-process without a conversation id on the tool call path, so the hub chose broadcast + “charge all active” as a demo shortcut.

---

## 6. Recommendations (priority order)

### P0 — Make progress hub conversation-scoped

1. Tag every `publish` / `try_consume_tool` with the owning `conversation_id`.
   - Prefer a `contextvars.ContextVar` set by the proxy for the MCP request path, or pass cid via LibreChat/MCP metadata if available.
2. `try_consume_tool(conversation_id)` charges **only** that cid.
3. `publish` sets `targets: [owner_cid]` only — stop broadcasting to `list(self._active)`.
4. Add tests for two active cids: events and budgets must not leak.

### P0 — Fix activate/deactivate semantics

- Refcount activations per cid, **or**
- Reject a second `/proxy/chat` for an already-active cid with **409 Conflict**.

### P1 — Frontend hardening

- Chat-epoch / generation token: ignore rAF publishes and load responses unless the epoch still matches.
- Cancel pending rAF on abort / conversation switch.
- After `await getConversationMessages`, bail if `conversationIdRef.current !== id`.
- Only persist when still appropriate (`conversationIdRef` / explicit “persist this cid even after switch” policy).

### P1 — Transcript write safety

- Optimistic concurrency: `updatedAt` / version on PUT; reject stale writes with 409.
- Or move to append-only message API so concurrent writers cannot wipe each other.

### P2 — Optional hard guard for the demo

- Global max concurrent streams (e.g. 1) with a clear error — documents the product constraint until P0 lands.
- Or allow N streams only after hub isolation ships.

### P2 — If multi-user ever matters

- Auth on conversation APIs, per-user storage paths, drop shared API-key trust from the browser.

---

## 7. Suggested verification (after fixes)

1. Two tabs, different chats, both streaming tool-heavy prompts → chips and budgets stay isolated.
2. Two tabs, same chat → second stream 409 **or** refcounted activate; no silent deactivate of the survivor.
3. Rapid switch A→B while A still loading → UI shows only B; no stale rAF paint of A.
4. Two overlapping PUTs to same cid with versioning → stale write rejected.
5. Sequential single-tab flow still unchanged (regression).

---

## 8. Key files

| Path | Role |
|---|---|
| `Atlys/service/chat_progress.py` | Shared hub — primary concurrency hazard |
| `Atlys/service/api.py` (`proxy_chat`) | Activate/deactivate + series begin |
| `Atlys/service/mcp_server.py` | Tool exec + unscoped hub publish |
| `Atlys/service/chat_store.py` | JSON transcript store (full replace) |
| `Atlys/ui/src/components/chat/ChatPanel.jsx` | Single-chat UI lifecycle |
| `Atlys/ui/src/api/client.js` | `chatStream`, chat id helpers |
| `Atlys/service/locks.py` | DDL keyed locks (not chat) |
| `Atlys/tests/test_chat_progress.py` | Single-cid budget tests only |
| `docs/chat-history-plan.md` | Single-operator history design |

---

## 9. Bottom line

Safe for **one streaming chat at a time** (the demo’s intended use).

Not safe for **two overlapping streams** in the same FastAPI process — especially across tabs — because MCP progress and tool budgets are process-global and fan out to every active conversation. Transcript files for different chats do not collide when streams do not overlap; the progress hub is what makes concurrent streaming unsafe.
