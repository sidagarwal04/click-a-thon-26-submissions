from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID, uuid4

import clickhouse_connect
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.types import JsonValue

SENSITIVE_METADATA_KEYS = {
    "credential",
    "credentials",
    "customer_rows",
    "prompt",
    "query_result",
    "raw_data",
    "secret",
    "token",
    "uploaded_values",
}


class UnsafeAuditMetadataError(ValueError):
    pass


def _sensitive_keys(value: JsonValue, path: str = "metadata") -> list[str]:
    if isinstance(value, dict):
        violations: list[str] = []
        for key, nested in value.items():
            child_path = f"{path}.{key}"
            if key.lower() in SENSITIVE_METADATA_KEYS:
                violations.append(child_path)
            violations.extend(_sensitive_keys(nested, child_path))
        return violations
    if isinstance(value, list):
        violations = []
        for index, nested in enumerate(value):
            violations.extend(_sensitive_keys(nested, f"{path}[{index}]"))
        return violations
    return []


class AuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID
    span_id: UUID
    tenant_id: UUID
    investigation_id: UUID
    event_type: str = Field(min_length=1)
    agent_id: str | None = None
    execution_id: UUID | None = None
    step: int | None = Field(default=None, ge=0)
    started_at: datetime
    completed_at: datetime
    latency_ms: int = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    input_hash: str = Field(min_length=1)
    outcome_kind: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    tools_called: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    model: str | None = None
    status: str
    artifact_refs: tuple[str, ...] = ()
    redacted_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("artifact_refs")
    @classmethod
    def validate_artifact_refs(cls, refs: tuple[str, ...]) -> tuple[str, ...]:
        invalid = [ref for ref in refs if not ref.startswith("artifact://")]
        if invalid:
            raise ValueError(
                "Audit artifact references must use the artifact:// scheme"
            )
        return refs

    @field_validator("redacted_metadata")
    @classmethod
    def reject_sensitive_metadata(
        cls, metadata: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        violations = _sensitive_keys(metadata)
        if violations:
            raise UnsafeAuditMetadataError(
                "Audit metadata contains forbidden customer-data fields: "
                + ", ".join(violations)
            )
        return metadata


class ClickHouseClient(Protocol):
    def command(self, command: str, **kwargs: Any) -> Any: ...

    def insert(
        self,
        table: str,
        data: list[list[Any]],
        *,
        column_names: list[str],
    ) -> Any: ...

    def query(self, query: str, *, parameters: dict[str, Any]) -> Any: ...

    def close(self) -> None: ...


class AuditRepository:
    columns = [
        "entry_id",
        "trace_id",
        "span_id",
        "tenant_id",
        "investigation_id",
        "event_type",
        "agent_id",
        "execution_id",
        "step",
        "started_at",
        "completed_at",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "total_cost_usd",
        "input_hash",
        "outcome_kind",
        "confidence",
        "tools_called",
        "errors",
        "model",
        "status",
        "artifact_refs",
        "redacted_metadata",
        "created_at",
    ]

    def __init__(
        self,
        client: ClickHouseClient | None = None,
        *,
        client_factory: Callable[[], ClickHouseClient] | None = None,
    ) -> None:
        if client is None and client_factory is None:
            raise ValueError("A ClickHouse client or client factory is required")
        self._client = client
        self._client_factory = client_factory

    def _get_client(self) -> ClickHouseClient:
        if self._client is None:
            assert self._client_factory is not None
            self._client = self._client_factory()
        return self._client

    @classmethod
    def connect(
        cls,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        secure: bool,
    ) -> AuditRepository:
        return cls(
            client_factory=lambda: clickhouse_connect.get_client(
                host=host,
                port=port,
                username=username,
                password=password,
                database=database,
                secure=secure,
            )
        )

    async def health(self) -> bool:
        try:
            await asyncio.to_thread(lambda: self._get_client().command("SELECT 1"))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.close)

    async def append(self, entry: AuditEntry) -> None:
        serialized = entry.model_dump(mode="python")
        serialized["tools_called"] = list(entry.tools_called)
        serialized["errors"] = list(entry.errors)
        serialized["artifact_refs"] = list(entry.artifact_refs)
        serialized["redacted_metadata"] = json.dumps(
            entry.redacted_metadata,
            separators=(",", ":"),
            sort_keys=True,
        )
        row = [serialized[column] for column in self.columns]
        await asyncio.to_thread(
            lambda: self._get_client().insert(
                "audit_entries",
                [row],
                column_names=self.columns,
            )
        )

    async def list_for_investigation(
        self,
        *,
        tenant_id: UUID,
        investigation_id: UUID,
    ) -> list[dict[str, Any]]:
        result = await asyncio.to_thread(
            lambda: self._get_client().query(
                """
                SELECT *
                FROM audit_entries
                WHERE tenant_id = {tenant_id:UUID}
                  AND investigation_id = {investigation_id:UUID}
                ORDER BY created_at, entry_id
                """,
                parameters={
                    "tenant_id": str(tenant_id),
                    "investigation_id": str(investigation_id),
                },
            )
        )
        rows = [
            dict(zip(result.column_names, row, strict=True))
            for row in result.result_rows
        ]
        deduplicated: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            deduplicated.setdefault(UUID(str(row["entry_id"])), row)
        return list(deduplicated.values())
