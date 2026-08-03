"""Atlys-owned chat transcript store (JSON files under generated/chats/).

Option B from docs/chat-history-plan.md — authoritative history for the React
shell. LibreChat may still receive conversationId for agent memory, but list /
reload go through this store.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
_TITLE_MAX = 72
_lock = threading.Lock()


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_conversation_id() -> str:
    return str(uuid.uuid4())


def is_valid_id(conversation_id: str) -> bool:
    return bool(conversation_id and _UUID_RE.match(conversation_id))


def _title_from_messages(messages: list[dict]) -> str | None:
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            text = " ".join(m["content"].split())
            if not text:
                continue
            if len(text) > _TITLE_MAX:
                return text[: _TITLE_MAX - 1].rstrip() + "…"
            return text
    return None


class ChatStore:
    """One JSON file per conversation: generated/chats/<id>.json"""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, conversation_id: str) -> Path:
        if not is_valid_id(conversation_id):
            raise ValueError(f"invalid conversation id: {conversation_id!r}")
        return self.root / f"{conversation_id}.json"

    def _read(self, conversation_id: str) -> dict | None:
        path = self._path(conversation_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        path = self._path(data["id"])
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)

    def create(self, conversation_id: str | None = None) -> dict:
        cid = conversation_id or new_conversation_id()
        if not is_valid_id(cid):
            raise ValueError(f"invalid conversation id: {cid!r}")
        now = _utcnow()
        data = {
            "id": cid,
            "title": "New chat",
            "createdAt": now,
            "updatedAt": now,
            "status": "idle",
            "messages": [],
        }
        with _lock:
            if self._path(cid).exists():
                existing = self._read(cid)
                assert existing is not None
                return existing
            self._write(data)
        return data

    def get(self, conversation_id: str) -> dict | None:
        with _lock:
            data = self._read(conversation_id)
        if data is None:
            return None
        return {
            "id": data["id"],
            "title": data.get("title") or "New chat",
            "createdAt": data.get("createdAt"),
            "updatedAt": data.get("updatedAt"),
            "status": data.get("status") or "idle",
        }

    def list(self, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        items: list[dict] = []
        with _lock:
            for path in self.root.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                # Skip empty shells with no user turns from the sidebar
                msgs = data.get("messages") or []
                if not any(m.get("role") == "user" for m in msgs):
                    continue
                items.append({
                    "id": data.get("id") or path.stem,
                    "title": data.get("title") or "New chat",
                    "createdAt": data.get("createdAt"),
                    "updatedAt": data.get("updatedAt"),
                    "status": data.get("status") or "idle",
                })
        items.sort(key=lambda x: x.get("updatedAt") or "", reverse=True)
        return items[:limit]

    def get_messages(self, conversation_id: str) -> list[dict] | None:
        with _lock:
            data = self._read(conversation_id)
        if data is None:
            return None
        return list(data.get("messages") or [])

    def get_status(self, conversation_id: str) -> str | None:
        with _lock:
            data = self._read(conversation_id)
        if data is None:
            return None
        return data.get("status") or "idle"

    def set_status(self, conversation_id: str, status: str) -> dict | None:
        """Update run status (`idle` | `running`) without touching messages."""
        if status not in ("idle", "running"):
            raise ValueError(f"invalid status: {status!r}")
        if not is_valid_id(conversation_id):
            raise ValueError(f"invalid conversation id: {conversation_id!r}")
        now = _utcnow()
        with _lock:
            data = self._read(conversation_id)
            if data is None:
                return None
            data["status"] = status
            data["updatedAt"] = now
            self._write(data)
        return {
            "id": data["id"],
            "title": data.get("title") or "New chat",
            "createdAt": data.get("createdAt"),
            "updatedAt": data["updatedAt"],
            "status": status,
        }

    def save_messages(
        self,
        conversation_id: str,
        messages: list[dict[str, Any]],
        *,
        status: str | None = None,
    ) -> dict:
        """Replace transcript. Creates the conversation if missing."""
        if not is_valid_id(conversation_id):
            raise ValueError(f"invalid conversation id: {conversation_id!r}")
        if status is not None and status not in ("idle", "running"):
            raise ValueError(f"invalid status: {status!r}")

        cleaned: list[dict] = []
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if role not in ("user", "assistant", "tool"):
                continue
            # Tool rows may have empty content (args/result live in dedicated fields).
            if role != "tool" and not isinstance(content, str):
                continue
            if role == "tool" and content is not None and not isinstance(content, str):
                continue
            if role == "tool" and content is None:
                content = ""
            # Never persist the synthetic welcome bubble
            if m.get("id") == "welcome":
                continue
            # Skip empty pending assistant placeholders
            if (
                role == "assistant"
                and m.get("pending")
                and not (content or "").strip()
                and not (m.get("thinking") or "").strip()
            ):
                continue
            entry: dict[str, Any] = {
                "id": m.get("id") or new_conversation_id(),
                "role": role,
                "content": content if isinstance(content, str) else "",
                "ts": m.get("ts") or _utcnow(),
            }
            if role == "assistant":
                thinking = m.get("thinking")
                if isinstance(thinking, str) and thinking:
                    entry["thinking"] = thinking
            if role == "tool":
                if m.get("toolName"):
                    entry["toolName"] = m["toolName"]
                if m.get("status"):
                    entry["status"] = m["status"]
                if m.get("label"):
                    entry["label"] = m["label"]
                if m.get("toolPhase"):
                    entry["toolPhase"] = m["toolPhase"]
                if m.get("args") is not None:
                    entry["args"] = m["args"] if isinstance(m["args"], str) else str(m["args"])
                if m.get("result") is not None:
                    entry["result"] = m["result"] if isinstance(m["result"], str) else str(m["result"])
                if m.get("callId"):
                    entry["callId"] = m["callId"]
                if m.get("summary") and isinstance(m.get("summary"), str):
                    entry["summary"] = m["summary"]
            cleaned.append(entry)

        now = _utcnow()
        with _lock:
            data = self._read(conversation_id)
            if data is None:
                data = {
                    "id": conversation_id,
                    "title": "New chat",
                    "createdAt": now,
                    "updatedAt": now,
                    "status": "idle",
                    "messages": [],
                }
            data["messages"] = cleaned
            data["updatedAt"] = now
            if status is not None:
                data["status"] = status
            elif "status" not in data:
                data["status"] = "idle"
            title = _title_from_messages(cleaned)
            if title:
                data["title"] = title
            elif not data.get("title"):
                data["title"] = "New chat"
            self._write(data)

        return {
            "id": data["id"],
            "title": data["title"],
            "createdAt": data["createdAt"],
            "updatedAt": data["updatedAt"],
            "status": data.get("status") or "idle",
            "messageCount": len(cleaned),
        }
