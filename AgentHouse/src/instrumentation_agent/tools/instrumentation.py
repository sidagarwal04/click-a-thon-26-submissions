"""Agno Toolkit for instrumentation — delegates to interfaces."""

from __future__ import annotations

from typing import Any

from agno.tools import Toolkit

from instrumentation_agent.interfaces.instrumentation import get_registry, instrument_feature


class InstrumentationTools(Toolkit):
    """Tools the Instrumentation Agno agent can call."""

    def __init__(self, **kwargs: Any) -> None:
        tools = [
            self.instrument_dataset,
            self.get_registry,
        ]
        super().__init__(name="instrumentation_tools", tools=tools, **kwargs)

    def instrument_dataset(
        self,
        feature_id: str = "",
        spec_path: str = "",
    ) -> str:
        """Instrument a feature pack: spec.md (+ optional sibling events.ndjson).

        Prefer evidence from NDJSON when present (do not invent columns). One table
        per event, ORDER BY time+segment keys, PARTITION BY month on timestamp.

        Args:
            feature_id: Feature id (defaults to parent folder of spec.md when empty).
            spec_path: Path to spec.md. Empty string means SPECS_ROOT/{feature_id}/spec.md.
        """
        return instrument_feature(
            feature_id or None,
            spec_path=spec_path or None,
        ).model_dump_json()

    def get_registry(self, feature_id: str) -> str:
        """Return Postgres meta_features + meta_events for a feature_id.

        Args:
            feature_id: Feature id previously instrumented.
        """
        return get_registry(feature_id).model_dump_json()
