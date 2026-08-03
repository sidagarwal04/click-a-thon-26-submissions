# Event profiler

The event profiler reads an NDJSON event file as a bounded stream and produces a deterministic summary for schema planning. It reads each line once and updates all statistics for a discovered field in one update path.

## Field discovery

JSON objects are flattened with dotted paths while retaining the parent object. For example:

```text
payment                    object
payment.amount             float
payment.currency           string
payment.latency_ms         integer
```

Flattening stops after `max_nesting_depth`, which defaults to `5`. Arrays remain a single field: indexed paths such as `travellers.0.name` are never created.

The number of discovered fields, field-name length, line size, distinct event names, and nesting depth are bounded by the profile configuration.

## Presence and nullability

Every field reports global statistics:

- `presence_count` and `presence_rate`
- `missing_count`
- `null_count` and `non_null_count`
- `null_rate_when_present`

The same statistics are calculated within each detected event type under `by_event`. This allows a field that is required for one event type to remain distinguishable from a globally optional field.

## Event-name detection

Callers can pass `event_name_field` explicitly. Otherwise, the profiler chooses one field for the file, preferring `event_name` and `event`. Generic `type` and `name` fields are accepted more cautiously and receive lower confidence.

The result includes `event_name_field` and `event_name_detection_confidence`. Once a field is selected, the profiler does not switch between event-name keys on individual rows.

## Value statistics

Cardinality is estimated only for JSON scalar values: strings, integers, floats, booleans, and null. Complete objects and arrays are not serialized or hashed for cardinality.

Numeric fields collect:

- minimum and maximum
- negative and zero counts
- maximum decimal places

String fields collect minimum and maximum lengths. At most `MAX_STRING_VALUES_ANALYSED_PER_FIELD` values per field are parsed for:

- ISO timestamps
- UUIDs
- numeric strings
- boolean strings
- identifier-like strings

Basic presence, null, length, example, and cardinality counting continues after the parsing limit is reached.

Arrays collect minimum and maximum lengths, empty-array count, observed element types, and field names found in object elements. At most `MAX_ARRAY_ELEMENTS_PROFILED` elements from an array value are inspected.

## Identifiers and examples

Names such as `event_id`, `user_id`, `application_id`, `session_id`, `share_id`, `group_id`, and other `*_id` fields are treated as identifiers. Value shape and near-unique cardinality can also identify unknown identifier fields.

Identifier examples are redacted. The profile returns `examples_redacted: true` and a structural description such as `app_<alphanumeric>` instead of source values. Examples remain available for useful dimensions such as `ios`, `android`, `IN`, `USD`, and `whatsapp`.

## Derived schema hints

The profiler derives `common_envelope_fields` for fields present on every event and `event_specific_fields` for fields strongly associated with an individual event type.

It also emits deterministic quality flags when applicable:

- `MIXED_TYPES`
- `HIGH_NULL_RATE`
- `HIGH_MISSING_RATE`
- `LIKELY_TIMESTAMP`
- `LIKELY_IDENTIFIER`
- `LOW_CARDINALITY`
- `NEAR_UNIQUE`
- `NUMERIC_STRING`
- `INCONSISTENT_CASE`
- `CONSTANT_FIELD`

## Profile metadata

Every result contains:

- `profiler_version`
- `source_file_hash`, calculated with SHA-256
- `duration_ms`
- `fields_discovered`
- `profile_configuration`

A reusable profile cache key can be constructed from the source SHA-256, profiler version, and normalized configuration.
