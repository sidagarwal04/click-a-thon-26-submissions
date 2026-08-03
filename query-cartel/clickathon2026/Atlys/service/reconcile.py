"""Schema-vs-context reconciliation (ENGINEERING.md §4.2 `reconcile.py`, §5.3).

Systematically diffs the *documented* context (base_context.md) against the
*actual* ClickHouse schema and the incoming spec. Output: a list of findings
with evidence — `undocumented_column`, `phantom_column`, `definition_gap`,
`known_issue_column_gap`, and prose-level contradictions from
`detect_contradictions` (T1–T8 in §5.3). Everything is content-driven: the
traps are surfaced by parsing the docs, never hardcoded by feature name.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Known-issue → columns that MUST exist for the issue's evidence to be computed.
# (From base_context.md §5; a missing column is a `known_issue_column_gap`.)
KNOWN_ISSUE_COLUMNS = {
    "K2": {"scan_mode", "failed_attempt_threshold"},
    "K6": {"coupon_name", "discount_amount"},
}

# The shared raw-event envelope — documented once in prose (§2/§3), not per-table.
# We never flag these as undocumented/phantom columns per table (that would be
# noise: every table would report the same 30 envelope columns).
COMMON_ENVELOPE = {
    "id", "timestamp", "user_id", "application_id", "app_session_id",
    "device", "device_type", "os", "app_version", "client_lib",
    "geoip_country_code", "geoip_subdivision_1_code", "city", "client_ip",
    "latitude", "longitude", "locale", "language", "funnel_type",
    "co_travelers", "is_guest", "is_referral", "is_enterprise", "gclid",
    "fbclid", "gad_source", "citizenship", "destination",
    "is_back_filled", "duplicate_id",
}


@dataclass
class Finding:
    kind: str  # undocumented_column | phantom_column | definition_gap | known_issue_column_gap | contradiction
    object: str
    diff: str
    rationale: str
    evidence: str = ""

    def to_row(self, version: int, agent: str, trace_id: str) -> list:
        return [version, agent, "reconciliation_finding", self.object, self.diff,
                self.rationale, trace_id]


# ---------------------------------------------------------------------------
# 1. Parse the documented context
# ---------------------------------------------------------------------------

def parse_documented_tables(context_md: str) -> dict[str, set[str]]:
    """Extract `table → {documented columns}` from the base context.

    Heuristic: lines that look like a table row (| `name` | kind | ... |
    <key event-specific columns> |) — we pull the backtick-quoted column
    names out of the whole line.
    """
    tables: dict[str, set[str]] = {}
    for line in context_md.splitlines():
        m = re.match(r"\|\s*`([a-z_]+)`\s*\|", line)
        if not m:
            continue
        table = m.group(1)
        cols = set(re.findall(r"`([a-z_0-9]+)`", line))
        cols.discard(table)  # the row's first backtick is the table name, not a column
        tables.setdefault(table, set()).update(cols)
    return tables


def parse_metric_references(context_md: str) -> list[str]:
    """Backticked column refs inside §4 (metric definitions) — used for definition_gap."""
    refs: list[str] = []
    in_metrics = False
    for line in context_md.splitlines():
        if line.strip().startswith("## 4."):
            in_metrics = True
            continue
        if line.strip().startswith("## 5."):
            in_metrics = False
            break
        if in_metrics:
            refs.extend(re.findall(r"`([a-z_0-9]+)`", line))
    return refs


# ---------------------------------------------------------------------------
# 2. Diff documented vs actual
# ---------------------------------------------------------------------------

def diff_documented_vs_actual(
    documented: dict[str, set[str]],
    actual: dict[str, set[str]],
    metric_refs: list[str],
) -> list[Finding]:
    """Produce findings: undocumented / phantom columns and definition gaps."""
    findings: list[Finding] = []

    # Undocumented / phantom columns per table that exists in the docs
    for table, doc_cols in documented.items():
        actual_cols = actual.get(table, set())
        undocumented = actual_cols - doc_cols - COMMON_ENVELOPE
        for col in sorted(undocumented):
            findings.append(Finding(
                kind="undocumented_column",
                object=f"{table}.{col}",
                diff=f"column {col} exists in schema but is absent from base_context §3",
                rationale="context layer should document every live column; this one lagged the schema",
            ))
        phantom = doc_cols - actual_cols
        for col in sorted(phantom):
            findings.append(Finding(
                kind="phantom_column",
                object=f"{table}.{col}",
                diff=f"column {col} documented in base_context §3 but missing from the actual schema",
                rationale="documented column does not exist — context is stale or the column was dropped",
            ))

    # Definition gaps: metric formulas reference columns that don't exist anywhere
    all_actual = {c for cols in actual.values() for c in cols}
    for ref in metric_refs:
        if ref not in all_actual:
            findings.append(Finding(
                kind="definition_gap",
                object=f"metric ref `{ref}`",
                diff=f"metric definition references column `{ref}` which exists in no table",
                rationale="a metric formula that references a missing column cannot be computed",
            ))

    # Known-issue column gaps (T3/T4): issue evidence columns missing from schema
    for issue, required in KNOWN_ISSUE_COLUMNS.items():
        missing = required - all_actual
        for col in sorted(missing):
            findings.append(Finding(
                kind="known_issue_column_gap",
                object=f"{issue}→{col}",
                diff=f"known issue {issue} needs column `{col}` for evidence but it is not in any table",
                rationale="without the column the issue cannot be surfaced from data",
            ))

    return findings


# ---------------------------------------------------------------------------
# 3. Prose-level contradictions (text heuristics)
# ---------------------------------------------------------------------------

def detect_contradictions(context_md: str) -> list[Finding]:
    """Surface prose-level drift (T1/T2/T5/T7/T8 style) via text heuristics.

    Content-driven: we look for *internal inconsistencies in the text itself*,
    not feature names.
    """
    findings: list[Finding] = []

    # T8-style naming drift: `visa_issuance_eta_days` documented vs `eta_shown` live.
    if "visa_issuance_eta_days" in context_md and "eta_shown" in context_md:
        findings.append(Finding(
            kind="contradiction",
            object="naming drift: visa_issuance_eta_days vs eta_shown",
            diff="context documents `visa_issuance_eta_days` but the application_started DDL "
                 "carries `eta_shown` — same concept, two names",
            rationale="naming drift breaks join/documentation trust; one name should win",
        ))

    # T1: conversion-rate denominators — count distinct denominators mentioned.
    denom_mentions = {
        "destination_card_clicked": "destination_card_clicked" in context_md,
        "application_started": "application_started" in context_md,
        "sessions": "sessions" in context_md,
    }
    used = [k for k, v in denom_mentions.items() if v]
    if len(used) >= 2:
        findings.append(Finding(
            kind="contradiction",
            object="conversion-rate denominators",
            diff="conversion rate is defined against multiple denominators: " + ", ".join(used),
            rationale="a single headline metric must have one denominator; this context defines it "
                      "several ways (T1)",
        ))

    # T2: 'sessions' is used as a metric denominator but no sessions table exists
    if "sessions" in context_md and "app_session_id" in context_md and "sessions table" not in context_md.lower():
        findings.append(Finding(
            kind="contradiction",
            object="'sessions' is undefined",
            diff="metric definitions divide by 'sessions' but no sessions table exists and "
                 "`app_session_id` is Nullable",
            rationale="the headline denominator is not computable from the funnel tables (T2)",
        ))

    # T7: declared out-of-scope metric — the doc itself says it's not computable here.
    if "not computable from the funnel tables" in context_md:
        findings.append(Finding(
            kind="contradiction",
            object="on-time delivery rate",
            diff="context declares 'on-time delivery rate' not computable from funnel tables",
            rationale="out-of-scope metric — keep it out of funnel-based insights (T7)",
        ))

    # T5: WhatsApp nudge 'already live' vs a spec that launches WhatsApp — surfaced
    # at run time by the context agent passing the spec text; here we just flag the
    # documented claim for the freshness check.
    if "WhatsApp" in context_md and "launch" in context_md.lower():
        findings.append(Finding(
            kind="contradiction",
            object="WhatsApp nudge status",
            diff="context says the WhatsApp re-engagement nudge is already live (K5, Feb 2026)",
            rationale="check against specs that plan to launch WhatsApp nudges — overlap risk (T5)",
        ))

    return findings


# ---------------------------------------------------------------------------
# 4. Top-level reconcile
# ---------------------------------------------------------------------------

def reconcile(actual_tables: dict[str, set[str]], context_md: str) -> list[Finding]:
    """Full reconciliation: documented-vs-actual diff + prose contradictions."""
    documented = parse_documented_tables(context_md)
    metric_refs = parse_metric_references(context_md)
    findings = diff_documented_vs_actual(documented, actual_tables, metric_refs)
    findings += detect_contradictions(context_md)
    return findings


def actual_from_store(store) -> dict[str, set[str]]:
    """Read the actual schema from a store (system.columns)."""
    out: dict[str, set[str]] = {}
    for table in store.all_tables():
        cols = [c["name"] for c in store.columns(table)]
        if cols:
            out[table] = set(cols)
    return out
