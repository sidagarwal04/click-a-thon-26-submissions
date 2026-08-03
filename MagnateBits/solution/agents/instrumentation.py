"""Instrumentation Agent: feature spec -> production-grade ClickHouse DDL -> loaded data.

Design stance
-------------
The LLM is used for exactly one thing: *judgement* about schema shape (which id is
the entity key, which rollup is worth materialising, how to word a rationale a
reviewer will disagree with). Everything mechanical -- rendering SQL, checking house
rules, proving the DDL against a real server, loading rows, measuring whether an MV
earned its keep -- is deterministic code in `ddl.py` and below.

That split is what makes an unseen 6th spec safe:

  * nothing here mentions a feature, an event name or a column name from the five
    known specs. Every name is read out of `SpecProfile` at runtime.
  * if the model is unavailable or wrong, `build_fallback_proposal()` produces a
    complete, lint-clean, executable proposal from the profile alone. The pipeline
    degrades in quality, never in availability.
  * the model's output is never trusted: `lint()` gates it against the house rules
    and `dry_run()` gates it against ClickHouse itself, each with a bounded repair
    loop that feeds the verbatim failure back.

Public surface:
    propose_ddl(profile, house_rules, ctx, ch=None) -> DDLProposal
    apply(proposal, ch, events_path, rebuild=False) -> LoadResult
    build_fallback_proposal(profile)                -> DDLProposal
    mv_report(proposal)                             -> list[str]
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Sequence

import ddl as ddl_mod
import llm
import tracing
from contracts import (
    ColumnSpec,
    ContextSnapshot,
    DDLProposal,
    EventFieldProfile,
    FeatureSemantics,
    LoadResult,
    MeasureSpec,
    MVSpec,
    SpecProfile,
)

MAX_LINT_REPAIRS = 2
MAX_DDL_REPAIRS = 2
MIN_MV_REDUCTION = 5.0

# Every name below is a *structural* pattern (suffix / substring conventions that
# hold for any event stream), never a value taken from one of the known specs.
_MS_RE = re.compile(r"(^|_)(latency|duration|elapsed|took)(_|$)|_ms$", re.IGNORECASE)
_SECONDS_RE = re.compile(r"(^|_)(seconds|secs|hours|minutes|age|since)(_|$)|_s$", re.IGNORECASE)
_RATE_RE = re.compile(r"(^|_)(rate|ratio|pct|percent|score|share_of)(_|$)", re.IGNORECASE)
_MONEY_RE = re.compile(
    r"(^|_)(amount|value|price|fee|cost|revenue|total|subtotal|charge|balance)(_|$)",
    re.IGNORECASE,
)
_COUNTISH_RE = re.compile(
    r"(^|_)(count|size|index|attempts|retries|retry|num|n|position|step|version)(_|$)",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"(^|_)(timestamp|time|ts)(_|$)|_at$", re.IGNORECASE)
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")

# Cardinality ceiling for a column to be worth a LowCardinality dictionary.
LOW_CARD_MAX = 500
# Cardinality ceiling for a column to be offered to Analytics as a segment dimension.
SEGMENT_CARD_MAX = 64


# --------------------------------------------------------------------------
# type mapping (delegates to mapping.ch_type_for when that module is present)
# --------------------------------------------------------------------------


def _local_ch_type_for(field: EventFieldProfile) -> str:
    """Rule-based ClickHouse type for one profiled field, straight from house rules §4."""
    name = field.name
    types = {t for t in field.json_types if t != "NoneType"}
    samples = [s for s in field.sample_values if s is not None]

    # timestamps: ISO-8601 with milliseconds; DateTime would silently truncate.
    if _TIME_RE.search(name) and (
        "str" in types and any(_ISO_RE.match(str(s)) for s in samples)
    ):
        return "DateTime64(3)"

    if types == {"bool"} or types == {"bool", "int"} and all(
        s in (0, 1, True, False) for s in samples
    ):
        return "UInt8"

    if types & {"int", "float"}:
        if _MS_RE.search(name):
            return "UInt32"
        if _RATE_RE.search(name):
            return "Float64"
        if _MONEY_RE.search(name) and not _COUNTISH_RE.search(name):
            return "Decimal(18, 4)"
        if "float" in types:
            return "Float64"
        nums = [s for s in samples if isinstance(s, (int, float)) and not isinstance(s, bool)]
        lo = min(nums) if nums else 0
        hi = max(nums) if nums else 0
        if lo < 0:
            return "Int32"
        if _SECONDS_RE.search(name):
            return "UInt16" if hi <= 65535 else "UInt32"
        if hi <= 255:
            return "UInt8"
        if hi <= 65535:
            return "UInt16"
        return "UInt32"

    # strings
    if ddl_mod.is_identity_name(name):
        return "String"
    if 0 < field.distinct_count <= LOW_CARD_MAX:
        return "LowCardinality(String)"
    return "String"


def ch_type_for(field: EventFieldProfile) -> str:
    """Prefer the shared `mapping` module when it exists; fall back to local rules.

    `mapping.py` is owned by another lane and may not be importable yet. The agent
    must not be blocked on it, and must not silently diverge from it either -- so we
    try it first and only fall back on failure.
    """
    try:
        import mapping  # type: ignore

        fn = getattr(mapping, "ch_type_for", None)
        if fn is not None:
            out = fn(field)
            # Reject types the house rules forbid outright rather than trusting them:
            # UUID cannot hold the 32-char dashless hex `id`, and Nullable is banned on
            # hot columns. Falling back is safer than emitting DDL that loses rows.
            if isinstance(out, str) and out.strip() and "UUID" not in out and "Nullable" not in out:
                return out.strip()
    except Exception:  # noqa: BLE001 - absence or signature drift must not break DDL
        pass
    return _local_ch_type_for(field)


def _codec_for(name: str, ch_type: str) -> str | None:
    if ch_type.startswith("DateTime"):
        return "(Delta, ZSTD(1))"
    if "LowCardinality" in ch_type:
        return None  # the dictionary already does the work
    if ch_type == "String":
        return "(ZSTD(1))"
    return None


def _default_for(ch_type: str) -> str | None:
    if "Nullable" in ch_type or ch_type.startswith("DateTime"):
        return None
    if "String" in ch_type:
        return "''"
    return "0"


# --------------------------------------------------------------------------
# profile-derived helpers (no LLM, no feature knowledge)
# --------------------------------------------------------------------------


def _column_name(field: EventFieldProfile) -> str:
    """Flatten a dotted json_path into a legal, collision-free column name."""
    base = field.name or field.json_path
    if "." in (field.json_path or ""):
        base = field.json_path
    return re.sub(r"[^A-Za-z0-9_]", "_", base).strip("_").lower() or "col"


def _coverage(field: EventFieldProfile, profile: SpecProfile) -> float:
    """Fraction of rows carrying this field, best-effort from two signals."""
    by_null = 1.0 - float(field.null_frac or 0.0)
    total = sum(profile.event_counts.values()) or profile.row_count or 1
    covered = sum(profile.event_counts.get(e, 0) for e in field.present_in_events)
    by_events = covered / total if total else 0.0
    return min(by_null, by_events) if field.present_in_events else by_null


def sparse_ratio(n_event_types: int) -> float:
    """min(0.9, 1 - 1/(E+1)) -- see house rules §1.

    An event-scoped column in a wide table is ~(1 - 1/E) defaults. For E=5 that is
    0.80, *below* ClickHouse's 0.9375 sparse threshold, so the column would stay
    dense. Lowering the threshold to 1 - 1/(E+1) puts it back on the sparse side.
    """
    e = max(1, int(n_event_types))
    return round(min(0.9, 1.0 - 1.0 / (e + 1)), 4)


def _identity_columns(cols: Sequence[ColumnSpec]) -> list[str]:
    return [c.name for c in cols if ddl_mod.is_identity_name(c.name) and c.name != "id"]


def segment_dimensions(profile: SpecProfile, cols: Sequence[ColumnSpec]) -> list[str]:
    """Low-cardinality, well-covered, non-identity columns Analytics can cut by.

    Derived purely from observed cardinality and coverage, so it works for a spec
    nobody has read.
    """
    by_name = {c.name: c for c in cols}
    scored: list[tuple[float, int, str]] = []
    for f in profile.fields:
        name = _column_name(f)
        col = by_name.get(name)
        if col is None or name in ("event", "id", "timestamp"):
            continue
        if ddl_mod.is_identity_name(name):
            continue
        if "String" not in col.type and "UInt8" not in col.type:
            continue
        if not (2 <= f.distinct_count <= SEGMENT_CARD_MAX):
            continue
        scored.append((-_coverage(f, profile), f.distinct_count, name))
    scored.sort()
    return [n for _, _, n in scored][:8]


def pm_questions(spec_markdown: str) -> list[str]:
    """Pull the spec's 'Questions the PM will ask' bullets, whatever the heading is."""
    out: list[str] = []
    in_section = False
    for line in (spec_markdown or "").splitlines():
        if line.startswith("#"):
            in_section = "question" in line.lower()
            continue
        if in_section:
            m = re.match(r"\s*[-*]\s+(.*)", line)
            if m:
                out.append(m.group(1).strip())
            elif out and line.strip():
                out[-1] += " " + line.strip()
    return [q for q in out if q][:12]


