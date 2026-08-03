import hashlib
import json
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Never, cast

from app.schemas.features import (
    EventFieldStats,
    EventProfile,
    FieldProfile,
    JsonScalar,
    ObservedFieldType,
)

DEFAULT_MAX_EVENT_LINE_BYTES = 1024 * 1024
DEFAULT_CARDINALITY_SAMPLE_SIZE = 1024
DEFAULT_MAX_FIELDS = 512
DEFAULT_MAX_EVENT_NAMES = 1024
DEFAULT_MAX_FIELD_NAME_LENGTH = 256
DEFAULT_MAX_EVENT_NAME_LENGTH = 256
DEFAULT_MAX_EXAMPLE_BYTES = 256
DEFAULT_MAX_NESTING_DEPTH = 5
MAX_STRING_VALUES_ANALYSED_PER_FIELD = 500
MAX_ARRAY_ELEMENTS_PROFILED = 20
MAX_EXAMPLES = 5
PROFILER_VERSION = "2.0.0"
_HASH_SPACE_SIZE = 1 << 64
_TYPE_ORDER = {field_type: index for index, field_type in enumerate(ObservedFieldType)}
_STRONG_EVENT_NAME_FIELDS = ("event_name", "event")
_BOOLEAN_STRINGS = {"true", "false", "yes", "no", "0", "1"}
_IDENTIFIER_NAME = re.compile(
    r"(?:^|_)(?:event|user|application|session|share|group)?_?id$", re.I
)
_IDENTIFIER_VALUE = re.compile(
    r"^(?=[A-Za-z0-9_-]*\d)[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)+$"
)
_NUMERIC_STRING = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


class EventProfilerError(Exception):
    """Base exception for deterministic NDJSON profiling failures."""


class EventFileError(EventProfilerError):
    """Raised when an event file cannot be read."""


class EventLineTooLongError(EventProfilerError):
    """Raised when one NDJSON record exceeds the configured byte bound."""


class InvalidEventError(EventProfilerError):
    """Raised when an NDJSON line is not a valid JSON object."""


class TooManyFieldsError(EventProfilerError):
    """Raised when input exceeds the configured distinct-field bound."""


class TooManyEventNamesError(EventProfilerError):
    """Raised when input exceeds the configured event-name bound."""


class EventProfilerConfigurationError(EventProfilerError):
    """Raised when profiler limits are invalid."""


@dataclass
class _CardinalityEstimator:
    sample_size: int
    hashes: set[int] = field(default_factory=set)
    overflowed: bool = False

    def add(self, canonical_value: bytes) -> None:
        value_hash = int.from_bytes(
            hashlib.blake2b(canonical_value, digest_size=8).digest()
        )
        if value_hash in self.hashes:
            return
        if len(self.hashes) < self.sample_size:
            self.hashes.add(value_hash)
            return
        self.overflowed = True
        largest_hash = max(self.hashes)
        if value_hash < largest_hash:
            self.hashes.remove(largest_hash)
            self.hashes.add(value_hash)

    def estimate(self) -> tuple[int, bool]:
        if not self.overflowed:
            return len(self.hashes), False
        largest_hash = max(self.hashes)
        if largest_hash == 0:
            return len(self.hashes), True
        estimate = round((self.sample_size - 1) * _HASH_SPACE_SIZE / largest_hash)
        return max(estimate, self.sample_size + 1), True


@dataclass
class _EventFieldState:
    presence_count: int = 0
    null_count: int = 0
    non_null_count: int = 0


@dataclass
class _FieldState:
    cardinality: _CardinalityEstimator
    presence_count: int = 0
    null_count: int = 0
    non_null_count: int = 0
    observed_types: set[ObservedFieldType] = field(default_factory=set)
    examples: list[JsonScalar] = field(default_factory=list)
    example_keys: set[bytes] = field(default_factory=set)
    by_event: dict[str, _EventFieldState] = field(default_factory=dict)
    minimum: int | float | None = None
    maximum: int | float | None = None
    negative_count: int = 0
    zero_count: int = 0
    maximum_decimal_places: int = 0
    minimum_length: int | None = None
    maximum_length: int | None = None
    empty_count: int = 0
    element_types: set[ObservedFieldType] = field(default_factory=set)
    object_field_names: set[str] = field(default_factory=set)
    string_values_analysed: int = 0
    string_type_counts: Counter[str] = field(default_factory=Counter)
    case_variants: dict[str, set[str]] = field(default_factory=dict)


