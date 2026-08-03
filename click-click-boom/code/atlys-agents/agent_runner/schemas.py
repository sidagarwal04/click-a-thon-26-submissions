"""Strict OpenAI Structured Outputs (json_schema, strict=true) per agent.

Confirmed via direct testing: strict json_schema works together with tool
calling in the same Responses API call, and guarantees every required key and
type in the FINAL message -- not just "valid JSON" (which json_object mode
gives, and which real runs proved insufficient: after extensive tool
exploration, the model drifted on a DIFFERENT structural field almost every
revision -- column_mapping, then ordering_key_candidates, then columns_ddl
twice -- burning an entire 4-revision budget on JSON formatting instead of
substance). This is the actual, durable fix for that whole bug class.

Strict mode's real constraints, applied throughout below:
  - Every property in `properties` must also appear in `required` (no true
    optional fields -- a field that's sometimes empty is still always PRESENT,
    just with an empty string/array).
  - Every object needs `additionalProperties: false`, including nested ones.
  - Arbitrary/dynamic-key maps aren't expressible -- reshaped:
      column_mapping: {raw_field: column_name} -> array of
        {raw_field, column_name} pairs (orchestrator/pipeline.py's
        _flatten_events reshapes this back into a dict at the point of use).
      chronicler sections[].fields: was a free-form nested object (whatever
        machine-readable numbers a section needs) -> a plain JSON-encoded
        STRING instead. Its shape genuinely varies per section; a string the
        model formats itself is the simplest strict-compatible representation,
        and orchestrator/pipeline.py's _write_context_sections already treats
        it as opaque content, not something it parses.
"""
from __future__ import annotations

_STRING = {"type": "string"}
_NUMBER = {"type": "number"}


def _strict_object(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties.keys()),
        "additionalProperties": False,
    }


_ORDERING_KEY_CANDIDATE = _strict_object({
    "label": _STRING, "ordering_key": _STRING, "partition_key": _STRING, "rationale": _STRING,
})

_COLUMN_MAPPING_ENTRY = _strict_object({"raw_field": _STRING, "column_name": _STRING})

_PM_QUESTION_COVERAGE = _strict_object({
    "question": _STRING,
    "servable_by": {"type": "string", "enum": ["base_table", "materialized_view"]},
    "note": _STRING,
})

_MATERIALIZED_VIEW = _strict_object({
    "name": _STRING, "answers_pm_question": _STRING, "ddl": _STRING,
})

INSTRUMENTATION_PROPOSER_SCHEMA = _strict_object({
    "table_name": _STRING,
    "columns_ddl": _STRING,
    "ordering_key_candidates": {"type": "array", "items": _ORDERING_KEY_CANDIDATE},
    "column_mapping": {"type": "array", "items": _COLUMN_MAPPING_ENTRY},
    "pm_question_coverage": {"type": "array", "items": _PM_QUESTION_COVERAGE},
    "materialized_views": {"type": "array", "items": _MATERIALIZED_VIEW},
    "confidence": _NUMBER,
    "rationale": _STRING,
})

_FINDING = _strict_object({
    "severity": {"type": "string", "enum": ["block", "warn", "info"]},
    "category": _STRING, "description": _STRING, "suggested_fix": _STRING,
})

CONTEXT_REVIEWER_SCHEMA = _strict_object({
    "verdict": {"type": "string", "enum": ["approve", "request_changes", "block"]},
    "findings": {"type": "array", "items": _FINDING},
    "context_sections_used": {"type": "array", "items": _STRING},
    "reviewer_confidence": _NUMBER,
})

_CONTEXT_SECTION = _strict_object({
    "section": _STRING, "title": _STRING, "summary": _STRING, "body": _STRING,
    "fields": _STRING,  # JSON-encoded string, model's own formatting -- see module docstring
    "sources": {"type": "array", "items": _STRING},
    "before": _STRING, "diff_summary": _STRING, "rationale": _STRING, "confidence": _NUMBER,
})

CONTEXT_CHRONICLER_SCHEMA = _strict_object({
    "sections": {"type": "array", "items": _CONTEXT_SECTION},
})

_KNOWN_ISSUE = _strict_object({
    "issue": _STRING, "matching_criteria": _STRING,
    "status": {"type": "string", "enum": ["confirmed", "partial", "contradicted", "untested"]},
})

ANALYTICS_AGENT_SCHEMA = _strict_object({
    "title": _STRING, "summary": _STRING,
    "segment_cuts": {"type": "array", "items": _STRING},
    "related_known_issues": {"type": "array", "items": _KNOWN_ISSUE},
    "confidence": _NUMBER, "confidence_drivers": _STRING,
    "report_html": _STRING,
})

SCHEMAS: dict[str, dict] = {
    "instrumentation_proposer": INSTRUMENTATION_PROPOSER_SCHEMA,
    "context_reviewer": CONTEXT_REVIEWER_SCHEMA,
    "context_chronicler": CONTEXT_CHRONICLER_SCHEMA,
    "analytics_agent": ANALYTICS_AGENT_SCHEMA,
}
