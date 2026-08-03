"""Mocked pipeline tools for workflow step 2 (real implementations come later)."""

from __future__ import annotations

import json
from typing import Any

from agno.tools import Toolkit


class PipelineTools(Toolkit):
    """Placeholder tools the pipeline planner can choose among.

    Replace the bodies later with real create/update/inspect logic.
    """

    def __init__(self, **kwargs: Any) -> None:
        tools = [
            self.inspect_existing_pipeline,
            self.create_pipeline,
            self.update_pipeline,
            self.skip_pipeline,
        ]
        super().__init__(name="pipeline_tools", tools=tools, **kwargs)

    def inspect_existing_pipeline(self, feature_id: str) -> str:
        """Inspect whether a pipeline already exists for this feature (MOCKED).

        Args:
            feature_id: Feature id to look up.
        """
        print("inspect_existing_pipeline", feature_id)
        from instrumentation_agent.interfaces.instrumentation import get_registry

        # Look up the feature in the metadata registry (MetaFeaturesCRUD via get_registry)
        registry = get_registry(feature_id)
        exists = registry.feature is not None
        status = "found" if exists else "not_found"
        message = (
            f"Existing pipeline found in meta_features for feature_id={feature_id}."
            if exists
            else "No existing pipeline registered (mock)."
        )
        print("message", message)
        print("END inspect_existing_pipeline")
        return json.dumps(
            {
                "mock": True,
                "feature_id": feature_id,
                "exists": exists,
                "status": status,
                "message": message,
                "event_count": len(registry.events),
            }
        )

    def create_pipeline(
        self,
        feature_id: str,
        event_names: str = "",
        notes: str = "",
    ) -> str:
        """Create a new instrumentation pipeline for the feature (MOCKED).

        Args:
            feature_id: Feature id to instrument.
            event_names: Comma-separated event / table names to materialize.
            notes: Optional planner notes for the mock pipeline.
        """
        events = [e.strip() for e in event_names.split(",") if e.strip()]
        return json.dumps(
            {
                "mock": True,
                "action": "create_pipeline",
                "feature_id": feature_id,
                "events": events,
                "notes": notes,
                "status": "accepted",
                "message": "Mock create_pipeline accepted; real CH/PG apply comes later.",
            }
        )

    def update_pipeline(
        self,
        feature_id: str,
        changes: str = "",
        event_names: str = "",
    ) -> str:
        """Update an existing instrumentation pipeline (MOCKED).

        Args:
            feature_id: Feature id whose pipeline should change.
            changes: Free-text description of requested pipeline changes.
            event_names: Comma-separated events affected by the change.
        """
        events = [e.strip() for e in event_names.split(",") if e.strip()]
        return json.dumps(
            {
                "mock": True,
                "action": "update_pipeline",
                "feature_id": feature_id,
                "events": events,
                "changes": changes,
                "status": "accepted",
                "message": "Mock update_pipeline accepted; real apply comes later.",
            }
        )

    def skip_pipeline(self, feature_id: str, reason: str = "") -> str:
        """Skip building or changing a pipeline for this feature (MOCKED).

        Args:
            feature_id: Feature id to skip.
            reason: Why no pipeline work is needed.
        """
        return json.dumps(
            {
                "mock": True,
                "action": "skip_pipeline",
                "feature_id": feature_id,
                "reason": reason,
                "status": "skipped",
                "message": "Mock skip_pipeline recorded.",
            }
        )
