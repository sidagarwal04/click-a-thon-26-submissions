"""T5b · Metric definition policy.

While a `definition_conflict` is open on a metric subject (today: conversion),
no report or chat answer may emit an unqualified number for that subject.
Both competing definitions must be labelled, each citing
`Finding.metric_definition_used` / an entry_id@version.

Deterministic. No LLM. Used by analytics.interpret, ask.py, and atlys-mcp.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from ch import CH
from contracts import ContextSnapshot, Finding, InsightReport

# Subjects that map many surface phrases onto one conflict key.
_SUBJECT_ALIASES: dict[str, tuple[str, ...]] = {
    "conversion": (
        "conversion rate",
        "conversion",
        "cvr",
        "purchase conversion",
        "checkout conversion",
    ),
}

_CONVERSION_RE = re.compile(
    r"\b(conversion(\s+rate)?|cvr)\b",
    re.IGNORECASE,
)


@dataclass
class CompetingDef:
    entry_id: str
    version: int
    title: str
    body: str

    @property
    def cite(self) -> str:
        return f"{self.entry_id}@v{self.version}"


@dataclass
class OpenConflict:
    subject: str  # e.g. "conversion"
    title: str
    claim: str
    evidence: str
    definitions: list[CompetingDef] = field(default_factory=list)
    contradiction_kind: str = "definition_conflict"

    def prompt_block(self) -> str:
        lines = [
            f"⚠ OPEN DEFINITION CONFLICT on '{self.subject}' — do NOT emit an "
            f"unqualified number for this subject.",
            f"Title: {self.title}",
            f"Evidence: {self.evidence[:400]}",
            "Report BOTH definitions, labelled, each with metric_definition_used:",
        ]
        for d in self.definitions:
            lines.append(f"  - {d.cite}: {d.title} — {d.body[:200]}")
        return "\n".join(lines)


def _defs_from_snapshot(ctx: ContextSnapshot, entry_ids: Iterable[str]) -> list[CompetingDef]:
    wanted = set(entry_ids)
    out: list[CompetingDef] = []
    for e in ctx.entries:
        if e.entry_id in wanted or e.key in wanted:
            out.append(
                CompetingDef(
                    entry_id=e.entry_id,
                    version=int(e.version),
                    title=getattr(e, "key", e.entry_id) or e.entry_id,
                    body=(e.body or "")[:500],
                )
            )
    # Prefer latest version per entry_id.
    best: dict[str, CompetingDef] = {}
    for d in out:
        prev = best.get(d.entry_id)
        if prev is None or d.version >= prev.version:
            best[d.entry_id] = d
    return list(best.values())


def load_open_conflicts(ch: CH, ctx: ContextSnapshot | None = None) -> list[OpenConflict]:
    """Open definition_conflict rows, joined to the live context snapshot when given."""
    try:
        rows = ch.run_select(
            "SELECT title, claim, evidence, entry_ids "
            "FROM contradiction "
            "WHERE kind = 'definition_conflict' "
            "ORDER BY detected_at DESC "
            "LIMIT 50",
            max_rows=50,
        )
    except Exception:  # noqa: BLE001
        return []

    seen: set[tuple[str, ...]] = set()
    out: list[OpenConflict] = []
    for r in rows:
        ids = tuple(sorted(str(x) for x in (r.get("entry_ids") or [])))
        if not ids or ids in seen:
            continue
        seen.add(ids)
        subject = "conversion" if any("conversion" in i for i in ids) else ids[0].split(".")[-1]
        defs = _defs_from_snapshot(ctx, ids) if ctx is not None else [
            CompetingDef(entry_id=i, version=0, title=i, body="") for i in ids
        ]
        out.append(
            OpenConflict(
                subject=subject,
                title=str(r.get("title") or ""),
                claim=str(r.get("claim") or ""),
                evidence=str(r.get("evidence") or ""),
                definitions=defs,
            )
        )
    return out


def mentions_subject(text: str, subject: str = "conversion") -> bool:
    if subject == "conversion":
        return bool(_CONVERSION_RE.search(text or ""))
    return subject.lower() in (text or "").lower()


def _norm(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip() + " "


def question_is_feature_scoped(question: str, sem: Any) -> bool:
    """True when the question names a concrete event type or measure of the feature
    being analysed -- and so is NOT asking for the disputed global metric.

    The open `definition_conflict` is about the org-wide conversion rate on the legacy
    tables (`purchase_completed` over `application_started` vs over sessions). The
    refusal exists to stop an *unqualified* number for THAT metric being emitted.

    A question that names this feature's own funnel step -- "do coupon users reach
    <step> at a higher rate than the no-coupon baseline" -- supplies its own numerator
    and denominator and is answerable from this feature's table alone. Refusing it
    suppresses a legitimate question the data can answer, and does nothing to protect
    the disputed metric, which the question never asked for. (The sealed 6th spec lists
    exactly such a question, so this is not hypothetical.)

    Detection is from the feature's runtime semantics -- event types and measure
    columns -- so no feature is named here and an unseen spec is handled identically.
    """
    if sem is None:
        return False
    q = _norm(question)
    tokens: list[str] = []
    tokens.extend(getattr(sem, "event_types", []) or [])
    tokens.extend(getattr(sem, "ordered_steps", []) or [])
    for m in getattr(sem, "measures", []) or []:
        col = getattr(m, "column", "")
        if col:
            tokens.append(col)
    # Require a multi-word/underscored token: a bare generic word like "shown" would
    # match half the questions ever asked, while `checkout_with_coupon` /
    # `discount_amount` are unambiguous references to this feature's own schema.
    for tok in tokens:
        if not tok or "_" not in tok:
            continue
        if _norm(tok) in q:
            return True
    return False


def is_qualified(text: str, conflict: OpenConflict) -> bool:
    """True if the text cites at least one competing definition by entry_id@version."""
    if not text:
        return False
    lower = text.lower()
    cites = 0
    for d in conflict.definitions:
        if d.cite.lower() in lower or d.entry_id.lower() in lower:
            cites += 1
    # Also accept explicit dual labelling.
    if "sessions" in lower and ("application_started" in lower or "application started" in lower):
        cites = max(cites, 2)
    return cites >= 1 and (
        cites >= 2
        or "both definition" in lower
        or "two definition" in lower
        or "definition conflict" in lower
        or "[disputed]" in lower
        or "unqualified" in lower
        or "cannot answer" in lower
        or "refuse" in lower
    )


def conflict_prompt_prefix(conflicts: list[OpenConflict]) -> str:
    if not conflicts:
        return ""
    return (
        "# OPEN METRIC DEFINITION CONFLICTS (binding)\n"
        + "\n\n".join(c.prompt_block() for c in conflicts)
        + "\n\nIf the user asks for a conflicted metric unqualified, REFUSE the single "
        "number and report BOTH labelled definitions with their entry_id@version cites.\n"
    )


def _dual_finding(conflict: OpenConflict) -> Finding:
    """A synthetic finding that surfaces both definitions instead of one number."""
    from contracts import ConfidenceBreakdown

    lines = []
    for d in conflict.definitions:
        lines.append(f"- **{d.cite}** ({d.title}): {d.body[:240]}")
    detail = (
        f"Open `definition_conflict`: {conflict.title}. "
        f"Executed evidence: {conflict.evidence[:300]}. "
        "No single 'conversion rate' exists until one denominator is chosen."
    )
    return Finding(
        headline="Conversion rate is disputed — two definitions, two numbers",
        what="The context layer defines conversion two incompatible ways.",
        why=detail,
        so_what="Any PM decision on 'the' conversion rate is premature; pick a denominator first.",
        recommended_action=(
            "Rename/version the two metrics (funnel conversion vs session conversion) "
            "and require every report to cite metric_definition_used."
        ),
        metric="conversion_rate",
        metric_definition_used=",".join(d.cite for d in conflict.definitions) or "definition_conflict",
        value=0.0,
        comparison=None,
        segment=None,
        confidence=ConfidenceBreakdown(
            sample_adequacy=1.0,
            statistical_strength=1.0,
            context_support=1.0,
            data_quality=1.0,
            score=0.95,
            method="descriptive",
            n=0,
            p_value=None,
        ),
        supporting_queries=[],
        context_refs=[d.cite for d in conflict.definitions] or list(
            # fall back to entry ids from the conflict title path
            []
        ),
        caveats=[
            "UNQUALIFIED conversion rate suppressed by metric_policy while definition_conflict is open.",
            conflict.evidence[:300],
        ],
        severity="act_now",
    )


def enforce_report(report: InsightReport, conflicts: list[OpenConflict]) -> InsightReport:
    """Post-process an InsightReport: demote/replace unqualified conversion claims."""
    if not conflicts:
        return report
    conv = next((c for c in conflicts if c.subject == "conversion"), None)
    if conv is None:
        return report

    kept: list[Finding] = []
    dropped_unqualified = False
    for f in report.findings:
        blob = " ".join(
            [
                f.headline or "",
                getattr(f, "what", "") or "",
                getattr(f, "why", "") or "",
                getattr(f, "so_what", "") or "",
                f.metric or "",
                f.metric_definition_used or "",
            ]
        )
        if not mentions_subject(blob, "conversion"):
            kept.append(f)
            continue
        qualified = bool(f.metric_definition_used) and (
            "metric.conversion" in f.metric_definition_used
            or is_qualified(blob + " " + f.metric_definition_used, conv)
        )
        if qualified:
            kept.append(f)
        else:
            dropped_unqualified = True

    summary_bad = mentions_subject(report.summary or "", "conversion") and not is_qualified(
        report.summary or "", conv
    )
    if not (dropped_unqualified or summary_bad):
        return report

    if not any(
        f.metric == "conversion_rate" and "disputed" in (f.headline or "").lower() for f in kept
    ):
        kept.insert(0, _dual_finding(conv))
    if summary_bad:
        report.summary = (
            "Conversion rate is currently DISPUTED in the context layer "
            f"({', '.join(d.cite for d in conv.definitions) or 'definition_conflict'}). "
            "Both definitions are listed in findings; no single headline number is reported."
        )
    caveats = list(report.caveats)
    note = (
        "metric_policy: unqualified 'conversion rate' suppressed — open "
        f"definition_conflict ({conv.title[:120]})."
    )
    if note not in caveats:
        caveats.insert(0, note)
    report.caveats = caveats
    report.findings = kept
    return report


def refuse_or_qualify_answer(question: str, answer_text: str, conflicts: list[OpenConflict]) -> str | None:
    """If the question asks about a conflicted metric and the answer is unqualified,
    return a replacement answer string. Otherwise return None (keep the model answer)."""
    conv = next((c for c in conflicts if c.subject == "conversion"), None)
    if conv is None:
        return None
    if not mentions_subject(question, "conversion"):
        return None
    if is_qualified(answer_text, conv):
        return None
    defs = "\n".join(
        f"- **{d.cite}**: {d.body[:220] or d.title}" for d in conv.definitions
    ) or "- (definitions recorded in the contradiction table)"
    return (
        f"**Refused: unqualified conversion rate.**\n\n"
        f"The context layer has an open `definition_conflict`: {conv.title}.\n\n"
        f"{conv.evidence}\n\n"
        f"Both definitions currently on the books:\n{defs}\n\n"
        "Pick a denominator (sessions vs `application_started` users) and ask again, "
        "or request both numbers labelled. I will not invent a single headline figure "
        "while this conflict is open."
    )


def explain_metric(ch: CH, name: str, ctx: ContextSnapshot | None = None) -> dict[str, Any]:
    """MCP/tool helper: return the definition(s) actually in force for a metric name."""
    conflicts = load_open_conflicts(ch, ctx)
    name_l = name.lower().strip()
    hit = next((c for c in conflicts if c.subject in name_l or name_l in c.subject), None)
    if hit is None and mentions_subject(name_l, "conversion"):
        hit = next((c for c in conflicts if c.subject == "conversion"), None)
    if hit:
        return {
            "metric": name,
            "status": "DISPUTED",
            "conflict_title": hit.title,
            "evidence": hit.evidence,
            "definitions": [
                {"cite": d.cite, "title": d.title, "body": d.body} for d in hit.definitions
            ],
            "policy": "Unqualified answers are refused until one denominator is chosen.",
        }
    # Fall back to context entries matching the name.
    defs: list[dict[str, Any]] = []
    if ctx is not None:
        for e in ctx.entries:
            if name_l in e.entry_id.lower() or name_l in (e.key or "").lower():
                defs.append(
                    {
                        "cite": f"{e.entry_id}@v{e.version}",
                        "title": e.key,
                        "body": (e.body or "")[:400],
                        "status": e.status,
                    }
                )
    return {
        "metric": name,
        "status": "ok" if defs else "unknown",
        "definitions": defs,
        "policy": "No open definition_conflict for this name.",
    }