def _reject_nonstandard_number(value: str) -> Never:
    raise ValueError(f"Non-standard JSON number is not allowed: {value}")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _observed_type(value: object) -> ObservedFieldType:
    if value is None:
        return ObservedFieldType.NULL
    if isinstance(value, bool):
        return ObservedFieldType.BOOLEAN
    if isinstance(value, int):
        return ObservedFieldType.INTEGER
    if isinstance(value, float):
        return ObservedFieldType.FLOAT
    if isinstance(value, str):
        return ObservedFieldType.STRING
    if isinstance(value, dict):
        return ObservedFieldType.OBJECT
    if isinstance(value, list):
        return ObservedFieldType.ARRAY
    raise TypeError(f"Unsupported decoded JSON value: {type(value).__name__}")


def _inferred_type(observed_types: set[ObservedFieldType]) -> ObservedFieldType:
    non_null_types = observed_types - {ObservedFieldType.NULL}
    if not non_null_types:
        return ObservedFieldType.NULL
    if len(non_null_types) == 1:
        return next(iter(non_null_types))
    if non_null_types <= {ObservedFieldType.INTEGER, ObservedFieldType.FLOAT}:
        return ObservedFieldType.FLOAT
    return ObservedFieldType.MIXED


def _looks_like_timestamp(value: str) -> bool:
    candidate = value.strip()
    if "T" not in candidate and not re.match(r"^\d{4}-\d{2}-\d{2} ", candidate):
        return False
    try:
        datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


def _decimal_places(value: int | float) -> int:
    if isinstance(value, int):
        return 0
    exponent = Decimal(str(value)).as_tuple().exponent
    return max(0, -cast(int, exponent))


def _example_shape(value: JsonScalar) -> str:
    if isinstance(value, str):
        prefix_match = re.match(r"^([A-Za-z]+)[_-][A-Za-z0-9_-]+$", value)
        if prefix_match:
            return f"{prefix_match.group(1)}_<alphanumeric>"
        if _looks_like_uuid(value):
            return "<uuid>"
        return "<alphanumeric>"
    if isinstance(value, int):
        return "<integer>"
    if isinstance(value, float):
        return "<number>"
    return "<identifier>"


def _identifier_name(field_name: str) -> bool:
    return bool(_IDENTIFIER_NAME.search(field_name.rsplit(".", 1)[-1]))


def _validate_limits(
    *,
    max_line_bytes: int,
    cardinality_sample_size: int,
    max_examples: int,
    max_fields: int,
    max_event_names: int,
    max_field_name_length: int,
    max_event_name_length: int,
    max_example_bytes: int,
    max_nesting_depth: int,
    max_string_values_analysed_per_field: int,
    max_array_elements_profiled: int,
) -> None:
    positive_limits = {
        "max_line_bytes": max_line_bytes,
        "max_fields": max_fields,
        "max_event_names": max_event_names,
        "max_field_name_length": max_field_name_length,
        "max_event_name_length": max_event_name_length,
        "max_example_bytes": max_example_bytes,
        "max_nesting_depth": max_nesting_depth,
        "max_string_values_analysed_per_field": max_string_values_analysed_per_field,
        "max_array_elements_profiled": max_array_elements_profiled,
    }
    invalid_names = [name for name, value in positive_limits.items() if value < 1]
    if invalid_names:
        raise EventProfilerConfigurationError(
            f"Profiler limits must be positive: {', '.join(invalid_names)}"
        )
    if cardinality_sample_size < 2:
        raise EventProfilerConfigurationError(
            "cardinality_sample_size must be at least 2"
        )
    if not 0 <= max_examples <= MAX_EXAMPLES:
        raise EventProfilerConfigurationError(
            f"max_examples must be between 0 and {MAX_EXAMPLES}"
        )