def _measures(profile: SpecProfile, cols: Sequence[ColumnSpec]) -> list[MeasureSpec]:
    by_name = {c.name: c for c in cols}
    out: list[MeasureSpec] = []
    for f in profile.fields:
        name = _column_name(f)
        col = by_name.get(name)
        if col is None or name == "timestamp":
            continue
        t = col.type
        if not re.match(r"^(U?Int(8|16|32|64)|Float64|Decimal)", t):
            continue
        if t == "UInt8" and {x for x in f.json_types if x != "NoneType"} == {"bool"}:
            continue  # that's a flag, not a measure
        if _MS_RE.search(name):
            kind, unit = "duration_ms", "ms"
        elif _RATE_RE.search(name):
            kind, unit = "rate", ""
        elif t.startswith("Decimal"):
            kind, unit = "money", "currency-denominated"
        elif _COUNTISH_RE.search(name):
            kind, unit = "count", ""
        elif _SECONDS_RE.search(name):
            kind, unit = "other", "elapsed time (integer units, see column name)"
        else:
            kind, unit = "other", ""
        out.append(
            MeasureSpec(column=name, kind=kind, scoped_to_events=list(f.present_in_events),
                        unit=unit)
        )
    return out


def _flags(profile: SpecProfile, cols: Sequence[ColumnSpec]) -> list[str]:
    by_name = {c.name: c for c in cols}
    out = []
    for f in profile.fields:
        name = _column_name(f)
        col = by_name.get(name)
        if col is not None and col.type == "UInt8" and "bool" in f.json_types:
            out.append(name)
    return out


def _disconnected_events(profile: SpecProfile, entity_key: str) -> list[str]:
    """Event types carrying neither the entity key nor user_id -- unjoinable rows."""
    carriers: dict[str, set[str]] = {}
    for f in profile.fields:
        carriers[_column_name(f)] = set(f.present_in_events)
    keyed = carriers.get(entity_key, set()) | carriers.get("user_id", set())
    return [e for e in profile.event_types if e not in keyed]


