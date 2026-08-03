"""Background chat runs that outlive the browser SSE connection.

When the user reloads mid-generation, the LibreChat upstream must keep
running. This module owns that upstream task, fans out SSE bytes to any
connected subscribers, and periodically persists transcript progress to
ChatStore so a fresh page load can poll the latest state.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from .chat_progress import progress_hub
from .chat_store import ChatStore

log = logging.getLogger("atlys.chat_runs")


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sse_atlys_progress(event: dict) -> bytes:
    payload = {
        "atlys_progress": {
            "type": event.get("type"),
            "id": event.get("id"),
            "name": event.get("name"),
            "arguments": event.get("arguments"),
            "ok": event.get("ok"),
            "used": event.get("used"),
            "limit": event.get("limit"),
        }
    }
    return f"data: {json.dumps(payload, default=str)}\n\n".encode()


def _bare_tool_name(name: str) -> str:
    import re
    return re.sub(r"_mcp_[A-Za-z0-9_-]+$", "", str(name or "tool"))


def _tool_fp(name: str, args: str) -> str:
    n = _bare_tool_name(name)
    raw = (args or "").strip() or "{}"
    try:
        parsed = json.loads(raw)
        raw = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    except (json.JSONDecodeError, TypeError):
        pass
    return f"{n}::{raw}"


def _is_incomplete_fp(fp: str) -> bool:
    return (
        not fp
        or fp.endswith("::")
        or fp.endswith("::{}")
        or fp.endswith("::null")
    )


class _TranscriptBuilder:
    """Best-effort UI transcript from Atlys progress + LibreChat deltas."""

    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = [dict(m) for m in messages]
        self._seen_fps: set[str] = set()
        self._assistant_id: str | None = None
        self._dirty = False
        for m in self.messages:
            if m.get("role") == "tool" and m.get("toolPhase") == "call":
                fp = _tool_fp(m.get("toolName") or "tool", m.get("args") or "{}")
                self._seen_fps.add(fp)
            if m.get("role") == "assistant" and m.get("id"):
                self._assistant_id = m["id"]

    def ensure_assistant(self) -> str:
        if self._assistant_id:
            for m in self.messages:
                if m.get("id") == self._assistant_id:
                    return self._assistant_id
        aid = f"a-{uuid.uuid4().hex[:12]}"
        self._assistant_id = aid
        self.messages.append({
            "id": aid,
            "role": "assistant",
            "content": "",
            "ts": _utcnow(),
        })
        self._dirty = True
        return aid

    def _relocate_assistant_before_trailing_tools(self, assistant_id: str) -> None:
        """Match ChatPanel.relocateAssistantBeforeTrailingTools for buffered dumps."""
        idx = next((i for i, m in enumerate(self.messages) if m.get("id") == assistant_id), -1)
        if idx <= 0:
            return
        insert_at = idx
        j = idx - 1
        while j >= 0:
            m = self.messages[j]
            if m.get("role") == "tool":
                insert_at = j
                j -= 1
                continue
            if (
                m.get("role") == "assistant"
                and not (m.get("content") or "").strip()
                and not (m.get("thinking") or "").strip()
            ):
                j -= 1
                continue
            break
        if insert_at == idx:
            return
        # If narration already sits before these tools, keep this bubble after them.
        for k in range(insert_at - 1, -1, -1):
            m = self.messages[k]
            if m.get("role") == "user":
                break
            if (
                m.get("role") == "assistant"
                and m.get("id") != assistant_id
                and ((m.get("content") or "").strip() or (m.get("thinking") or "").strip())
            ):
                return
        row = self.messages.pop(idx)
        self.messages.insert(insert_at, row)
        self._dirty = True

    def append_text(self, text: str) -> None:
        if not text:
            return
        aid = self.ensure_assistant()
        was_empty = False
        for m in self.messages:
            if m.get("id") == aid:
                was_empty = not (m.get("content") or "").strip() and not (m.get("thinking") or "").strip()
                m["content"] = (m.get("content") or "") + text
                self._dirty = True
                break
        if was_empty:
            self._relocate_assistant_before_trailing_tools(aid)

    def append_thinking(self, text: str) -> None:
        if not text:
            return
        aid = self.ensure_assistant()
        was_empty = False
        for m in self.messages:
            if m.get("id") == aid:
                was_empty = not (m.get("content") or "").strip() and not (m.get("thinking") or "").strip()
                m["thinking"] = (m.get("thinking") or "") + text
                self._dirty = True
                break
        if was_empty:
            self._relocate_assistant_before_trailing_tools(aid)

    def tool_call(self, call_id: str, name: str, arguments: Any) -> None:
        if isinstance(arguments, str):
            args_str = arguments
        else:
            args_str = json.dumps(arguments if arguments is not None else {}, default=str)
        name = _bare_tool_name(name)
        fp = _tool_fp(name, args_str)
        if fp in self._seen_fps:
            return
        # Skip LibreChat empty-arg stubs that arrive after a real call of this tool.
        if _is_incomplete_fp(fp):
            prefix = f"{name}::"
            if any(seen.startswith(prefix) and not _is_incomplete_fp(seen) for seen in self._seen_fps):
                return
        self._seen_fps.add(fp)
        # Drop empty trailing assistant so tools appear before the reply bubble.
        if self.messages:
            last = self.messages[-1]
            if (
                last.get("role") == "assistant"
                and not (last.get("content") or "").strip()
                and not (last.get("thinking") or "").strip()
            ):
                self.messages.pop()
                if self._assistant_id == last.get("id"):
                    self._assistant_id = None
        tid = call_id or f"t-{uuid.uuid4().hex[:12]}"
        self.messages.append({
            "id": tid,
            "role": "tool",
            "toolPhase": "call",
            "toolName": name,
            "args": args_str,
            "content": "",
            "status": "running",
            "ts": _utcnow(),
        })
        self._dirty = True

    def tool_done(self, call_id: str | None, name: str | None, ok: bool = True) -> None:
        name = _bare_tool_name(name) if name else None
        for m in reversed(self.messages):
            if m.get("role") != "tool" or m.get("toolPhase") != "call":
                continue
            if m.get("status") != "running":
                continue
            if call_id and m.get("id") == call_id:
                m["status"] = "done" if ok else "error"
                self._dirty = True
                return
            if name and m.get("toolName") == name:
                m["status"] = "done" if ok else "error"
                self._dirty = True
                return
        # Fallback: mark oldest running tool done
        for m in self.messages:
            if m.get("role") == "tool" and m.get("status") == "running":
                m["status"] = "done" if ok else "error"
                self._dirty = True
                return

    def finalize(self) -> None:
        for m in self.messages:
            if m.get("role") == "tool" and m.get("status") == "running":
                m["status"] = "done"
                self._dirty = True
        # Drop empty assistant shells
        self.messages = [
            m for m in self.messages
            if not (
                m.get("role") == "assistant"
                and not (m.get("content") or "").strip()
                and not (m.get("thinking") or "").strip()
            )
        ]
        # Drop trailing incomplete stubs (after a complete call of the same tool).
        seen_complete: set[str] = set()
        kept: list[dict[str, Any]] = []
        for m in self.messages:
            if m.get("role") != "tool":
                kept.append(m)
                continue
            bare = _bare_tool_name(m.get("toolName") or "")
            fp = _tool_fp(m.get("toolName") or "tool", m.get("args") or "{}")
            if not _is_incomplete_fp(fp):
                seen_complete.add(bare)
                kept.append(m)
                continue
            if bare in seen_complete:
                self._dirty = True
                continue
            kept.append(m)
        self.messages = kept
        # Collapse tools-then-single-assistant → assistant then tools
        self._repair_collapsed_order()

    def _find_answer_cut(self, content: str) -> int:
        """Index where the final report starts, or -1.

        LibreChat often concatenates mid-turn lines without newlines
        ("…for context.Here are the numbers"), so markers match mid-string.
        """
        import re
        if not content:
            return -1
        markers = [
            r"Here's the answer\b",
            r"Here is the answer\b",
            r"Here are the (?:numbers|results|figures|findings)\b",
            r"Here's what I found\b",
            r"Here is what I found\b",
            r"\*\*Key takeaways\b",
            r"#{1,3}\s+[A-Z][^\n]{8,}",
            r"(?m)^\|.+\|",
        ]
        cut = -1
        for pat in markers:
            m = re.search(pat, content, flags=re.I)
            if m and (cut < 0 or m.start() < cut):
                cut = m.start()
        return cut

    def _split_assistant_around_tools(
        self, assistant: dict[str, Any], tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import re
        content = assistant.get("content") or ""
        cut = self._find_answer_cut(content)
        if cut < 0:
            looks_final = len(content) > 400 or (
                "|" in content and re.search(r"\|.+\|", content) is not None
            )
            if looks_final:
                return [*tools, assistant]
            return [assistant, *tools]
        before = content[:cut].strip()
        after = content[cut:].strip()
        if not before or not after:
            if not before and after:
                return [*tools, {**assistant, "content": after}]
            return [assistant, *tools]
        head = {**assistant, "content": before}
        tail = {
            **assistant,
            "id": f"{assistant.get('id')}-answer",
            "content": after,
        }
        tail.pop("thinking", None)
        return [head, *tools, tail]

    def _repair_collapsed_order(self) -> None:
        """user → tools* → assistant  ⇒  user → preamble → tools* → answer."""
        if len(self.messages) < 2:
            return
        out: list[dict[str, Any]] = []
        i = 0
        changed = False
        while i < len(self.messages):
            head = self.messages[i]
            out.append(head)
            i += 1
            if head.get("role") != "user":
                continue
            segment: list[dict[str, Any]] = []
            while i < len(self.messages) and self.messages[i].get("role") != "user":
                segment.append(self.messages[i])
                i += 1
            tools = [m for m in segment if m.get("role") == "tool"]
            assistants = [
                m for m in segment
                if m.get("role") == "assistant"
                and ((m.get("content") or "").strip() or (m.get("thinking") or "").strip())
            ]
            if len(assistants) == 1 and tools:
                rebuilt = self._split_assistant_around_tools(assistants[0], tools)
                # Also handle tools-first by always rebuilding through the splitter
                if rebuilt != segment:
                    out.extend(rebuilt)
                    changed = True
                    continue
            out.extend(segment)
        if changed:
            self.messages = out
            self._dirty = True

    def take_dirty(self) -> bool:
        d = self._dirty
        self._dirty = False
        return d


class ChatRun:
    """One LibreChat upstream generation for a conversation."""

    def __init__(
        self,
        conversation_id: str,
        *,
        client: httpx.AsyncClient,
        resp: httpx.Response,
        store: ChatStore,
        tool_limit: int,
        extend_series: bool,
    ) -> None:
        self.conversation_id = conversation_id
        self.store = store
        self.tool_limit = tool_limit
        self.extend_series = extend_series
        self.done = False
        self.error: str | None = None
        self._cancel = asyncio.Event()
        self._subscribers: list[asyncio.Queue] = []
        self._task: asyncio.Task | None = None
        self._client = client
        self._resp = resp
        self._last_persist = 0.0
        # Buffer early SSE so the first browser subscriber doesn't miss bytes
        # that arrived before StreamingResponse started iterating.
        self._replay: list[bytes] = []
        self._replay_bytes = 0
        self._replay_max_bytes = 2_000_000
        seed = store.get_messages(conversation_id) or []
        self._builder = _TranscriptBuilder(seed)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        for chunk in self._replay:
            try:
                q.put_nowait(chunk)
            except asyncio.QueueFull:
                break
        if self.done:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def request_stop(self) -> None:
        self._cancel.set()

    async def close_upstream(self) -> None:
        resp = self._resp
        if resp is not None and not resp.is_closed:
            try:
                await resp.aclose()
            except Exception:  # noqa: BLE001
                pass

    def _remember(self, chunk: bytes) -> None:
        self._replay.append(chunk)
        self._replay_bytes += len(chunk)
        while self._replay and self._replay_bytes > self._replay_max_bytes:
            dropped = self._replay.pop(0)
            self._replay_bytes -= len(dropped)

    def _broadcast(self, chunk: bytes | None) -> None:
        if chunk is not None and not self.done:
            self._remember(chunk)
        dead: list[asyncio.Queue] = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(chunk)
            except asyncio.QueueFull:
                # Drop oldest to make room — prefer live over backlog.
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(chunk)
                except asyncio.QueueFull:
                    dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    def _persist(self, *, force: bool = False, status: str | None = None) -> None:
        now = time.monotonic()
        dirty = self._builder.take_dirty()
        if not force and not dirty:
            return
        if not force and (now - self._last_persist) < 0.75:
            if dirty:
                self._builder._dirty = True
            return
        self._last_persist = now
        try:
            self.store.save_messages(
                self.conversation_id,
                self._builder.messages,
                status=status if status is not None else "running",
            )
        except Exception as e:  # noqa: BLE001
            log.warning("chat run persist failed (%s): %s", self.conversation_id, e)

    def _handle_progress(self, ev: dict) -> None:
        typ = ev.get("type")
        if typ == "tool_call":
            self._builder.tool_call(ev.get("id") or "", ev.get("name") or "tool", ev.get("arguments"))
            self._persist(force=True, status="running")
        elif typ == "tool_done":
            self._builder.tool_done(ev.get("id"), ev.get("name"), ok=ev.get("ok") is not False)
            self._persist(force=True, status="running")
        elif typ == "tool_limit":
            self._persist(force=True, status="running")

    def _handle_delta(self, delta: dict) -> None:
        reasoning = (
            delta.get("reasoning_content")
            or delta.get("reasoning")
            or delta.get("thinking")
            or delta.get("reasoning_text")
        )
        if reasoning:
            self._builder.append_thinking(str(reasoning))
        content = delta.get("content")
        if content:
            self._builder.append_text(str(content))
        # Native tool_calls — usually replayed after Atlys side-channel; fingerprint dedupes.
        for tc in delta.get("tool_calls") or []:
            fn = tc.get("function") or {}
            if fn.get("name"):
                self._builder.tool_call(
                    tc.get("id") or "",
                    fn.get("name"),
                    fn.get("arguments") or "{}",
                )

    def _process_sse_line(self, line: str) -> str | None:
        trimmed = line.strip()
        if not trimmed or trimmed.startswith(":") or trimmed.startswith("event:"):
            return None
        if not trimmed.startswith("data:"):
            return None
        payload = trimmed[5:].lstrip()
        if payload == "[DONE]":
            return "done"
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        prog = parsed.get("atlys_progress")
        if isinstance(prog, dict):
            self._handle_progress(prog)
            return None
        delta = (parsed.get("choices") or [{}])[0].get("delta")
        if isinstance(delta, dict):
            self._handle_delta(delta)
            return None
        msg_delta = (parsed.get("message") or {}).get("delta") or parsed.get("delta")
        if isinstance(msg_delta, dict):
            self._handle_delta(msg_delta)
        return None

    async def run(self) -> None:
        cid = self.conversation_id
        progress_hub.begin_series(cid, limit=self.tool_limit, extend=self.extend_series)
        cursor = progress_hub.activate(cid)
        try:
            self.store.set_status(cid, "running")
        except Exception:  # noqa: BLE001
            pass

        client = self._client
        resp = self._resp
        sse_buf = ""
        try:
            queue: asyncio.Queue = asyncio.Queue()

            async def _pump() -> None:
                try:
                    async for chunk in resp.aiter_bytes():
                        if chunk:
                            await queue.put(chunk)
                        if self._cancel.is_set():
                            break
                except Exception as e:  # noqa: BLE001
                    log.warning("LibreChat run pump error (%s): %s", cid, e)
                finally:
                    await queue.put(None)

            task = asyncio.create_task(_pump())
            t0 = time.monotonic()
            first_data = False
            try:
                self._broadcast(b": atlys-proxy connected\n\n")
                while not self._cancel.is_set():
                    events, cursor = progress_hub.poll_since(cid, cursor)
                    for ev in events:
                        self._handle_progress(ev)
                        self._broadcast(_sse_atlys_progress(ev))

                    try:
                        chunk = await asyncio.wait_for(queue.get(), timeout=0.4)
                    except asyncio.TimeoutError:
                        waited = time.monotonic() - t0
                        self._broadcast(
                            f": keepalive waiting={waited:.1f}s first_data={str(first_data).lower()}\n\n".encode()
                        )
                        self._persist()
                        continue

                    if chunk is None:
                        events, cursor = progress_hub.poll_since(cid, cursor)
                        for ev in events:
                            self._handle_progress(ev)
                            self._broadcast(_sse_atlys_progress(ev))
                        break

                    if not first_data:
                        first_data = True
                        log.info(
                            "chat run first upstream byte after %.2fs (conversationId=%s)",
                            time.monotonic() - t0, cid,
                        )

                    events, cursor = progress_hub.poll_since(cid, cursor)
                    for ev in events:
                        self._handle_progress(ev)
                        self._broadcast(_sse_atlys_progress(ev))

                    self._broadcast(chunk)

                    try:
                        text = chunk.decode("utf-8", errors="replace")
                    except Exception:  # noqa: BLE001
                        text = ""
                    if text:
                        sse_buf += text.replace("\r\n", "\n").replace("\r", "\n")
                        lines = sse_buf.split("\n")
                        sse_buf = lines.pop() or ""
                        for line in lines:
                            if self._process_sse_line(line) == "done":
                                break
                        self._persist()
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
            log.exception("chat run failed (%s)", cid)
        finally:
            if resp is not None and not resp.is_closed:
                await resp.aclose()
            await client.aclose()
            progress_hub.deactivate(cid)
            self._builder.finalize()
            self._persist(force=True, status="idle")
            try:
                self.store.set_status(cid, "idle")
            except Exception:  # noqa: BLE001
                pass
            self.done = True
            self._broadcast(None)
            log.info(
                "chat run finished (conversationId=%s cancelled=%s error=%s)",
                cid, self._cancel.is_set(), bool(self.error),
            )


class ChatRunManager:
    def __init__(self) -> None:
        self._runs: dict[str, ChatRun] = {}
        self._lock = asyncio.Lock()

    def get(self, conversation_id: str) -> ChatRun | None:
        return self._runs.get(conversation_id)

    def is_running(self, conversation_id: str) -> bool:
        run = self._runs.get(conversation_id)
        return bool(run and not run.done)

    async def start(
        self,
        conversation_id: str,
        *,
        client: httpx.AsyncClient,
        resp: httpx.Response,
        store: ChatStore,
        tool_limit: int,
        extend_series: bool = False,
    ) -> ChatRun:
        async with self._lock:
            existing = self._runs.get(conversation_id)
            if existing and not existing.done:
                raise RuntimeError("conversation already has an active run")
            run = ChatRun(
                conversation_id,
                client=client,
                resp=resp,
                store=store,
                tool_limit=tool_limit,
                extend_series=extend_series,
            )
            self._runs[conversation_id] = run

            async def _wrapper() -> None:
                try:
                    await run.run()
                finally:
                    async with self._lock:
                        if self._runs.get(conversation_id) is run:
                            del self._runs[conversation_id]

            run._task = asyncio.create_task(_wrapper())
            return run

    async def stop(self, conversation_id: str) -> bool:
        run = self._runs.get(conversation_id)
        if not run or run.done:
            # Nothing in-flight for this conversation (manager is in-memory).
            return False
        run.request_stop()
        await run.close_upstream()
        task = run._task
        if task and not task.done():
            try:
                await asyncio.wait_for(task, timeout=3.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        return True


# Process-wide singleton
chat_runs = ChatRunManager()