def _detect_event_name_field(
    event: dict[str, object], explicit_field: str | None
) -> tuple[str | None, float]:
    if explicit_field is not None:
        return explicit_field, 1.0
    for field_name in _STRONG_EVENT_NAME_FIELDS:
        value = event.get(field_name)
        if isinstance(value, str) and value.strip():
            return field_name, 0.98 if field_name == "event_name" else 0.9
    # Generic keys are accepted only when they contain a plausible short label.
    for field_name, confidence in (("type", 0.55), ("name", 0.35)):
        value = event.get(field_name)
        if (
            isinstance(value, str)
            and value.strip()
            and len(value.strip()) <= 64
            and not _looks_like_uuid(value.strip())
        ):
            return field_name, confidence
    return None, 0.0


def _flatten_fields(
    event: dict[str, object], max_nesting_depth: int
) -> list[tuple[str, object]]:
    flattened: list[tuple[str, object]] = []
    seen: set[str] = set()

    def visit(path: str, value: object, depth: int) -> None:
        if path in seen:
            return
        seen.add(path)
        flattened.append((path, value))
        if isinstance(value, dict) and depth < max_nesting_depth:
            for child_name, child_value in value.items():
                visit(f"{path}.{child_name}", child_value, depth + 1)

    for field_name, value in event.items():
        visit(field_name, value, 0)
    return flattened


def _update_string(state: _FieldState, value: str, analysis_limit: int) -> None:
    length = len(value)
    state.minimum_length = (
        length if state.minimum_length is None else min(state.minimum_length, length)
    )
    state.maximum_length = (
        length if state.maximum_length is None else max(state.maximum_length, length)
    )
    if state.string_values_analysed >= analysis_limit:
        return
    state.string_values_analysed += 1
    stripped = value.strip()
    if _looks_like_timestamp(stripped):
        state.string_type_counts["iso_timestamp"] += 1
    if _looks_like_uuid(stripped):
        state.string_type_counts["uuid"] += 1
    if _NUMERIC_STRING.fullmatch(stripped):
        try:
            Decimal(stripped)
        except InvalidOperation:
            pass
        else:
            state.string_type_counts["numeric_string"] += 1
    if stripped.casefold() in _BOOLEAN_STRINGS:
        state.string_type_counts["boolean_string"] += 1
    if _IDENTIFIER_VALUE.fullmatch(stripped) or _looks_like_uuid(stripped):
        state.string_type_counts["identifier_like"] += 1
    state.case_variants.setdefault(stripped.casefold(), set()).add(stripped)


def _update_array(state: _FieldState, value: list[object], element_limit: int) -> None:
    length = len(value)
    state.minimum_length = (
        length if state.minimum_length is None else min(state.minimum_length, length)
    )
    state.maximum_length = (
        length if state.maximum_length is None else max(state.maximum_length, length)
    )
    if not value:
        state.empty_count += 1
    for element in value[:element_limit]:
        state.element_types.add(_observed_type(element))
        if isinstance(element, dict):
            state.object_field_names.update(str(key) for key in element)


def _update_state(
    state: _FieldState,
    value: object,
    event_name: str | None,
    *,
    max_examples: int,
    max_example_bytes: int,
    string_analysis_limit: int,
    array_element_limit: int,
) -> None:
    observed_type = _observed_type(value)
    state.presence_count += 1
    state.observed_types.add(observed_type)
    if value is None:
        state.null_count += 1
    else:
        state.non_null_count += 1
    if event_name is not None:
        event_state = state.by_event.setdefault(event_name, _EventFieldState())
        event_state.presence_count += 1
        if value is None:
            event_state.null_count += 1
        else:
            event_state.non_null_count += 1

    is_scalar = value is None or isinstance(value, str | int | float | bool)
    canonical_value: bytes | None = None
    if is_scalar:
        canonical_value = _canonical_json(value)
        state.cardinality.add(canonical_value)

    if isinstance(value, int | float) and not isinstance(value, bool):
        state.minimum = value if state.minimum is None else min(state.minimum, value)
        state.maximum = value if state.maximum is None else max(state.maximum, value)
        if value < 0:
            state.negative_count += 1
        if value == 0:
            state.zero_count += 1
        state.maximum_decimal_places = max(
            state.maximum_decimal_places, _decimal_places(value)
        )
    elif isinstance(value, str):
        _update_string(state, value, string_analysis_limit)
    elif isinstance(value, list):
        _update_array(state, value, array_element_limit)

    if (
        is_scalar
        and canonical_value is not None
        and len(state.examples) < max_examples
        and len(canonical_value) <= max_example_bytes
        and canonical_value not in state.example_keys
    ):
        state.examples.append(cast(JsonScalar, value))
        state.example_keys.add(canonical_value)


