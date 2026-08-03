from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from app.repositories.clickhouse import ClickHouseRepository
from app.schemas.agents import InstrumentationPlan, MaterializationPlan
from app.schemas.features import (
    ContextDocument,
    EventProfile,
    InsightSummary,
    ProcessFeatureResult,
    RunSummary,
)
from app.tools.base_context import load_base_context

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RunStoreError(RuntimeError):
    """Base error for durable pipeline run storage."""


class InvalidDatabaseNameError(RunStoreError):
    """Raised before interpolating an unsafe ClickHouse database identifier."""


class RunNotFoundError(RunStoreError):
    """Raised when no stored snapshot exists for a run id."""


class ArtifactNotFoundError(RunStoreError):
    """Raised when a requested run artifact has not been generated yet."""


class RunStore(Protocol):
    """Persistence contract used by the transport-independent pipeline."""

    def save_profiled_run(
        self,
        result: ProcessFeatureResult,
        *,
        event_profile: EventProfile,
        spec_sha256: str,
        available_tables: Sequence[str],
    ) -> None: ...

    def get_run_summary(self, run_id: str) -> RunSummary: ...

    def get_artifact(self, run_id: str, artifact_type: str) -> JsonValue: ...

    def get_latest_context(self) -> ContextDocument | None: ...

    def get_context_version(self, version: int) -> ContextDocument | None: ...

    def ensure_base_context(self) -> ContextDocument | None: ...

    def get_schema_contract(self, feature: str) -> InstrumentationPlan | None: ...

    def save_schema_contract(
        self,
        feature: str,
        plan: InstrumentationPlan,
        *,
        fingerprint: str,
        run_id: str,
    ) -> None: ...

    def get_materialization_contract(self, feature: str) -> MaterializationPlan | None: ...

    def save_materialization_contract(
        self,
        feature: str,
        plan: MaterializationPlan,
        *,
        run_id: str,
    ) -> None: ...

    def save_context_version(
        self,
        document: ContextDocument,
        *,
        run_id: str | None,
        now: datetime | None = None,
    ) -> None: ...

    def get_artifacts(self, run_id: str) -> dict[str, JsonValue]: ...