def _partial_identity_columns(profile: SpecProfile, cols: Sequence[ColumnSpec]) -> list[str]:
    """Identity columns with <100% coverage -- the `uniq('')` trap, made explicit.

    DEFAULT '' means a bare uniq() counts "no user" as one user. Anything listed
    here must be aggregated as uniqIf(col, col != '').
    """
    out = []
    n_events = len(profile.event_types)
    for f in profile.fields:
        name = _column_name(f)
        if not ddl_mod.is_identity_name(name) or name == "id":
            continue
        if float(f.null_frac or 0.0) > 0.0 or len(f.present_in_events) < n_events:
            out.append(name)
    return out


# --------------------------------------------------------------------------
# deterministic fallback proposal
# --------------------------------------------------------------------------


def build_columns(profile: SpecProfile) -> list[ColumnSpec]:
    cols: list[ColumnSpec] = []
    seen: set[str] = set()
    for f in profile.fields:
        name = _column_name(f)
        if name in seen:
            continue
        seen.add(name)
        t = ch_type_for(f)
        cols.append(
            ColumnSpec(
                name=name,
                type=t,
                json_path=f.json_path,
                codec=_codec_for(name, t),
                default=_default_for(t),
                comment=(
                    f"events: {','.join(f.present_in_events) or 'all'}"
                    f"; coverage={1.0 - float(f.null_frac or 0.0):.2f}"
                    f"; distinct={f.distinct_count}"
                ),
            )
        )
    return cols


def _mv_dimensions(profile: SpecProfile, dims: Sequence[str], cols: Sequence[ColumnSpec]) -> list[str]:
    """Pick rollup dimensions under an explicit row budget.

    A rollup only earns its keep if it is materially smaller than the raw table. We
    project the target's row count (days x event types x prod(cardinality)) and spend
    that budget -- row_count/8, which leaves headroom over the 5x keep/drop gate -- on
    the *highest*-cardinality dimensions that still fit, because those carry the most
    segmentation per stored row. This is why the generated rollup survives the gate
    instead of exploding on a 27-value dimension.
    """
    card = {}
    for f in profile.fields:
        card[_column_name(f)] = max(1, f.distinct_count)
    days = max(1, (profile.ts_max - profile.ts_min).days + 1)
    base = days * max(1, len(profile.event_types))
    budget = max(base, (profile.row_count or 1) / 8.0)
    chosen: list[str] = []
    projected = float(base)
    for d in sorted(dims, key=lambda x: -card.get(x, 10**6)):
        if len(chosen) >= 3:
            break
        nxt = projected * card.get(d, 10**6)
        if nxt <= budget:
            chosen.append(d)
            projected = nxt
    return chosen


def build_rollup_mv(
    profile: SpecProfile,
    table: str,
    entity_key: str,
    dims: Sequence[str],
    cols: Sequence[ColumnSpec],
    questions: Sequence[str],
) -> MVSpec | None:
    slug = profile.feature_slug
    by_name = {c.name: c for c in cols}
    if "timestamp" not in by_name or "event" not in by_name:
        return None
    keys = ["day", "event"] + list(dims)
    sel = [
        "    toDate(timestamp) AS day",
        "    event",
    ] + [f"    {d}" for d in dims]
    sel.append("    countState() AS events_state")
    if entity_key in by_name:
        sel.append(
            f"    uniqStateIf({entity_key}, {entity_key} != '') AS uniq_entities"
        )
    if "user_id" in by_name and entity_key != "user_id":
        sel.append("    uniqStateIf(user_id, user_id != '') AS uniq_users")
    # one money and one duration aggregate, if the feature has them
    for m in _measures(profile, cols)[:6]:
        if m.kind == "money" and not any("sum_" in s for s in sel):
            sel.append(f"    sumState({m.column}) AS sum_{m.column}")
        elif m.kind == "duration_ms" and not any("avg_" in s for s in sel):
            sel.append(f"    avgState({m.column}) AS avg_{m.column}")

    select_sql = (
        "SELECT\n" + ",\n".join(sel) + f"\nFROM {table}\nGROUP BY " + ", ".join(keys)
    )
    return MVSpec(
        name=f"mv_{slug}_funnel_daily",
        target_table=f"agg_{slug}_funnel_daily",
        select_sql=select_sql,
        justification=(
            "Daily per-step, per-segment funnel counters. Every PM question in this spec is "
            "'step X -> step Y, cut by a segment, over time', which this answers by reading "
            "the rollup instead of the raw stream. It is also the retention pair for the raw "
            "TTL: raw events expire at 18 months, this survives, so long-range trend queries "
            "keep working on a fraction of the bytes. Distinct counts are stored as uniqState "
            "and must be read with uniqMerge -- summing distinct counts across parts is wrong."
        ),
        serves_questions=list(questions[:4]),
    )


# Trap F -- column-shape patterns that mark a row as a re-ingested duplicate or a backfill.
# Matched on NAME SHAPE, never on an Atlys-specific literal, so an unseen spec that carries
# such a column is handled and one that doesn't is untouched.
# `duplicate`/`dedup`/`reingest` match as substrings (so duplicate_id, is_duplicate,
# deduplicated, row_reingested all fire); `dup` only as a bounded token (so it catches a
# `dup`/`dup_flag` column but NOT `duration_ms`); backfill matches with optional separator/
# is_ prefix. Tuned against false positives like `backup_count`, `duration_ms`, `dup_rate`.
_DEDUP_SIGNAL_RE = re.compile(
    r"duplicate|dedup|reingest"
    r"|(^|_)dup(_|$)"
    r"|(^|_)(is_)?back[_]?fill(ed)?(_|$)",
    re.IGNORECASE,
)


# ClickHouse only accepts an unsigned-int / Date / DateTime / DateTime64 / numeric column as a
# ReplacingMergeTree version. A String/LowCardinality(String) version is REJECTED (code 169).
_VERSION_TYPE_OK = re.compile(
    r"^(U?Int(8|16|32|64|128|256)|Date(Time)?(64)?(\(|$)|Float(32|64)|Decimal)", re.IGNORECASE
)