def _quality_flags(
    state: _FieldState,
    inferred_type: ObservedFieldType,
    cardinality: int,
    event_count: int,
    identifier_like: bool,
) -> list[str]:
    flags: list[str] = []
    if inferred_type is ObservedFieldType.MIXED:
        flags.append("MIXED_TYPES")
    if state.presence_count and state.null_count / state.presence_count >= 0.5:
        flags.append("HIGH_NULL_RATE")
    if event_count and (event_count - state.presence_count) / event_count >= 0.5:
        flags.append("HIGH_MISSING_RATE")
    analysed = state.string_values_analysed
    if analysed and state.string_type_counts["iso_timestamp"] / analysed >= 0.8:
        flags.append("LIKELY_TIMESTAMP")
    if identifier_like:
        flags.append("LIKELY_IDENTIFIER")
    if state.non_null_count and cardinality == 1:
        flags.append("CONSTANT_FIELD")
    elif (
        state.non_null_count
        and cardinality <= 20
        and cardinality / state.non_null_count <= 0.1
    ):
        flags.append("LOW_CARDINALITY")
    if state.non_null_count and cardinality / state.non_null_count >= 0.9:
        flags.append("NEAR_UNIQUE")
    if analysed and state.string_type_counts["numeric_string"] / analysed >= 0.8:
        flags.append("NUMERIC_STRING")
    if any(len(variants) > 1 for variants in state.case_variants.values()):
        flags.append("INCONSISTENT_CASE")
    return flags


