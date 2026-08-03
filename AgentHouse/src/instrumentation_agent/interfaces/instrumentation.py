"""Instrumentation interfaces used by instrument/registry routers and Agno tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from instrumentation_agent.db.connection import get_engine
from instrumentation_agent.db.meta_events import MetaEventsCRUD
from instrumentation_agent.db.meta_features import MetaFeaturesCRUD
from instrumentation_agent.models.domain import FeaturePaths
from instrumentation_agent.models.schemas import (
    EventSummary,
    FeatureSpecMetadata,
    InstrumentRequest,
    InstrumentResponse,
    PipelinePlan,
    RegistryResponse,
)
from instrumentation_agent.settings import get_settings
from instrumentation_agent.utils.clickhouse import (
    apply_event_table,
    apply_meta_event_tables_and_activity_mvs,
    get_client,
)
from instrumentation_agent.utils.paths import feature_paths, resolve_feature_paths
from instrumentation_agent.utils.profiler import profile_feature


def get_registry(feature_id: str) -> RegistryResponse:
    features = MetaFeaturesCRUD()
    events = MetaEventsCRUD()
    return RegistryResponse(
        feature_id=feature_id,
        feature=features.get_by_feature_id(feature_id),
        events=events.list_by_feature_id(feature_id),
    )


def register_meta_from_summary(
    metadata: FeatureSpecMetadata,
    *,
    spec_path: str | Path,
) -> dict[str, Any]:
    """Ensure ``meta_features`` + ``meta_events`` from summarize_spec output.

    - If the feature is absent from ``meta_features``, insert it from metadata.
    - For each journey event: insert a new ``meta_events`` row, or if the event
      already exists append this ``feature_id`` as a comma-separated value.
    """
    spec = Path(spec_path).expanduser().resolve()

    journey = [
        {
            "event_name": e.event_name,
            "journey_order": e.journey_order,
            "ch_table": e.ch_table,
        }
        for e in metadata.journey
    ]

    features = MetaFeaturesCRUD()
    events_crud = MetaEventsCRUD()
    created_events: list[str] = []
    linked_events: list[str] = []

    engine = get_engine()
    with engine.begin() as conn:
        feature_created = features.insert_if_missing(
            feature_id=metadata.feature_id,
            spec_path=str(spec),
            journey=journey,
            conn=conn,
        )
        for ev in metadata.journey:
            # Provisional String types until NDJSON profiling fills real CH types.
            columns = {
                col: "String"
                for col in dict.fromkeys([*ev.join_keys, *ev.expected_columns])
            }
            outcome = events_crud.insert_if_missing(
                event_name=ev.event_name,
                feature_id=metadata.feature_id,
                ch_table=ev.ch_table,
                columns=columns,
                conn=conn,
            )
            if outcome == "created":
                created_events.append(ev.event_name)
            elif outcome == "linked":
                linked_events.append(ev.event_name)

    context_added = bool(feature_created or created_events or linked_events)
    return {
        "feature_created": feature_created,
        "events_created": created_events,
        "events_linked": linked_events,
        "context_added": context_added,
    }


def apply_clickhouse_from_meta(feature_id: str) -> PipelinePlan:
    """Create ClickHouse event tables + activity_events MVs from ``meta_events``.

    For each event linked to ``feature_id``:
    1. CREATE TABLE IF NOT EXISTS using ``columns`` from Postgres meta
    2. CREATE MATERIALIZED VIEW IF NOT EXISTS … TO activity_events
       so inserts into the event table flow into the combined activity table
    """
    if not feature_id or not feature_id.strip():
        raise ValueError("feature_id is required")

    events_crud = MetaEventsCRUD()
    events = events_crud.list_by_feature_id(feature_id.strip())
    if not events:
        raise ValueError(
            f"No meta_events rows for feature_id={feature_id!r}; "
            "run register_meta before apply_clickhouse."
        )

    applied = apply_meta_event_tables_and_activity_mvs(events)
    events_crud.mark_status([str(e["event_name"]) for e in events], status="done")

    tables = applied["tables_created"]
    mvs = applied["materialized_views"]
    return PipelinePlan(
        action="create_pipeline",
        rationale=(
            f"Created {len(tables)} ClickHouse event table(s) from meta_events "
            f"and {len(mvs)} materialized view(s) into {applied['activity_table']}."
        ),
        feature_id=feature_id.strip(),
        events_to_materialize=tables,
        pipeline_changes=[
            f"CREATE TABLE IF NOT EXISTS {applied['activity_table']}",
            *[f"CREATE TABLE IF NOT EXISTS {t}" for t in tables],
            *[f"CREATE MATERIALIZED VIEW IF NOT EXISTS {mv}" for mv in mvs],
        ],
        tool_choices=[],
    )


def validate_instrument_request(request: InstrumentRequest) -> FeaturePaths:
    """Validate instrument inputs before the workflow runs.

    Rules:
    - Explicit ``spec_path`` must exist when provided.
    - Else ``SPECS_ROOT/{feature_id}/spec.md`` when that file exists.
    - If ``feature_id`` is not in the Postgres registry and no spec is available,
      ``spec_path`` is required.

    Raises:
        ValueError: invalid/incomplete input (map to HTTP 422).
    """
    if request.spec_path:
        spec = Path(request.spec_path).expanduser()
        if not spec.is_file():
            raise ValueError(
                f"Invalid input: spec_path does not exist or is not a file: {request.spec_path}"
            )
        paths = resolve_feature_paths(
            feature_id=request.feature_id,
            spec_path=request.spec_path,
        )
        return paths

    if not request.feature_id:
        raise ValueError("Invalid input: provide feature_id and/or spec_path")

    paths = feature_paths(request.feature_id)
    if paths.spec_path.is_file():
        return paths

    in_db = False
    try:
        in_db = get_registry(request.feature_id).feature is not None
    except Exception:  # noqa: BLE001
        in_db = False

    if not in_db:
        raise ValueError(
            f"Invalid input: feature_id '{request.feature_id}' is not present in the "
            f"metadata registry and no spec.md was found at {paths.spec_path}. "
            "Provide spec_path (path to spec.md) to instrument a new feature."
        )

    raise ValueError(
        f"Invalid input: feature_id '{request.feature_id}' exists in the registry but "
        f"spec.md is missing at {paths.spec_path}. Provide spec_path."
    )


def instrument_feature(
    feature_id: str | None = None,
    *,
    spec_path: str | Path | None = None,
) -> InstrumentResponse:
    """Profile (optional NDJSON beside spec) → ClickHouse → Postgres metadata.

    Accepts ``SPECS_ROOT/{feature_id}`` or an explicit ``spec_path``.
    ``events.ndjson`` next to the spec is used when present; otherwise CH load is skipped
    and only metadata from an empty profile shell is not written — requires NDJSON for apply.
    """
    paths = resolve_feature_paths(
        feature_id=feature_id,
        spec_path=spec_path,
    )
    paths.require_exists()
    events_path = paths.feature_dir / "events.ndjson"
    if not events_path.is_file():
        raise ValueError(
            f"Cannot apply instrumentation: events.ndjson not found beside spec at {events_path}"
        )

    run_id = uuid4()
    settings = get_settings()
    features = MetaFeaturesCRUD()
    events_crud = MetaEventsCRUD()

    try:
        profile = profile_feature(paths.feature_id, paths.spec_path, events_path)
        client = get_client(settings)
        try:
            for event in profile.events:
                apply_event_table(event, client=client, settings=settings, recreate=True)
        finally:
            client.close()

        engine = get_engine()
        with engine.begin() as conn:
            features.upsert_ok(
                feature_id=paths.feature_id,
                spec_path=str(paths.spec_path),
                events=profile.events,
                conn=conn,
            )
            events_crud.replace_for_feature(
                feature_id=paths.feature_id,
                events=profile.events,
                conn=conn,
            )

        return InstrumentResponse(
            status="ok",
            run_id=str(run_id),
            feature_id=paths.feature_id,
            events=[
                EventSummary(
                    event_name=e.event_name,
                    journey_order=e.journey_order,
                    ch_table=e.ch_table,
                    row_count=e.row_count,
                )
                for e in profile.events
            ],
        )
    except Exception as exc:  # noqa: BLE001
        try:
            features.upsert_failed(
                feature_id=paths.feature_id,
                spec_path=str(paths.spec_path),
            )
        except Exception:  # noqa: BLE001
            pass
        raise