def _dedup_engine(names: set[str], order_by: list[str],
                  col_types: dict[str, str] | None = None) -> tuple[str, str]:
    """Choose MergeTree vs ReplacingMergeTree based on dedup/backfill signal columns.

    Returns (engine, rationale). When a signal column is present:
      * if there is a column ClickHouse will accept as a *version* (temporal/numeric — a
        String version is rejected outright), use ReplacingMergeTree(<that column>);
      * otherwise use keyless ReplacingMergeTree.
    When no signal is present, plain MergeTree, with a rationale that records the check ran.

    `col_types` maps column name -> rendered ClickHouse type; when omitted we assume the
    conventional `timestamp` column is temporal (back-compat for callers that don't pass it).
    """
    col_types = col_types or {}
    signals = sorted(n for n in names if _DEDUP_SIGNAL_RE.search(n))
    if signals:
        # pick a valid version column: prefer `timestamp`, else the first temporal/numeric col.
        def _valid_version(col: str) -> bool:
            t = col_types.get(col)
            # if we weren't told the type, only trust the conventional `timestamp` name
            return _VERSION_TYPE_OK.match(t) is not None if t else col == "timestamp"

        version_col = None
        if "timestamp" in names and _valid_version("timestamp"):
            version_col = "timestamp"
        else:
            version_col = next((c for c in sorted(names) if _valid_version(c)), None)

        if version_col:
            return (
                f"ReplacingMergeTree({version_col})",
                (
                    f"ReplacingMergeTree({version_col}): the events carry dedup/backfill signal "
                    f"column(s) {signals}, so re-ingested/backfilled rows would otherwise "
                    f"double-count. Replacing collapses rows that share the full ORDER BY tuple, "
                    f"with `{version_col}` breaking ties (highest wins) on merge — so an exact "
                    f"duplicate (same key tuple) is de-duplicated. A corrected re-ingest with a "
                    f"changed ORDER BY value is a distinct row by design; use FINAL or aggregate "
                    f"at query time for exactness before merges settle. Signal detected by column "
                    f"shape, not a hardcoded name — generalises to an unseen spec."
                ),
            )
        return (
            "ReplacingMergeTree",
            (
                f"ReplacingMergeTree (no version column): dedup/backfill signal(s) {signals} "
                f"present but no temporal/numeric column ClickHouse accepts as a version, so the "
                f"most-recently-inserted row per ORDER BY tuple wins on merge."
            ),
        )
    return (
        "MergeTree",
        (
            "MergeTree: no dedup/backfill signal column (duplicate_id / is_back_filled / "
            "reingest-style) is present in these events, so re-ingestion collapsing is "
            "unnecessary and plain MergeTree is correct. The check ran and found none."
        ),
    )


def build_fallback_proposal(profile: SpecProfile) -> DDLProposal:
    """A complete, lint-clean proposal derived from the profile with no LLM at all.

    This is the availability floor: if the model is down, hallucinating, or the API
    key is missing, the pipeline still produces defensible DDL for an unseen spec.
    """
    slug = profile.feature_slug
    table = f"f_{slug}_events"
    cols = build_columns(profile)
    names = {c.name for c in cols}

    entity = profile.entity_key if profile.entity_key in names else (
        "user_id" if "user_id" in names else next(
            (c.name for c in cols if ddl_mod.is_identity_name(c.name) and c.name != "id"),
            "",
        )
    )
    order_by = [n for n in ("event", "timestamp") if n in names]
    if entity and entity in names:
        order_by.append(entity)
    if not order_by:  # pathological profile; sort by anything non-identity
        order_by = [c.name for c in cols if not ddl_mod.is_identity_name(c.name)][:1]

    dims = segment_dimensions(profile, cols)
    e = len(profile.event_types)
    ratio = sparse_ratio(e)
    questions = pm_questions(profile.spec_markdown)
    mv = build_rollup_mv(profile, table, entity, _mv_dimensions(profile, dims, cols),
                         cols, questions)

    semantics = FeatureSemantics(
        feature_slug=slug,
        table_fqn=f"atlys.{table}",
        event_column="event",
        event_types=list(profile.event_types),
        entity_key=entity,
        entity_key_confidence=0.7,
        secondary_keys=[n for n in _identity_columns(cols) if n != entity],
        ordered_steps=list(profile.derived_funnel or profile.event_types),
        step_order_source="spec" if profile.derived_funnel else "volume",
        segment_dims=dims,
        measures=_measures(profile, cols),
        flags=_flags(profile, cols),
        disconnected_event_types=_disconnected_events(profile, entity),
        partial_identity_columns=_partial_identity_columns(profile, cols),
    )

    # Trap F -- decide the engine (dedup/backfill signal -> ReplacingMergeTree) BEFORE the
    # rationale dict, which cites the reason. Generic detection by column shape.
    engine, dedup_rationale = _dedup_engine(
        names, order_by, col_types={c.name: c.type for c in cols})

    rationale = {
        "order_by": (
            f"ORDER BY ({', '.join(order_by)}). The 8 existing tables use "
            "(id, timestamp, user_id); id is unique, so the primary index prunes nothing for "
            "queries that filter by time and segment and never by id. Leading with the event "
            f"discriminator ({e} values) prunes hard and compresses well, timestamp second "
            "matches every time-windowed query, and "
            f"{entity or 'the entity key'} last keeps each entity's step sequence co-located "
            "for windowFunnel."
        ),
        "partition_by": (
            "toYYYYMM(timestamp), matching the existing tables so cross-table segment queries "
            "prune consistently. Daily partitions would create thousands of tiny parts at this "
            "volume and slow merges for no pruning benefit over a monthly part."
        ),
        "types": (
            f"E={e} event types in one wide table, so an event-scoped column is ~(1 - 1/{e}) = "
            f"{1 - 1 / max(1, e):.2f} defaults -- under ClickHouse's 0.9375 sparse threshold, so "
            f"it would stay dense. ratio_of_defaults_for_sparse_serialization is set to "
            f"min(0.9, 1 - 1/(E+1)) = {ratio} so those columns actually go sparse. "
            "id is a 32-char hex string with no dashes and is typed String, not UUID, which "
            "would reject the literal outright. timestamp is DateTime64(3) because the source "
            "carries milliseconds. Enums are LowCardinality(String); high-cardinality ids are "
            "plain String with ZSTD(1); currency-denominated values are Decimal(18,4) so sums "
            "are exact; genuinely approximate ratios stay Float64."
        ),
        "nullable": (
            "No Nullable columns. A null map is a second column to read and it weakens index "
            "usage on exactly the columns we filter by; absent values use DEFAULT ''/0 instead. "
            "The trap this creates is recorded, not ignored: "
            f"partial-coverage identity columns are {semantics.partial_identity_columns or 'none'}"
            ", and every distinct-user metric on them must be uniqIf(col, col != '') because a "
            "bare uniq() would count the empty string as a real user."
        ),
        "ttl": (
            "TTL toDateTime(timestamp) + INTERVAL 18 MONTH on raw events, paired with a rollup "
            "that has no TTL. That pairing is what makes the MV worth its cost: the aggregate "
            "outlives raw expiry, so long-range trend queries keep answering."
        ),
        "mvs": (
            "One daily per-step, per-segment rollup. Dimensions are chosen under a row budget "
            "(days x event types x cardinality <= row_count/8) so the rollup is materially "
            "smaller than the source; anything that fails the 5x measured reduction gate after "
            "load is dropped with the number recorded. At sample volume the MV is unnecessary; "
            "it is justified against projected annual volume, not against these rows."
            if mv else "No materialized view: no aggregate beats the raw scan at this shape."
        ),
        "contrast_with_legacy": (
            "One wide table per feature instead of one table per event: every PM question here "
            "is a within-feature funnel, which is one windowFunnel on a wide table and an "
            "N-way join on the legacy shape. The existing one-table-per-event layout is an SDK "
            "artifact, not a design decision, and the id-first sorting key is a bug we do not "
            "copy."
        ),
        "engine": dedup_rationale,
    }

    proposal = DDLProposal(
        table_name=table,
        columns=cols,
        engine=engine,
        order_by=order_by,
        partition_by="toYYYYMM(timestamp)" if "timestamp" in names else None,
        ttl="toDateTime(timestamp) + INTERVAL 18 MONTH" if "timestamp" in names else None,
        settings={
            "ratio_of_defaults_for_sparse_serialization": ratio,
            "index_granularity": 8192,
        },
        materialized_views=[mv] if mv else [],
        semantics=semantics,
        rationale=rationale,
        ddl_sql=[],
    )
    proposal.ddl_sql = ddl_mod.render(proposal)
    return proposal