def profile_events(
    events_path: str | Path,
    *,
    event_name_field: str | None = None,
    max_line_bytes: int = DEFAULT_MAX_EVENT_LINE_BYTES,
    cardinality_sample_size: int = DEFAULT_CARDINALITY_SAMPLE_SIZE,
    max_examples: int = MAX_EXAMPLES,
    max_fields: int = DEFAULT_MAX_FIELDS,
    max_event_names: int = DEFAULT_MAX_EVENT_NAMES,
    max_field_name_length: int = DEFAULT_MAX_FIELD_NAME_LENGTH,
    max_event_name_length: int = DEFAULT_MAX_EVENT_NAME_LENGTH,
    max_example_bytes: int = DEFAULT_MAX_EXAMPLE_BYTES,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
    max_string_values_analysed_per_field: int = MAX_STRING_VALUES_ANALYSED_PER_FIELD,
    max_array_elements_profiled: int = MAX_ARRAY_ELEMENTS_PROFILED,
) -> EventProfile:
    """Profile NDJSON in one bounded streaming pass."""

    started = time.perf_counter()
    _validate_limits(
        max_line_bytes=max_line_bytes,
        cardinality_sample_size=cardinality_sample_size,
        max_examples=max_examples,
        max_fields=max_fields,
        max_event_names=max_event_names,
        max_field_name_length=max_field_name_length,
        max_event_name_length=max_event_name_length,
        max_example_bytes=max_example_bytes,
        max_nesting_depth=max_nesting_depth,
        max_string_values_analysed_per_field=max_string_values_analysed_per_field,
        max_array_elements_profiled=max_array_elements_profiled,
    )
    if event_name_field is not None and not event_name_field.strip():
        raise EventProfilerConfigurationError("event_name_field must not be blank")

    path = Path(events_path)
    field_states: dict[str, _FieldState] = {}
    event_names: Counter[str] = Counter()
    event_count = 0
    unnamed_event_count = 0
    detected_event_name_field = event_name_field
    event_name_detection_confidence = 1.0 if event_name_field else 0.0
    source_hash = hashlib.sha256()

    try:
        event_file = path.open("rb")
    except OSError as exc:
        raise EventFileError(f"Could not open event file: {path}") from exc

    try:
        with event_file:
            line_number = 0
            while True:
                raw_line = event_file.readline(max_line_bytes + 2)
                if not raw_line:
                    break
                source_hash.update(raw_line)
                line_number += 1
                payload = raw_line.rstrip(b"\r\n")
                if len(payload) > max_line_bytes:
                    raise EventLineTooLongError(
                        f"Event line {line_number} exceeds the {max_line_bytes}-byte limit."
                    )
                if not payload.strip():
                    continue
                try:
                    text = payload.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise InvalidEventError(
                        f"Event line {line_number} is not valid UTF-8."
                    ) from exc
                try:
                    decoded = json.loads(
                        text, parse_constant=_reject_nonstandard_number
                    )
                except (json.JSONDecodeError, RecursionError, ValueError) as exc:
                    raise InvalidEventError(
                        f"Event line {line_number} is not valid JSON: {exc}"
                    ) from exc
                if not isinstance(decoded, dict):
                    raise InvalidEventError(
                        f"Event line {line_number} must contain a JSON object."
                    )

                event = cast(dict[str, object], decoded)
                event_count += 1
                # Auto-detection is record-local because real NDJSON samples can
                # mix common discriminator keys (event_name/event/type/name).
                # Keep the strongest detected field as profile metadata while
                # still classifying each row with the best key it contains.
                row_event_name_field, row_detection_confidence = (
                    _detect_event_name_field(event, event_name_field)
                )
                if row_detection_confidence > event_name_detection_confidence:
                    detected_event_name_field = row_event_name_field
                    event_name_detection_confidence = row_detection_confidence
                raw_name = (
                    event.get(row_event_name_field)
                    if row_event_name_field
                    else None
                )
                name = (
                    raw_name.strip()
                    if isinstance(raw_name, str) and raw_name.strip()
                    else None
                )
                if name is None:
                    unnamed_event_count += 1
                else:
                    if len(name) > max_event_name_length:
                        raise InvalidEventError(
                            f"Event name on line {line_number} exceeds the {max_event_name_length}-character limit."
                        )
                    if name not in event_names and len(event_names) >= max_event_names:
                        raise TooManyEventNamesError(
                            f"Event file exceeds the {max_event_names} distinct event-name limit."
                        )
                    event_names[name] += 1

                for field_name, value in _flatten_fields(event, max_nesting_depth):
                    if len(field_name) > max_field_name_length:
                        raise InvalidEventError(
                            f"Field name on line {line_number} exceeds the {max_field_name_length}-character limit."
                        )
                    state = field_states.get(field_name)
                    if state is None:
                        if len(field_states) >= max_fields:
                            raise TooManyFieldsError(
                                f"Event file exceeds the {max_fields} distinct-field limit."
                            )
                        state = _FieldState(
                            cardinality=_CardinalityEstimator(cardinality_sample_size)
                        )
                        field_states[field_name] = state
                    try:
                        _update_state(
                            state,
                            value,
                            name,
                            max_examples=max_examples,
                            max_example_bytes=max_example_bytes,
                            string_analysis_limit=max_string_values_analysed_per_field,
                            array_element_limit=max_array_elements_profiled,
                        )
                    except (RecursionError, TypeError, ValueError) as exc:
                        raise InvalidEventError(
                            f"Field {field_name!r} on event line {line_number} cannot be represented safely as JSON."
                        ) from exc
    except OSError as exc:
        raise EventFileError(f"Could not read event file: {path}") from exc

    fields: dict[str, FieldProfile] = {}
    for field_name, state in field_states.items():
        cardinality, cardinality_is_estimate = state.cardinality.estimate()
        observed_types = sorted(state.observed_types, key=_TYPE_ORDER.__getitem__)
        inferred_type = _inferred_type(state.observed_types)
        non_null_cardinality = max(0, cardinality - (1 if state.null_count else 0))
        name_is_identifier = _identifier_name(field_name)
        values_are_identifiers = (
            state.string_values_analysed > 0
            and state.string_type_counts["identifier_like"]
            / state.string_values_analysed
            >= 0.8
            and non_null_cardinality / max(1, state.non_null_count) >= 0.8
        )
        identifier_like = name_is_identifier or values_are_identifiers
        by_event: dict[str, EventFieldStats] = {}
        for event_name, event_total in event_names.items():
            event_state = state.by_event.get(event_name, _EventFieldState())
            presence_rate = event_state.presence_count / event_total
            by_event[event_name] = EventFieldStats(
                presence_count=event_state.presence_count,
                missing_count=event_total - event_state.presence_count,
                null_count=event_state.null_count,
                non_null_count=event_state.non_null_count,
                presence=presence_rate,
                presence_rate=presence_rate,
                null_rate_when_present=(
                    event_state.null_count / event_state.presence_count
                    if event_state.presence_count
                    else 0.0
                ),
            )
        presence_rate = state.presence_count / event_count if event_count else 0.0
        examples = [] if identifier_like else state.examples
        example_shape = (
            _example_shape(state.examples[0])
            if identifier_like and state.examples
            else None
        )
        fields[field_name] = FieldProfile(
            observed_type=inferred_type,
            observed_types=observed_types,
            presence_count=state.presence_count,
            missing_count=event_count - state.presence_count,
            null_count=state.null_count,
            non_null_count=state.non_null_count,
            presence=presence_rate,
            presence_rate=presence_rate,
            global_presence=presence_rate,
            null_rate_when_present=state.null_count / state.presence_count
            if state.presence_count
            else 0.0,
            by_event=by_event,
            approx_cardinality=cardinality,
            cardinality_is_estimate=cardinality_is_estimate,
            examples=examples,
            examples_redacted=identifier_like,
            example_shape=example_shape,
            minimum=state.minimum,
            maximum=state.maximum,
            negative_count=state.negative_count,
            zero_count=state.zero_count,
            maximum_decimal_places=state.maximum_decimal_places,
            minimum_length=state.minimum_length,
            maximum_length=state.maximum_length,
            empty_count=state.empty_count,
            element_types=sorted(state.element_types, key=_TYPE_ORDER.__getitem__),
            object_field_names=sorted(state.object_field_names),
            string_values_analysed=state.string_values_analysed,
            string_type_counts=dict(state.string_type_counts),
            identifier_like=identifier_like,
            quality_flags=_quality_flags(
                state,
                inferred_type,
                non_null_cardinality,
                event_count,
                identifier_like,
            ),
        )

    common_envelope_fields = sorted(
        field_name
        for field_name, profile in fields.items()
        if profile.presence_rate == 1.0
    )
    common_set = set(common_envelope_fields)
    event_specific_fields: dict[str, list[str]] = {}
    for event_name in event_names:
        specific = []
        for field_name, profile in fields.items():
            stats = profile.by_event[event_name]
            other_presence = [
                other.presence_rate
                for other_name, other in profile.by_event.items()
                if other_name != event_name
            ]
            if (
                field_name not in common_set
                and stats.presence_rate >= 0.8
                and (not other_presence or max(other_presence) < stats.presence_rate)
            ):
                specific.append(field_name)
        event_specific_fields[event_name] = sorted(specific)

    configuration: dict[str, int | str | bool] = {
        "max_line_bytes": max_line_bytes,
        "cardinality_sample_size": cardinality_sample_size,
        "max_examples": max_examples,
        "max_fields": max_fields,
        "max_event_names": max_event_names,
        "max_field_name_length": max_field_name_length,
        "max_event_name_length": max_event_name_length,
        "max_example_bytes": max_example_bytes,
        "max_nesting_depth": max_nesting_depth,
        "max_string_values_analysed_per_field": max_string_values_analysed_per_field,
        "max_array_elements_profiled": max_array_elements_profiled,
        "event_name_field": event_name_field or "auto",
    }
    return EventProfile(
        event_count=event_count,
        event_names=dict(event_names.most_common()),
        unnamed_event_count=unnamed_event_count,
        fields=fields,
        event_name_field=detected_event_name_field,
        event_name_detection_confidence=event_name_detection_confidence,
        common_envelope_fields=common_envelope_fields,
        event_specific_fields=event_specific_fields,
        profiler_version=PROFILER_VERSION,
        source_file_hash=source_hash.hexdigest(),
        duration_ms=(time.perf_counter() - started) * 1000,
        fields_discovered=len(fields),
        profile_configuration=configuration,
    )