class ClickHouseRunStore:
    """Append-only run snapshots and artifacts stored in ClickHouse."""

    def __init__(
        self,
        repository: ClickHouseRepository,
        *,
        database: str,
    ) -> None:
        if _SAFE_IDENTIFIER.fullmatch(database) is None:
            raise InvalidDatabaseNameError(
                "ClickHouse database must contain only letters, numbers, and "
                "underscores and cannot start with a number"
            )
        self._repository = repository
        self._database = database
        self._initialized = False

    def _table(self, name: str) -> str:
        return f"`{self._database}`.`{name}`"

    def ensure_tables(self) -> None:
        if self._initialized:
            return

        self._repository.command(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table("agent_runs")}
            (
                run_id UUID,
                version UInt64,
                status LowCardinality(String),
                feature String,
                event_count UInt64,
                table_created String DEFAULT '',
                rows_loaded UInt64 DEFAULT 0,
                context_version UInt64 DEFAULT 0,
                insights_json String DEFAULT '[]',
                langfuse_trace_id String DEFAULT '',
                error String DEFAULT '',
                created_at DateTime64(3, 'UTC'),
                updated_at DateTime64(3, 'UTC')
            )
            ENGINE = ReplacingMergeTree(version)
            ORDER BY run_id
            """
        )
        self._repository.command(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table("generated_artifacts")}
            (
                run_id UUID,
                artifact_type LowCardinality(String),
                payload String,
                created_at DateTime64(3, 'UTC')
            )
            ENGINE = ReplacingMergeTree(created_at)
            ORDER BY (run_id, artifact_type)
            """
        )
        self._repository.command(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table("context_versions")}
            (
                version UInt64,
                run_id UUID,
                document String,
                created_at DateTime64(3, 'UTC')
            )
            ENGINE = MergeTree
            ORDER BY version
            """
        )
        self._repository.command(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table("feature_schema_contracts")}
            (
                feature String,
                version UInt64,
                plan String,
                fingerprint FixedString(64),
                run_id UUID,
                created_at DateTime64(3, 'UTC')
            )
            ENGINE = ReplacingMergeTree(version)
            ORDER BY feature
            """
        )
        self._repository.command(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table("feature_materialization_contracts")}
            (
                feature String,
                version UInt64,
                plan String,
                run_id UUID,
                created_at DateTime64(3, 'UTC')
            )
            ENGINE = ReplacingMergeTree(version)
            ORDER BY feature
            """
        )
        self._initialized = True

    def save_profiled_run(
        self,
        result: ProcessFeatureResult,
        *,
        event_profile: EventProfile,
        spec_sha256: str,
        available_tables: Sequence[str],
    ) -> None:
        try:
            self.save_run_snapshot(result, event_count=event_profile.event_count)
            now = datetime.now(UTC)
            artifact: dict[str, JsonValue] = {
                "profile": event_profile.model_dump(mode="json"),
                "spec_sha256": spec_sha256,
                "available_tables": list(available_tables),
            }
            self.save_artifact(result.run_id, "event_profile", artifact, now=now)
        except RunStoreError:
            raise
        except Exception as exc:
            raise RunStoreError(
                f"Could not persist profiled run {result.run_id}: {exc}"
            ) from exc

    def save_run_snapshot(
        self,
        result: ProcessFeatureResult,
        *,
        event_count: int,
        error: str = "",
    ) -> None:
        self.ensure_tables()
        now = datetime.now(UTC)
        version = int(now.timestamp() * 1_000_000)
        insights_json = json.dumps(
            [insight.model_dump(mode="json") for insight in result.insights],
            separators=(",", ":"),
        )
        self._repository.insert(
            "agent_runs",
            [
                [
                    UUID(result.run_id),
                    version,
                    result.status,
                    result.feature,
                    event_count,
                    result.table_created or "",
                    result.rows_loaded,
                    result.context_version or 0,
                    insights_json,
                    result.langfuse_trace_id or "",
                    error,
                    now,
                    now,
                ]
            ],
            column_names=[
                "run_id",
                "version",
                "status",
                "feature",
                "event_count",
                "table_created",
                "rows_loaded",
                "context_version",
                "insights_json",
                "langfuse_trace_id",
                "error",
                "created_at",
                "updated_at",
            ],
            database=self._database,
        )

    def save_artifact(
        self,
        run_id: str,
        artifact_type: str,
        payload: JsonValue,
        *,
        now: datetime | None = None,
    ) -> None:
        self._repository.insert(
            "generated_artifacts",
            [
                [
                    UUID(run_id),
                    artifact_type,
                    json.dumps(payload, separators=(",", ":")),
                    now or datetime.now(UTC),
                ]
            ],
            column_names=["run_id", "artifact_type", "payload", "created_at"],
            database=self._database,
        )

    def next_context_version(self) -> int:
        """Allocate the next context version, called only at the write step."""

        self.ensure_tables()
        rows = self._repository.query_rows(
            f"SELECT max(version) FROM {self._table('context_versions')}"
        )
        if not rows or not rows[0] or rows[0][0] is None:
            return 1
        return int(str(rows[0][0])) + 1

    def get_latest_context(self) -> ContextDocument | None:
        """Return the newest context snapshot, or None before the first write."""

        self.ensure_tables()
        rows = self._repository.query_rows(
            f"""
            SELECT document
            FROM {self._table("context_versions")}
            ORDER BY version DESC
            LIMIT 1
            """
        )
        return self._decode_context_row(rows)

    def get_context_version(self, version: int) -> ContextDocument | None:
        """Return one historical snapshot, or None when that version is absent.

        Every version is written as a complete document, so an older snapshot
        is read directly rather than replayed from its diffs.
        """

        self.ensure_tables()
        rows = self._repository.query_rows(
            f"""
            SELECT document
            FROM {self._table("context_versions")}
            WHERE version = {{version:UInt64}}
            ORDER BY version DESC
            LIMIT 1
            """,
            parameters={"version": version},
        )
        return self._decode_context_row(rows)

    def _decode_context_row(self, rows: Sequence[Sequence[object]]) -> ContextDocument | None:
        if not rows or not rows[0]:
            return None
        try:
            decoded = json.loads(str(rows[0][0]))
        except json.JSONDecodeError as exc:
            raise RunStoreError("Stored context document is not valid JSON") from exc
        if isinstance(decoded, dict):
            decoded = _normalize_legacy_known_issues(decoded)
        return ContextDocument.model_validate(decoded)

    def save_context_version(
        self,
        document: ContextDocument,
        *,
        run_id: str | None,
        now: datetime | None = None,
    ) -> None:
        """Append one immutable context snapshot. Never updates an older row.

        The seeded base layer has no originating run, so `run_id` is optional
        and stored as the nil UUID.
        """

        self.ensure_tables()
        self._repository.insert(
            "context_versions",
            [
                [
                    document.version,
                    UUID(run_id) if run_id is not None else UUID(int=0),
                    json.dumps(document.model_dump(mode="json"), separators=(",", ":")),
                    now or datetime.now(UTC),
                ]
            ],
            column_names=["version", "run_id", "document", "created_at"],
            database=self._database,
        )

    def ensure_base_context(self) -> ContextDocument | None:
        """Seed the hand-written base context layer as the first version.

        The challenge supplies `base_context.md` as the starting semantic layer,
        so it becomes version 1 and every later version accumulates on top of
        it. Seeding is idempotent: once any version exists this is a no-op, so
        a re-run never reintroduces base definitions the Context Agent has
        already superseded.
        """

        self.ensure_tables()
        existing = self.get_latest_context()
        if existing is not None:
            return existing
        base = load_base_context()
        if base is None:
            return None
        self.save_context_version(base, run_id=None)
        return base

    def get_schema_contract(self, feature: str) -> InstrumentationPlan | None:
        """Return the accepted physical schema for a feature, if one exists."""

        self.ensure_tables()
        rows = self._repository.query_rows(
            f"""
            SELECT plan
            FROM {self._table("feature_schema_contracts")} FINAL
            WHERE feature = {{feature:String}}
            LIMIT 1
            """,
            parameters={"feature": feature},
        )
        if not rows:
            return None
        try:
            decoded = json.loads(str(rows[0][0]))
            return InstrumentationPlan.model_validate(decoded)
        except (json.JSONDecodeError, ValueError) as exc:
            raise RunStoreError(
                f"Stored schema contract is invalid for feature {feature!r}"
            ) from exc

    def save_schema_contract(
        self,
        feature: str,
        plan: InstrumentationPlan,
        *,
        fingerprint: str,
        run_id: str,
    ) -> None:
        """Persist the first accepted schema decision for later reruns."""

        self.ensure_tables()
        now = datetime.now(UTC)
        self._repository.insert(
            "feature_schema_contracts",
            [
                [
                    feature,
                    int(now.timestamp() * 1_000_000),
                    json.dumps(plan.model_dump(mode="json"), separators=(",", ":")),
                    fingerprint,
                    UUID(run_id),
                    now,
                ]
            ],
            column_names=[
                "feature",
                "version",
                "plan",
                "fingerprint",
                "run_id",
                "created_at",
            ],
            database=self._database,
        )

    def get_materialization_contract(self, feature: str) -> MaterializationPlan | None:
        self.ensure_tables()
        rows = self._repository.query_rows(
            f"""
            SELECT plan
            FROM {self._table("feature_materialization_contracts")} FINAL
            WHERE feature = {{feature:String}}
            LIMIT 1
            """,
            parameters={"feature": feature},
        )
        if not rows:
            return None
        try:
            decoded = json.loads(str(rows[0][0]))
            return MaterializationPlan.model_validate(decoded)
        except (json.JSONDecodeError, ValueError) as exc:
            raise RunStoreError(
                f"Stored materialization contract is invalid for feature {feature!r}"
            ) from exc

    def save_materialization_contract(
        self,
        feature: str,
        plan: MaterializationPlan,
        *,
        run_id: str,
    ) -> None:
        self.ensure_tables()
        now = datetime.now(UTC)
        self._repository.insert(
            "feature_materialization_contracts",
            [
                [
                    feature,
                    int(now.timestamp() * 1_000_000),
                    json.dumps(plan.model_dump(mode="json"), separators=(",", ":")),
                    UUID(run_id),
                    now,
                ]
            ],
            column_names=["feature", "version", "plan", "run_id", "created_at"],
            database=self._database,
        )

    def get_run_summary(self, run_id: str) -> RunSummary:
        normalized_run_id = _parse_run_id(run_id)
        self.ensure_tables()
        rows = self._repository.query_rows(
            f"""
            SELECT
                toString(run_id), status, feature, table_created, rows_loaded,
                context_version, insights_json, langfuse_trace_id
            FROM {self._table("agent_runs")} FINAL
            WHERE run_id = {{run_id:UUID}}
            ORDER BY version DESC
            LIMIT 1
            """,
            parameters={"run_id": normalized_run_id},
        )
        if not rows:
            raise RunNotFoundError(f"Run not found: {run_id}")

        row = rows[0]
        insights = _parse_insights(str(row[6]))
        context_version = int(str(row[5]))
        return RunSummary(
            run_id=str(row[0]),
            status=str(row[1]),
            feature=str(row[2]),
            table_created=str(row[3]) or None,
            rows_loaded=int(str(row[4])),
            context_version=context_version or None,
            insights=insights,
            langfuse_trace_id=str(row[7]) or None,
        )

    def get_artifact(self, run_id: str, artifact_type: str) -> JsonValue:
        normalized_run_id = _parse_run_id(run_id)
        self.ensure_tables()
        rows = self._repository.query_rows(
            f"""
            SELECT payload
            FROM {self._table("generated_artifacts")} FINAL
            WHERE run_id = {{run_id:UUID}}
              AND artifact_type = {{artifact_type:String}}
            ORDER BY created_at DESC
            LIMIT 1
            """,
            parameters={
                "run_id": normalized_run_id,
                "artifact_type": artifact_type,
            },
        )
        if not rows:
            raise ArtifactNotFoundError(
                f"Artifact {artifact_type!r} is not available for run {run_id}"
            )
        decoded = json.loads(str(rows[0][0]))
        return _as_json_value(decoded)

    def get_artifacts(self, run_id: str) -> dict[str, JsonValue]:
        """Return dashboard-safe artifacts without exposing uploaded raw events."""

        normalized_run_id = _parse_run_id(run_id)
        self.ensure_tables()
        rows = self._repository.query_rows(
            f"""
            SELECT artifact_type, payload
            FROM {self._table("generated_artifacts")} FINAL
            WHERE run_id = {{run_id:UUID}}
            ORDER BY artifact_type
            """,
            parameters={"run_id": normalized_run_id},
        )
        if not rows:
            raise RunNotFoundError(f"Run artifacts not found: {run_id}")

        public_types = {
            "event_profile",
            "instrumentation_plan",
            "materialization_plan",
            "schema",
            "context_diff",
            "proposed_analysis_plan",
            "analysis_plan",
            "query_results",
            "insights",
        }
        artifacts: dict[str, JsonValue] = {}
        for artifact_type, payload in rows:
            name = str(artifact_type)
            if name not in public_types:
                continue
            try:
                artifacts[name] = _as_json_value(json.loads(str(payload)))
            except json.JSONDecodeError as exc:
                raise RunStoreError(
                    f"Stored artifact {name!r} is not valid JSON"
                ) from exc
        return artifacts


def _parse_run_id(run_id: str) -> UUID:
    try:
        return UUID(run_id)
    except ValueError as exc:
        raise RunNotFoundError(f"Invalid run id: {run_id}") from exc


def _normalize_legacy_known_issues(document: dict[str, object]) -> dict[str, object]:
    """Move only K-prefixed issue strings out of legacy conflict snapshots."""

    conflicts = document.get("conflicts")
    if not isinstance(conflicts, list):
        return document
    known_issues = document.get("known_issues")
    normalized_issues = list(known_issues) if isinstance(known_issues, list) else []
    remaining_conflicts: list[object] = []
    changed = False
    issue_pattern = re.compile(
        r"^(?P<key>K\d+)\s*[-–—]\s*(?P<title>[^:]+)(?::\s*(?P<description>.*))?$"
    )
    known_keys = {
        issue.get("key") for issue in normalized_issues if isinstance(issue, dict)
    }
    for conflict in conflicts:
        match = issue_pattern.match(conflict) if isinstance(conflict, str) else None
        if match is None:
            remaining_conflicts.append(conflict)
            continue
        changed = True
        key = match.group("key")
        if key not in known_keys:
            normalized_issues.append(
                {
                    "key": key,
                    "title": match.group("title").strip(),
                    "description": (match.group("description") or "").strip(),
                }
            )
            known_keys.add(key)
    if not changed:
        return document
    normalized = dict(document)
    normalized["known_issues"] = normalized_issues
    normalized["conflicts"] = remaining_conflicts
    return normalized


def _parse_insights(payload: str) -> list[InsightSummary]:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RunStoreError("Stored insights are not valid JSON") from exc
    if not isinstance(decoded, list):
        raise RunStoreError("Stored insights must be a JSON list")
    return [InsightSummary.model_validate(value) for value in decoded]


def _as_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [_as_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _as_json_value(item) for key, item in value.items()}
    raise RunStoreError("Stored artifact contains a non-JSON value")