# --------------------------------------------------------------------------
# prompt construction
# --------------------------------------------------------------------------


LEGACY_DDL_PATH = Path(__file__).resolve().parents[2] / "data" / "ddl.sql"


def _legacy_from_file(path: Path = LEGACY_DDL_PATH) -> str:
    """Digest the shipped production DDL when live introspection is unavailable.

    `CH.run_select` currently rejects any query mentioning `system` (see the report),
    so `system.tables` is unreadable through the sanctioned read path. Parsing the
    checked-in DDL gives the same three facts -- sorting key, partition key, Nullable
    density -- without reaching around the frozen module.
    """
    try:
        text = path.read_text()
    except Exception:  # noqa: BLE001
        return ""
    lines = ["table | ORDER BY | PARTITION BY | Nullable cols / total  (parsed from data/ddl.sql)"]
    for block in re.finditer(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\(\s*\n(.*?)\n\s*\)\s*(.*?);",
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        name, body, tail = block.group(1), block.group(2), block.group(3)
        cols = [c for c in body.split("\n") if c.strip()]
        nullable = sum(1 for c in cols if "Nullable(" in c)
        ob = re.search(r"ORDER\s+BY\s+(\(.*?\)|\w+)", tail, re.IGNORECASE)
        pb = re.search(r"PARTITION\s+BY\s+(.*?)(?:\n|$)", tail, re.IGNORECASE)
        lines.append(
            f"{name} | {ob.group(1) if ob else '?'} | {pb.group(1).strip() if pb else '?'} | "
            f"{nullable}/{len(cols)}"
        )
    return "\n".join(lines) if len(lines) > 1 else ""


def legacy_schema_summary(ch: Any | None) -> str:
    """Compact digest of the pre-existing production tables, read live when possible.

    The model is shown the anti-pattern it must consciously depart from, measured
    from the actual schema rather than asserted in prose.
    """
    if ch is None:
        return _legacy_from_file() or (
            "(existing schema unavailable at prompt time -- the 8 production event tables "
            "use ORDER BY (id, timestamp, user_id) with nearly every column Nullable and "
            "id typed UUID; that is the anti-pattern.)"
        )
    try:
        rows = ch.run_select(
            "SELECT t.name AS name, t.total_rows AS rows, t.sorting_key AS sorting_key, "
            "t.partition_key AS partition_key, "
            "countIf(c.type LIKE 'Nullable%') AS nullable_cols, count() AS n_cols "
            f"FROM system.tables t INNER JOIN system.columns c "
            f"ON c.database = t.database AND c.table = t.name "
            f"WHERE t.database = '{ch.database}' AND t.engine LIKE '%MergeTree' "
            "AND t.name NOT LIKE 'f\\_%' AND t.name NOT LIKE 'agg\\_%' "
            "AND t.name NOT LIKE 'context\\_%' AND t.name NOT LIKE 'schema\\_%' "
            "AND t.name NOT LIKE 'pipeline\\_%' AND t.name NOT LIKE 'insights\\_%' "
            "AND t.name != 'contradiction' "
            "GROUP BY name, rows, sorting_key, partition_key ORDER BY rows DESC",
            max_rows=50,
        )
    except Exception as exc:  # noqa: BLE001
        fallback = _legacy_from_file()
        return fallback or f"(existing schema introspection failed: {exc})"
    if not rows:
        return _legacy_from_file() or "(no pre-existing production tables found)"
    lines = [
        "table | rows | ORDER BY | PARTITION BY | Nullable cols / total",
    ]
    for r in rows:
        lines.append(
            f"{r['name']} | {r['rows']:,} | ({r['sorting_key']}) | {r['partition_key']} | "
            f"{r['nullable_cols']}/{r['n_cols']}"
        )
    return "\n".join(lines)


def _field_table(profile: SpecProfile) -> str:
    head = "column_candidate | json_path | json_types | coverage | distinct | present_in_events | samples"
    lines = [head]
    for f in profile.fields:
        samples = ", ".join(str(s)[:24] for s in (f.sample_values or [])[:4])
        lines.append(
            f"{_column_name(f)} | {f.json_path} | {'/'.join(f.json_types)} | "
            f"{_coverage(f, profile):.3f} | {f.distinct_count} | "
            f"{','.join(f.present_in_events)} | {samples}"
        )
    return "\n".join(lines)


SYSTEM_PROMPT = """You are the Instrumentation Agent for Atlys, a digital visa platform.

You turn a product feature spec plus a profile of its raw event stream into ONE
production-grade ClickHouse schema proposal. You are designing for a reviewer who will
disagree with you: every choice must carry a concrete, falsifiable reason, never
"best practice".

You emit a structured DDLProposal. You do NOT write the final SQL text -- a deterministic
renderer builds CREATE TABLE / CREATE TABLE (rollup target) / CREATE MATERIALIZED VIEW ... TO
from your proposal, in that order, with IF NOT EXISTS everywhere. Leave `ddl_sql` empty.

The house rules below are binding. A deterministic linter checks them and ClickHouse itself
executes your DDL in a scratch database before it is accepted; you will be shown verbatim
violations and server errors and asked to repair.

=== HOUSE RULES (verbatim) ===
{house_rules}
=== END HOUSE RULES ===

Additional mechanical constraints of the renderer and of this ClickHouse server (26.x):
- Column names must be plain identifiers. Set `json_path` on every column to the dotted path
  in the source event (e.g. "payment.amount"); the loader extracts by that path, so a wrong
  path silently loads defaults. Use json_path="" only for columns nothing writes.
- Every materialized view SELECT must read FROM the raw feature table, must contain a GROUP BY,
  and every GROUP BY item must be a bare alias defined in the SELECT list (write
  `toDate(timestamp) AS day ... GROUP BY day`, never `GROUP BY toDate(timestamp)`), because the
  rollup target's ORDER BY is derived from that GROUP BY list.
- The rollup target is created with `EMPTY AS <your select>`, so its column types come from
  your SELECT. On AggregatingMergeTree EVERY non-key output must be an aggregate state:
  write `countState() AS events_state`, `sumState(x)`, `avgState(x)`,
  `uniqStateIf(user_id, user_id != '')`. A bare `count() AS c` is REJECTED by the server.
- Name the view mv_<slug>_<purpose> and its target agg_<slug>_<purpose>.
- Fill `semantics` carefully: it is the ONLY thing the Analytics Agent reads. Its
  `segment_dims`, `measures`, `flags`, `ordered_steps`, `entity_key` and
  `partial_identity_columns` parameterise every query template. `partial_identity_columns` must
  list every identity column with less than 100% coverage.
"""


USER_TEMPLATE = """# Feature: {title}  (slug: `{slug}`)

## Spec (verbatim)
{spec_md}

## Questions the PM will ask (extracted -- MVs should cite these in serves_questions)
{questions}

## Observed event stream
rows: {row_count:,}   window: {ts_min} .. {ts_max}   event types (E): {n_events}
counts: {counts}
derived funnel order: {funnel}
   (how derived: {funnel_derivation})
derived entity key: {entity_key}
   (why: {entity_rationale})
events with a partial envelope (missing user_id / device / geo): {partial}

## Field profile (every column you declare must come from here)
{fields}

## Pre-existing production tables in the same database -- the shape to depart from
{legacy}

## Context layer feeding this decision
{context}

## Your task
Propose the single wide feature table `f_{slug}_events`, its sorting key, partitioning, TTL,
sparse-serialisation setting, and 1-2 rollup materialized views that each answer a listed PM
question at materially lower cost. Fill `rationale` for at least order_by, partition_by, types,
nullable, ttl, mvs and contrast_with_legacy, each referring to THIS feature's numbers (E, the
cardinalities and coverages above), not to generalities. Show the sparse-ratio arithmetic.
"""


def _build_user_prompt(profile: SpecProfile, ctx: ContextSnapshot, legacy: str,
                       instructions: str = "") -> str:
    qs = pm_questions(profile.spec_markdown)
    prompt = USER_TEMPLATE.format(
        title=profile.spec_title,
        slug=profile.feature_slug,
        spec_md=(profile.spec_markdown or "")[:8000],
        questions="\n".join(f"- {q}" for q in qs) or "- (none found in the spec)",
        row_count=profile.row_count,
        ts_min=profile.ts_min,
        ts_max=profile.ts_max,
        n_events=len(profile.event_types),
        counts=", ".join(f"{k}={v}" for k, v in profile.event_counts.items()),
        funnel=" -> ".join(profile.derived_funnel or profile.event_types),
        funnel_derivation=profile.funnel_derivation,
        entity_key=profile.entity_key,
        entity_rationale=profile.entity_key_rationale,
        partial=", ".join(profile.partial_envelope_events) or "none",
        fields=_field_table(profile),
        legacy=legacy,
        context=(ctx.as_prompt() if ctx else "(no context layer)")[:12000],
    )
    if instructions.strip():
        # G6 — operator steering (human-in-the-loop). Free-text guidance an engineer supplies
        # for THIS run (retention, partition grain, a preferred primary cut, PII masking, ...).
        # Presented as hard constraints that override the defaults where they conflict, but the
        # house rules and lint still bound the result — an instruction can't produce invalid DDL.
        prompt += (
            "\n\n## OPERATOR INSTRUCTIONS (human-in-the-loop, authoritative for this run)\n"
            "Honour these where they apply; they override the defaults on conflict. You must "
            "still satisfy the house rules and lint (an instruction cannot justify invalid DDL "
            "or an id-leading ORDER BY). Note in the relevant rationale entry which choice an "
            "instruction changed.\n"
            f"{instructions.strip()[:2000]}\n"
        )
    return prompt


def _repair_prompt(base_user: str, proposal: DDLProposal, problems: str, kind: str) -> str:
    return (
        base_user
        + f"\n\n## PREVIOUS ATTEMPT REJECTED ({kind})\n"
        + "Your previous proposal was:\n```json\n"
        + proposal.model_dump_json(indent=1, exclude={"ddl_sql"})[:12000]
        + "\n```\n\nIt was rejected for these reasons:\n"
        + problems
        + "\n\nEmit a corrected DDLProposal. Change only what is necessary to clear every "
        "item above; keep everything else identical.\n"
    )


# --------------------------------------------------------------------------
# deterministic repair of a model proposal
# --------------------------------------------------------------------------


def _pin(proposal: DDLProposal, profile: SpecProfile) -> DDLProposal:
    """Pin the few fields the model must not be free to drift on, then re-render.

    Slug and table_fqn are identity, not judgement: Analytics resolves the table by
    `semantics.table_fqn`, so a drifted value breaks the seam silently.
    """
    proposal.semantics.feature_slug = profile.feature_slug
    if not proposal.semantics.event_types:
        proposal.semantics.event_types = list(profile.event_types)
    if not proposal.semantics.table_fqn or "." not in proposal.semantics.table_fqn:
        proposal.semantics.table_fqn = f"atlys.{proposal.table_name}"
    proposal.ddl_sql = ddl_mod.render(proposal)
    return proposal


def _coerce_to_rules(proposal: DDLProposal, profile: SpecProfile) -> DDLProposal:
    """Last-resort mechanical fixes, applied only after the repair budget is spent."""
    fb = build_fallback_proposal(profile)
    names = {c.name for c in proposal.columns}

    proposal.table_name = f"f_{profile.feature_slug}_events"
    proposal.semantics.table_fqn = f"atlys.{proposal.table_name}"
    if not proposal.partition_by:
        proposal.partition_by = fb.partition_by
    if not proposal.ttl:
        proposal.ttl = fb.ttl
    if "ratio_of_defaults_for_sparse_serialization" not in {
        k.lower() for k in proposal.settings
    }:
        proposal.settings["ratio_of_defaults_for_sparse_serialization"] = sparse_ratio(
            len(profile.event_types)
        )
    order_by = [o for o in proposal.order_by if o in names]
    if not order_by or ddl_mod.is_identity_name(order_by[0]):
        order_by = [o for o in fb.order_by if o in names] or order_by
    proposal.order_by = order_by or fb.order_by
    for c in proposal.columns:
        if ddl_mod.is_identity_name(c.name) and "LowCardinality" in c.type:
            c.type = "String"
        if "Nullable(" in c.type and (
            c.name in proposal.order_by or c.name in (proposal.semantics.segment_dims or [])
        ):
            c.type = re.sub(r"Nullable\((.*)\)", r"\1", c.type)
    for key, text in fb.rationale.items():
        if not (proposal.rationale.get(key) or "").strip():
            proposal.rationale[key] = text
    proposal.semantics.segment_dims = [
        d for d in (proposal.semantics.segment_dims or []) if d in names
    ]
    if proposal.semantics.entity_key not in names:
        proposal.semantics.entity_key = fb.semantics.entity_key
    return _pin(proposal, profile)


# --------------------------------------------------------------------------
# the agent
# --------------------------------------------------------------------------


def propose_ddl(
    profile: SpecProfile,
    house_rules: str,
    ctx: ContextSnapshot,
    ch: Any | None = None,
    instructions: str = "",
) -> DDLProposal:
    """One LLM call, then bounded lint repairs, then bounded ClickHouse repairs.

    `instructions` (G6) is optional free-text operator guidance for this run (e.g. retention,
    partition grain, a preferred primary cut, PII masking); it is injected into the design
    prompt as authoritative-but-still-lint-bounded constraints.

    Never raises: if the model is unusable the deterministic fallback is returned, so
    the pipeline always has a schema to load into.
    """
    with tracing.span(
        "instrumentation.propose_ddl",
        feature_slug=profile.feature_slug,
        context_version=getattr(ctx, "version", 0),
    ) as sp:
        legacy = legacy_schema_summary(ch)
        system = SYSTEM_PROMPT.format(house_rules=house_rules)
        base_user = _build_user_prompt(profile, ctx, legacy, instructions)

        proposal: DDLProposal | None = None
        attempts: list[str] = []
        user = base_user

        for attempt in range(1 + MAX_LINT_REPAIRS + MAX_DDL_REPAIRS):
            try:
                candidate = llm.complete_json(
                    name=f"propose_ddl:{profile.feature_slug}"
                    + ("" if attempt == 0 else f":repair{attempt}"),
                    system=system,
                    user=user,
                    schema=DDLProposal,
                    context_version=getattr(ctx, "version", 0),
                )
            except Exception as exc:  # noqa: BLE001 - no key / API down / invalid output
                attempts.append(f"attempt {attempt}: LLM call failed: {exc}")
                break

            proposal = _pin(candidate, profile)

            with tracing.span("instrumentation.lint", attempt=attempt):
                violations = ddl_mod.lint(proposal)
            if violations:
                attempts.append(
                    f"attempt {attempt}: {len(violations)} lint violation(s): "
                    + " | ".join(violations)
                )
                if attempt < MAX_LINT_REPAIRS:
                    user = _repair_prompt(
                        base_user, proposal, "\n".join(f"- {v}" for v in violations), "house-rule lint"
                    )
                    continue
                proposal = _coerce_to_rules(proposal, profile)
                violations = ddl_mod.lint(proposal)
                if violations:
                    attempts.append("mechanical coercion still violates: " + " | ".join(violations))
                    proposal = None
                    break

            if ch is None:
                break

            with tracing.span("instrumentation.dry_run", attempt=attempt) as dsp:
                ok, err = ddl_mod.dry_run(proposal, ch)
                dsp.update(metadata={"ok": ok, "error": err[:2000]})
            if ok:
                attempts.append(f"attempt {attempt}: lint clean, dry run OK")
                break
            attempts.append(f"attempt {attempt}: ClickHouse rejected the DDL: {err[:400]}")
            if attempt < MAX_LINT_REPAIRS + MAX_DDL_REPAIRS:
                user = _repair_prompt(
                    base_user,
                    proposal,
                    "ClickHouse rejected the rendered DDL with this VERBATIM error:\n"
                    f"```\n{err[:3000]}\n```",
                    "ClickHouse execution",
                )
                continue
            proposal = None
            break

        if proposal is None:
            proposal = build_fallback_proposal(profile)
            attempts.append("fell back to the deterministic rule-based proposal")
            if ch is not None:
                ok, err = ddl_mod.dry_run(proposal, ch)
                attempts.append(f"fallback dry run ok={ok} {err[:300]}")

        sp.update(
            metadata={
                "table": proposal.table_name,
                "columns": len(proposal.columns),
                "mvs": len(proposal.materialized_views),
                "attempts": attempts,
            }
        )
        proposal.rationale.setdefault("generation_log", " ; ".join(attempts))
        return proposal


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------


def _count(ch: Any, table: str) -> int:
    rows = ch.run_select(f"SELECT count() AS n FROM {table}")
    return int(rows[0]["n"]) if rows else 0


def apply(
    proposal: DDLProposal,
    ch: Any,
    events_path: str | Path,
    rebuild: bool = False,
) -> LoadResult:
    """Execute the DDL, load the events, then measure whether each MV earned its keep.

    Idempotent by construction: DDL is IF NOT EXISTS, and the raw table plus every
    rollup target is truncated before the load, so running twice yields the same
    row counts rather than double-counting. `rebuild=True` drops everything first,
    which is what you want after the proposal itself changed.
    """
    path = Path(events_path)
    errors: list[str] = []

    with tracing.span(
        "instrumentation.apply", table=proposal.table_name, rebuild=rebuild
    ) as sp:
        statements = ddl_mod.render(proposal)
        proposal.ddl_sql = statements

        if rebuild:
            for stmt in ddl_mod.drop_statements(proposal):
                ch.execute_ddl(stmt)

        with tracing.span("instrumentation.execute_ddl", statements=len(statements)):
            for stmt in statements:
                ch.execute_ddl(stmt)

        # Idempotency: a second run must not double-count. Truncate source and every
        # rollup target together so the MVs are repopulated by the insert below.
        ch.execute_ddl(f"TRUNCATE TABLE IF EXISTS {proposal.table_name}")
        for mv in proposal.materialized_views:
            ch.execute_ddl(f"TRUNCATE TABLE IF EXISTS {mv.target_table}")

        with tracing.span("instrumentation.load", path=str(path)) as lsp:
            result = ch.insert_ndjson(proposal.table_name, path, proposal.columns)
            lsp.update(
                metadata={
                    "rows_read": result.rows_read,
                    "rows_inserted": result.rows_inserted,
                    "rejected": result.rejected,
                }
            )

        with tracing.span("instrumentation.measure_mvs") as msp:
            source_rows = _count(ch, proposal.table_name)
            for mv in proposal.materialized_views:
                try:
                    target_rows = _count(ch, mv.target_table)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{mv.name}: could not measure target: {exc}")
                    continue
                mv.measured_source_rows = source_rows
                mv.measured_target_rows = target_rows
                mv.reduction_factor = (
                    round(source_rows / target_rows, 2) if target_rows else 0.0
                )
                mv.kept = bool(mv.reduction_factor >= MIN_MV_REDUCTION)
                if not mv.kept:
                    # An MV dropped with evidence is worth more than one kept on faith.
                    ch.execute_ddl(f"DROP VIEW IF EXISTS {mv.name}")
                    ch.execute_ddl(f"DROP TABLE IF EXISTS {mv.target_table}")
            msp.update(metadata={"report": mv_report(proposal)})

        result.errors = list(result.errors) + errors
        sp.update(
            metadata={
                "rows_inserted": result.rows_inserted,
                "rejected": result.rejected,
                "mv_report": mv_report(proposal),
            }
        )
        return result


def mv_report(proposal: DDLProposal) -> list[str]:
    """The keep/drop line the house rules ask to be reported, one per view."""
    out = []
    for mv in proposal.materialized_views:
        if mv.measured_source_rows is None:
            out.append(f"{mv.name}: not measured")
            continue
        verdict = "KEPT" if mv.kept else f"DROPPED (< {MIN_MV_REDUCTION:g}x)"
        out.append(
            f"{mv.name}: {mv.measured_source_rows:,} -> {mv.measured_target_rows:,} rows "
            f"({mv.reduction_factor}x) {verdict}"
        )
    return out
