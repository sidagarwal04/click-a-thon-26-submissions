import re
from collections.abc import Mapping, Sequence

from app.schemas.agents import AnalysisPlan, AnalysisQuery, InstrumentationPlan
from app.schemas.features import EventProfile, ObservedFieldType

# Bounds keep every generated aggregate small enough to interpret, and keep the
# grouped queries from fanning out across a high-cardinality dimension.
MAX_SEGMENT_CARDINALITY = 50
MIN_SEGMENT_CARDINALITY = 2
MAX_SEGMENT_DIMENSIONS = 3
MAX_MEASURE_COLUMNS = 3
DEFAULT_RESULT_LIMIT = 200

_LATENCY_NAME = re.compile(
    r"(?:^|_)(?:latency|duration|elapsed)(?:_|$)"
    r"|_(?:ms|millis|milliseconds|seconds|secs)$",
    re.IGNORECASE,
)


class UnsafeAnalysisQueryError(RuntimeError):
    """Raised when agent-generated analytics SQL is not safely read-only."""


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|ATTACH|DETACH|SYSTEM|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
_TABLE_REFERENCE = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:`?[A-Za-z_][A-Za-z0-9_]*`?\.)?`?([A-Za-z_][A-Za-z0-9_]*)`?",
    re.IGNORECASE,
)
_CTE_ALIAS = re.compile(
    r"(?:\bWITH\b|,)\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s+AS\s*\(",
    re.IGNORECASE,
)
_SAFE_TABLE_FUNCTIONS = frozenset({"numbers", "numbers_mt", "range"})
_IDENTIFIER_TOKEN = re.compile(
    r"`([A-Za-z_][A-Za-z0-9_]*)`|\b([A-Za-z_][A-Za-z0-9_]*)\b"
)
_ALIAS = re.compile(r"\bAS\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.IGNORECASE)
_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")

# Words that appear in valid ClickHouse SQL but are never column names. Used
# only to avoid false "unknown column" rejections, never to permit unsafe SQL.
_SQL_WORDS = frozenset(
    """
    select from where group by order asc desc limit offset having and or not in is
    null as on join left right inner outer full cross using union all distinct
    case when then else end between like ilike interval with settings prewhere
    array tuple map nullable lowcardinality string int64 float64 uint8 datetime64
    """.split()
)


def _strip_literals(sql: str) -> str:
    """Blank out string literals so their contents are never read as identifiers."""

    return _STRING_LITERAL.sub("''", sql)


def validate_analysis_sql(
    sql: str,
    *,
    allowed_tables: Sequence[str],
    table_columns: Mapping[str, Sequence[str]] | None = None,
) -> str:
    """Return bounded read-only SQL, or explain precisely why it was rejected.

    Rejection messages name the offending table or column so a planning agent
    can be handed the failure and retry against it.
    """

    normalized = sql.strip()
    if not normalized.upper().startswith(("SELECT ", "WITH ")):
        raise UnsafeAnalysisQueryError("Analytics SQL must start with SELECT or WITH")
    if ";" in normalized or "--" in normalized or "/*" in normalized:
        raise UnsafeAnalysisQueryError(
            "SQL comments and multiple statements are forbidden"
        )
    if _FORBIDDEN.search(normalized):
        raise UnsafeAnalysisQueryError("Analytics SQL contains a forbidden statement")

    inspectable = _strip_literals(normalized)
    references = set(_TABLE_REFERENCE.findall(inspectable))
    cte_aliases = set(_CTE_ALIAS.findall(inspectable))
    table_functions = {
        reference
        for reference in references
        if reference.casefold() in _SAFE_TABLE_FUNCTIONS
        and re.search(
            rf"\b(?:FROM|JOIN)\s+`?{re.escape(reference)}`?\s*\(",
            inspectable,
            re.IGNORECASE,
        )
    }
    physical_references = references - cte_aliases - table_functions
    unknown_tables = physical_references - set(allowed_tables)
    if not references or unknown_tables:
        raise UnsafeAnalysisQueryError(
            f"Analytics SQL references invalid tables: {sorted(unknown_tables)}"
        )
    if table_columns is not None:
        _validate_columns(inspectable, references, table_columns)

    if re.search(r"\bLIMIT\s+\d+\b", normalized, re.IGNORECASE) is None:
        normalized += f" LIMIT {DEFAULT_RESULT_LIMIT}"
    return normalized


def _validate_columns(
    inspectable: str,
    references: set[str],
    table_columns: Mapping[str, Sequence[str]],
) -> None:
    """Reject identifiers that are not columns of any referenced table.

    Column sets are unioned across referenced tables rather than resolved per
    alias: the goal is to catch an agent inventing a column, not to reimplement
    SQL name resolution.
    """

    available: set[str] = set()
    for table in references:
        available.update(table_columns.get(table, ()))
    if not available:
        return

    # Aliases the query defines are legal to reference later in the same query.
    defined = {alias.casefold() for alias in _ALIAS.findall(inspectable)}
    known = {column.casefold() for column in available}
    folded_tables = {table.casefold() for table in references}
    unknown: list[str] = []
    for quoted, bare in _IDENTIFIER_TOKEN.findall(inspectable):
        token = quoted or bare
        folded = token.casefold()
        if folded in known or folded in defined or folded in folded_tables:
            continue
        if not quoted:
            if folded in _SQL_WORDS or token.isdigit():
                continue
            # A bare word followed by "(" is a function call, not a column.
            if re.search(rf"\b{re.escape(token)}\s*\(", inspectable):
                continue
        unknown.append(token)
    if unknown:
        raise UnsafeAnalysisQueryError(
            f"Analytics SQL references unknown columns: {sorted(set(unknown))}. "
            f"Available columns: {sorted(available)}"
        )


def _segment_dimensions(
    instrumentation: InstrumentationPlan,
    profile: EventProfile | None,
    column_names: set[str],
) -> list[str]:
    """Choose grouping columns from observed shape, never from known names.

    Preference order is the contract's own declared dimensions, then columns the
    profile shows to be genuinely low-cardinality. Identifier-like and
    near-unique columns are excluded so a grouped query stays bounded.
    """

    candidates: list[str] = []
    for name in instrumentation.dimensions:
        if name in column_names and name not in candidates:
            candidates.append(name)

    if profile is not None:
        scored: list[tuple[int, str]] = []
        for name, field in profile.fields.items():
            if "." in name or name in candidates or name not in column_names:
                continue
            if name in (
                instrumentation.timestamp_field,
                instrumentation.primary_entity,
            ):
                continue
            if field.identifier_like or "NEAR_UNIQUE" in field.quality_flags:
                continue
            if field.observed_type not in (
                ObservedFieldType.STRING,
                ObservedFieldType.BOOLEAN,
                ObservedFieldType.INTEGER,
            ):
                continue
            cardinality = field.approx_cardinality
            if not MIN_SEGMENT_CARDINALITY <= cardinality <= MAX_SEGMENT_CARDINALITY:
                continue
            scored.append((cardinality, name))
        candidates.extend(name for _, name in sorted(scored))

    return candidates[:MAX_SEGMENT_DIMENSIONS]


def _measure_columns(
    instrumentation: InstrumentationPlan,
    profile: EventProfile | None,
    predicate: str,
) -> list[str]:
    """Find columns worth measuring, by observed type rather than by name."""

    if profile is None:
        return []
    column_names = {column.name for column in instrumentation.columns}
    reserved = {instrumentation.timestamp_field, instrumentation.primary_entity}
    numeric_types = (ObservedFieldType.INTEGER, ObservedFieldType.FLOAT)
    selected: list[str] = []
    for name, field in profile.fields.items():
        if "." in name or name not in column_names or name in reserved:
            continue
        if field.identifier_like:
            continue
        if predicate == "boolean":
            if field.observed_type is not ObservedFieldType.BOOLEAN:
                continue
        elif predicate == "numeric":
            if field.observed_type not in numeric_types or _LATENCY_NAME.search(name):
                continue
        elif predicate == "latency":
            if field.observed_type not in numeric_types:
                continue
            if not _LATENCY_NAME.search(name):
                continue
        selected.append(name)
    return sorted(selected)[:MAX_MEASURE_COLUMNS]


def build_deterministic_analysis_plan(
    instrumentation: InstrumentationPlan,
    *,
    profile: EventProfile | None = None,
) -> AnalysisPlan:
    """Build executable SQL using only the validated feature contract.

    The primitives depend on funnel positions, observed types, and observed
    cardinality, never on domain-specific event, field, or table names, so an
    unseen specification produces the same breadth of analysis as a known one.
    """

    table = _identifier(instrumentation.table_name)
    column_names = {column.name for column in instrumentation.columns}
    entity = _identifier(instrumentation.primary_entity)
    timestamp = _identifier(instrumentation.timestamp_field)
    event_name = "event" if "event" in column_names else "event_name"
    if event_name not in column_names:
        raise UnsafeAnalysisQueryError(
            "The feature table has no event-name column to build a funnel from"
        )
    event_field = _identifier(event_name)

    dimensions = _segment_dimensions(instrumentation, profile, column_names)
    dimension_sql = ", ".join(_identifier(name) for name in dimensions)
    group_sql = f" GROUP BY {dimension_sql}" if dimension_sql else ""
    select_dimensions = f"{dimension_sql}, " if dimension_sql else ""

    steps = instrumentation.funnel_steps
    if len(steps) < 2:
        raise UnsafeAnalysisQueryError("At least two funnel steps are required")
    first = _literal(steps[0])
    second = _literal(steps[1])
    last = _literal(steps[-1])
    step_literals = ", ".join(_literal(step) for step in steps)
    # Rank by declared funnel position so results read in journey order rather
    # than by row volume.
    step_rank = " ".join(
        f"WHEN {_literal(step)} THEN {index}" for index, step in enumerate(steps)
    )

    analyses = [
        AnalysisQuery(
            query_id="funnel",
            analysis_type="funnel",
            purpose=(
                "Measure unique-entity progression through every feature step, "
                "in journey order."
            ),
            sql=(
                f"SELECT {event_field}, CASE {event_field} {step_rank} ELSE 99 END "
                f"AS step_position, uniqExact({entity}) AS entities, count() AS "
                f"event_rows FROM {table} WHERE {event_field} IN ({step_literals}) "
                f"GROUP BY {event_field} ORDER BY step_position"
            ),
        ),
        AnalysisQuery(
            query_id="adoption_by_segment",
            analysis_type="adoption",
            purpose=(
                "Measure second-step adoption against the first step using the "
                "same entity denominator, by segment."
            ),
            sql=(
                f"SELECT {select_dimensions}uniqExactIf({entity}, {event_field} = "
                f"{second}) AS selected_entities, uniqExactIf({entity}, "
                f"{event_field} = {first}) AS shown_entities, selected_entities / "
                f"nullIf(shown_entities, 0) AS adoption_rate FROM {table}{group_sql}"
            ),
        ),
        AnalysisQuery(
            query_id="completion_trend",
            analysis_type="trend",
            purpose=(
                "Track daily completion rate and volume to expose drift, "
                "seasonality, or anomalies over time."
            ),
            sql=(
                f"SELECT toStartOfDay({timestamp}) AS day, uniqExact({entity}) AS "
                f"entities, uniqExactIf({entity}, {event_field} = {last}) AS "
                f"completed_entities, completed_entities / nullIf(entities, 0) AS "
                f"completion_rate FROM {table} GROUP BY day ORDER BY day"
            ),
        ),
    ]

    if dimensions:
        analyses.append(
            AnalysisQuery(
                query_id="completion_by_segment",
                analysis_type="segment_comparison",
                purpose=(
                    "Compare end-to-end completion rate and sample size across "
                    "segments to locate where the feature underperforms."
                ),
                sql=(
                    f"SELECT {select_dimensions}uniqExact({entity}) AS entities, "
                    f"uniqExactIf({entity}, {event_field} = {last}) AS "
                    f"completed_entities, completed_entities / nullIf(uniqExactIf("
                    f"{entity}, {event_field} = {first}), 0) AS completion_rate "
                    f"FROM {table}{group_sql}"
                ),
            )
        )

    boolean_columns = _measure_columns(instrumentation, profile, "boolean")
    if boolean_columns:
        measures = ", ".join(
            f"avg(toFloat64({_identifier(name)})) AS {name}_rate"
            for name in boolean_columns
        )
        analyses.append(
            AnalysisQuery(
                query_id="outcome_rates_by_segment",
                analysis_type="segment_comparison",
                purpose=(
                    "Compare observed success/failure rates and sample size by segment."
                ),
                sql=(
                    f"SELECT {select_dimensions}count() AS sample_size, {measures} "
                    f"FROM {table}{group_sql}"
                ),
            )
        )

    latency_columns = _measure_columns(instrumentation, profile, "latency")
    numeric_columns = _measure_columns(instrumentation, profile, "numeric")
    if latency_columns:
        column = _identifier(latency_columns[0])
        analyses.append(
            AnalysisQuery(
                query_id="latency_by_segment",
                analysis_type="latency",
                purpose="Measure the reported latency distribution by segment.",
                sql=(
                    f"SELECT {select_dimensions}count() AS sample_size, "
                    f"quantile(0.5)({column}) AS p50, quantile(0.9)({column}) AS p90, "
                    f"quantile(0.99)({column}) AS p99, avg({column}) AS mean "
                    f"FROM {table} WHERE {column} IS NOT NULL{group_sql}"
                ),
            )
        )
    elif numeric_columns:
        column = _identifier(numeric_columns[0])
        analyses.append(
            AnalysisQuery(
                query_id="numeric_distribution_by_segment",
                analysis_type="segment_comparison",
                purpose=(
                    "Measure the distribution of the primary numeric measure by "
                    "segment."
                ),
                sql=(
                    f"SELECT {select_dimensions}count() AS sample_size, "
                    f"quantile(0.5)({column}) AS p50, quantile(0.9)({column}) AS p90, "
                    f"avg({column}) AS mean FROM {table} "
                    f"WHERE {column} IS NOT NULL{group_sql}"
                ),
            )
        )
    return AnalysisPlan(analyses=analyses)


def _identifier(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) is None:
        raise UnsafeAnalysisQueryError(f"Unsafe analytics identifier: {value!r}")
    return f"`{value}`"


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


__all__ = [
    "UnsafeAnalysisQueryError",
    "build_deterministic_analysis_plan",
    "validate_analysis_sql",
]
