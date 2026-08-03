"""
ContextAgent -- the single object every other agent talks to for context.

Business context is ONE whole Markdown document, not decomposed into rows.
It lives in analytics_context.business_context (doc_id, content, version,
changelog_summary, updated_at), a ReplacingMergeTree keyed on doc_id: every
change -- the initial seed, new tables being documented, an audit finding a
flag, a flag being resolved, AnalyticsAgent recording a batch of findings --
INSERTs a new version rather than mutating any row in place, so the table
doubles as the full audit trail. Callers always read the latest version and
inject `content` directly into their prompts; there is no per-row filtering to
do because the document is the atomic unit.

New tables are appended as rows to Section 3's existing table catalog (not a
separate section); AnalyticsAgent's findings land in their own Section 10.
Both update_context() and add_analytical_findings() are meant to be called
ONCE per batch of work (once per spec's tables, once per analysis run) --
never once per item -- to keep the version history meaningful instead of
noisy; see each method's docstring.

Fixed interface: load_v1, get_latest_context, update_context, run_audit,
resolve_flag, add_analytical_findings.
"""

import json
import re
from datetime import datetime, timezone

import clickhouse_connect

from .load_base_context import DOC_ID, OPEN_FLAGS_MARKER, FINDINGS_MARKER, NONE_YET, NONE_OPEN, build_seed_content
from .audit_base_context import freshness_check, AUDIT_PROMPT, parse_llm_json

UPDATE_PROMPT = """New ClickHouse tables were just created for a feature spec. Describe EACH
one the same way the existing "raw event tables" catalog does: a "kind" (funnel/supporting/
dimension), a short "emitted when" phrase (~6-10 words, e.g. "user taps Pay Now at
checkout"), and its 2-5 most important columns -- skip the standard envelope (id,
timestamp, user_id, application_id), name the columns specific to what this table
actually captures.

NEW TABLES:
{tables_block}

SPEC THEY CAME FROM:
{source_spec}

Respond as JSON: {{"tables": [{{"name": "...", "kind": "funnel|supporting|dimension",
"emitted_when": "...", "key_columns": ["col1", "col2"]}}, ...], "changelog_summary": "one line covering all tables"}}
No prose, no markdown fences outside the JSON string values.
"""

RESOLVE_PROMPT = """You are resolving an open flag in a business-context document.
Entity: {entity}
Key: {key}
Flag line: {flag_line}

Provide a short resolution note explaining how this should be understood/fixed going
forward (1-3 sentences). Respond in JSON: {{"resolution_notes": "..."}}
No prose, no markdown fences.
"""

# Enforces Section 5's own mandatory rule (base_context.md): a known issue that
# fresh query results contradict must be corrected, not left to go stale.
KNOWN_ISSUE_CORRECTION_PROMPT = """You are checking whether new analytical findings
contradict any entry in a "Known-issues log" (a numbered list of known data/product
issues, each tagged K1, K2, etc). An insight CONTRADICTS a known issue only if the data
now shows the issue's own claim is wrong, resolved, or meaningfully different from what
it states -- not merely "related to" or "about the same table as" it. Most findings
contradict nothing; don't force a match.

KNOWN-ISSUES LOG:
{known_issues}

NEW ANALYTICAL FINDINGS:
{findings}

For each known issue a finding directly contradicts, provide a corrected replacement for
that ENTIRE numbered item -- keep its number and Kn tag exactly (e.g. "3. **K3 — ...** ...")
and rewrite the rest to reflect what the data now shows.

Respond as JSON: {{"corrections": [{{"kn": "K3", "corrected_block": "3. **K3 — ...** ...", "reason": "one line"}}]}}
If nothing contradicts, respond {{"corrections": []}}. No prose, no markdown fences outside
the JSON string values.
"""

# A flag is rendered as one bullet line, in a format that's both readable and
# machine-parseable so re-auditing an unchanged document doesn't re-flag the
# same issue every time (see _existing_flag_keys()).
_FLAG_LINE_RE = re.compile(r"^- \*\*\[(?P<flag_type>[^\]]+)\]\*\* `(?P<entity>[^`]*)` */ *`(?P<key>[^`]*)`", re.MULTILINE)

# Stops a spliced region at the next top-level heading, the next `---` section
# divider, or end of document -- whichever comes first. Keeps the divider
# between sections intact across replacements instead of it being swallowed
# into whatever gets spliced in.
_SECTION_STOP = r"(?=\n---\s*\n|\n##\s|\Z)"


def _extract_entries(markdown: str, marker: str) -> str:
    pattern = re.compile(re.escape(marker) + r"\n(.*?)" + _SECTION_STOP, re.DOTALL)
    match = pattern.search(markdown)
    return match.group(1) if match else ""


def _replace_entries(markdown: str, marker: str, new_body: str) -> str:
    pattern = re.compile("(" + re.escape(marker) + r"\n)(.*?)" + _SECTION_STOP, re.DOTALL)
    match = pattern.search(markdown)
    if not match:
        raise ValueError(f"Marker {marker!r} not found in document -- was it seeded via build_seed_content()?")
    return markdown[:match.start(2)] + new_body.strip() + "\n" + markdown[match.end(2):]


def _is_empty_placeholder(entries: str) -> bool:
    stripped = entries.strip()
    return stripped in ("", NONE_YET, NONE_OPEN)


def _extract_section_by_heading(markdown: str, heading_text: str) -> str:
    """Read-only extraction of a whole section's body by heading text (handles
    an optional leading "N. " number), for sections that aren't marker-based --
    e.g. Section 5's Known-issues log, which AnalyticsAgent's findings get
    checked against but never append to directly."""
    pattern = re.compile(
        rf"^##\s*(?:\d+\.\s*)?{re.escape(heading_text)}[^\n]*\n(.*?)" + _SECTION_STOP,
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    return match.group(1) if match else ""


# Matches one numbered item in Section 5's Known-issues log, e.g. "3. **K3 —
# Title.** description text...", up through (but not including) the next
# numbered item or the section's end. Used to replace a single Kn entry in
# place without touching the rest of the log.
def _known_issue_pattern(kn: str) -> re.Pattern:
    return re.compile(
        rf"\d+\.\s+\*\*{re.escape(kn)}\b.*?(?=\n\d+\.\s+\*\*K\d+|\n---\s*\n|\n##\s|\Z)",
        re.DOTALL,
    )


def _replace_known_issue(markdown: str, kn: str, corrected_block: str) -> bool | str:
    """Replaces the numbered item tagged `kn` (e.g. "K3") with corrected_block.
    Returns the updated markdown, or False if `kn` wasn't found (nothing
    corrected -- caller decides whether that's worth logging)."""
    match = _known_issue_pattern(kn).search(markdown)
    if not match:
        return False
    return markdown[:match.start()] + corrected_block.strip() + "\n" + markdown[match.end():]


def _render_flag_line(flag: dict) -> str:
    flag_type = flag.get("flag_type", "ambiguous_definition")
    entity = flag.get("entity", "")
    key = flag.get("key", "")
    description = flag.get("description", "")
    return f"- **[{flag_type}]** `{entity}` / `{key}` -- {description}"


def _existing_flag_keys(entries: str) -> set[tuple[str, str, str]]:
    return {
        (m.group("flag_type"), m.group("entity"), m.group("key"))
        for m in _FLAG_LINE_RE.finditer(entries)
    }


# Section 3 (base_context.md's "raw event tables" catalog) is a Markdown table,
# not a marker+bullets section like Open flags/Analytical findings -- new tables
# get appended as additional rows to this SAME table rather than a separate
# section, so the document has one place that lists tables, not two. Matches
# structurally on the table's own header (fixed since v1) and captures the
# contiguous block of `| ... |` rows that follows it; appending just means
# inserting more such rows at the end of that block.
_SECTION3_TABLE_RE = re.compile(
    r"(\| Table \| Kind \| Emitted when \| Key event-specific columns \|\n\|[-\s|]*\|\n)((?:\|.*\|\n)+)"
)


def _extract_section3_rows(markdown: str) -> str:
    match = _SECTION3_TABLE_RE.search(markdown)
    return match.group(2) if match else ""


def _append_section3_rows(markdown: str, new_rows: str) -> str:
    match = _SECTION3_TABLE_RE.search(markdown)
    if not match:
        raise ValueError("Section 3's table not found in document -- has its header format changed?")
    rows_text = new_rows if new_rows.endswith("\n") else new_rows + "\n"
    return markdown[:match.end(2)] + rows_text + markdown[match.end(2):]


def _render_table3_row(table: dict) -> str:
    """Renders one LLM-described table as a Section 3 row, in Python rather
    than trusting the LLM to hand-format valid pipe-table syntax -- a literal
    `|` anywhere in an LLM-written field would otherwise silently break the
    table, so it's escaped here rather than left to chance."""
    def esc(value) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ").strip()

    name = esc(table.get("name", ""))
    kind = esc(table.get("kind", "supporting"))
    emitted_when = esc(table.get("emitted_when", ""))
    columns = table.get("key_columns") or []
    columns_str = ", ".join(f"`{esc(c)}`" for c in columns) if columns else "—"
    return f"| `{name}` | {kind} | {emitted_when} | {columns_str} |"


class ContextAgent:
    def __init__(self, client, llm_call_fn):
        self.client = client
        self.llm_call_fn = llm_call_fn  # Wrapped in Langfuse span at call sites

    # ============================================================
    # Reading
    # ============================================================

    def _latest_doc(self, doc_id: str = DOC_ID) -> dict:
        query = f"""
            SELECT doc_id, content, version, changelog_summary, updated_at
            FROM analytics_context.business_context
            WHERE doc_id = '{doc_id}'
            ORDER BY version DESC
            LIMIT 1
        """
        result = self.client.query(query)
        if not result.result_rows:
            return {"doc_id": doc_id, "content": "", "version": 0, "changelog_summary": "", "updated_at": None}
        return dict(zip(result.column_names, result.result_rows[0]))

    def get_latest_context(self, entities: list[str] | None = None) -> dict:
        """Returns the latest version of the unified business-context document:
        {doc_id, content, version, changelog_summary, updated_at}.

        `entities` is accepted for backward compatibility with callers written
        against the old per-row context model, but no longer filters anything --
        the document is one atomic whole now, so callers inject `content`
        directly into their prompts rather than filtering structured rows.
        """
        return self._latest_doc()

    def _insert_version(self, content: str, version: int, changelog_summary: str, doc_id: str = DOC_ID) -> None:
        # async_insert=0: forces a synchronous, durable write. This ClickHouse
        # Cloud service defaults to async_insert=1 (server-side buffering before
        # a background flush); observed live, rapid-fire small control-plane
        # inserts silently lost rows when the process moved on before the async
        # buffer flushed. Every write here is low-volume and correctness-critical.
        self.client.insert(
            "analytics_context.business_context",
            [[doc_id, content, version, changelog_summary, datetime.now(timezone.utc)]],
            column_names=["doc_id", "content", "version", "changelog_summary", "updated_at"],
            settings={"async_insert": 0},
        )

    # ============================================================
    # Seeding
    # ============================================================

    def load_v1(self, force: bool = False) -> int:
        """Seeds version 1 of the business-context document from base_context.md
        (plus the operational sections -- auto-instrumented tables, freshness
        check, open flags -- appended by build_seed_content()).

        Guarded by default: analytics_context.business_context is a plain
        ReplacingMergeTree with no dedup until merge, so calling this twice
        would leave a stray duplicate version=1 row until the background merge
        catches up. Pass force=True to reseed anyway.
        """
        if not force:
            existing = self._latest_doc()
            if existing["version"] > 0:
                print(f"analytics_context.business_context already seeded ({DOC_ID} at version {existing['version']}) -- skipping load_v1() (pass force=True to reseed anyway).")
                return 0

        content = build_seed_content()
        self._insert_version(content=content, version=1, changelog_summary="Initial seed from base_context.md")
        return 1

    # ============================================================
    # LLM plumbing
    # ============================================================

    def _call_llm_json(self, prompt: str, span_name: str):
        """Call the LLM and parse its JSON response, returning None on any
        failure (API error or malformed JSON) instead of raising -- every
        other LLM call site in this codebase already degrades gracefully on
        LLM failure, so a single flaky call doesn't take the whole pipeline down."""
        try:
            try:
                raw = self.llm_call_fn(prompt, span_name=span_name)
            except TypeError:
                raw = self.llm_call_fn(prompt)
            return parse_llm_json(raw)
        except Exception as e:
            print(f"Warning: ContextAgent LLM call ({span_name}) failed, skipping: {e}")
            return None

    # ============================================================
    # Auto-update on new tables
    # ============================================================

    def update_context(self, new_tables: list[dict], source_spec: str) -> int | None:
        """Invoked once per spec by InstrumentationAgent, after ALL of that
        spec's tables have been created -- not once per table. `new_tables` is
        a list of {"name": str, "ddl": str} dicts.

        Appends one row per table directly to Section 3's existing table --
        the same "raw event tables" catalog base_context.md ships with 8 rows
        in -- rather than a separate "auto-instrumented" section, so the
        document has ONE place that lists tables, not two. One LLM call
        describes every table in a single pass (never a rewrite of the whole
        document -- see module docstring for why); Python renders the actual
        table row so a stray `|` in an LLM-written field can't corrupt the
        table. Then re-audits once so any new contradiction/gap/staleness
        these tables introduce gets surfaced in the same pass. A spec
        producing N tables used to mean up to 2N new document versions (N
        update_context calls, each with its own trailing run_audit); batched,
        it's at most 2 regardless of N.
        """
        if not new_tables:
            return None

        table_names = [t["name"] for t in new_tables]
        latest = self._latest_doc()
        if latest["version"] == 0:
            print(f"Warning: business context not seeded yet -- call load_v1() first. Skipping update_context for {table_names}.")
            return None

        tables_block = "\n\n".join(f"TABLE: {t['name']}\nDDL:\n{t['ddl']}" for t in new_tables)
        prompt = UPDATE_PROMPT.format(
            tables_block=tables_block,
            source_spec=(source_spec or "")[:4000],
        )
        parsed = self._call_llm_json(prompt, "context_update")
        if parsed is None:
            print(f"Skipping context update for {table_names} (LLM call failed) -- tables were still created, just without context enrichment.")
            return None

        table_entries = parsed.get("tables", [])
        if not isinstance(table_entries, list):
            table_entries = []
        new_rows = "\n".join(_render_table3_row(t) for t in table_entries if isinstance(t, dict) and t.get("name"))
        if not new_rows:
            print(f"Skipping context update for {table_names} -- LLM returned no table rows.")
            return None

        new_content = _append_section3_rows(latest["content"], new_rows)

        next_version = latest["version"] + 1
        changelog = str(parsed.get("changelog_summary") or f"Added {len(new_tables)} table(s) to Section 3: {', '.join(table_names)}")
        self._insert_version(content=new_content, version=next_version, changelog_summary=changelog)
        print(f"Updated business context to version {next_version}: {changelog}")

        # Re-audit new state once for the whole batch -- only writes yet
        # another version if it actually finds something new.
        self.run_audit(scope=table_names)
        return next_version

    # ============================================================
    # Auditing -- contradictions/gaps (LLM) + obsolete data (deterministic)
    # ============================================================

    def run_audit(self, scope: list[str] | None = None) -> list[dict]:
        """Surfaces contradictions, gaps, and obsolete/stale facts in the
        business-context document:
        - freshness_check(): deterministic, no LLM -- does every table
          InstrumentationAgent has registered still actually exist? This is
          exactly the check Section 8 (Data freshness check) tells readers to
          run; running it here means the document polices its own staleness.
        - An LLM pass over the full document for contradictions/ambiguity it
          can support from the text alone.

        New flags (deduped against ones already listed under Section 9) are
        appended there and a new version is written; if nothing new is found,
        no version is written and an empty list is returned -- re-running audit
        on an unchanged document doesn't pile up duplicate flags or noise the
        version history.

        Known limitation: dedup is exact-match on (flag_type, entity, key) plus
        showing the LLM the already-flagged list in-prompt -- freshness_check()'s
        flags are deterministic so this is exact, but the LLM's own entity/key
        choice for the SAME underlying contradiction isn't perfectly stable
        across independent calls (observed live: `metric.conversion_rate`/
        `session_undefined` vs `entity.session`/`session_undefined` for what's
        the same issue). Calling run_audit() repeatedly with no document change
        in between can occasionally add a near-duplicate, differently-worded
        flag rather than recognizing it as one already raised. A text-similarity
        heuristic was tried and rejected -- it scored two genuinely different
        freshness flags (different table, near-identical template sentence) as
        MORE similar than two genuinely-the-same LLM flags (same issue, very
        different phrasing), so it would suppress real distinct flags rather
        than catch true duplicates.
        """
        latest = self._latest_doc()
        if latest["version"] == 0:
            print("Warning: business context not seeded yet -- call load_v1() first. Skipping run_audit().")
            return []

        current_entries = _extract_entries(latest["content"], OPEN_FLAGS_MARKER)
        existing_keys = _existing_flag_keys(current_entries)

        flags = list(freshness_check(self.client))

        # Showing the LLM what's already flagged is the primary defense against
        # re-flagging the same issue reworded (e.g. `metric.conversion_rate` /
        # `session_undefined` vs `entity.session` / `session_undefined` on two
        # different audit passes -- observed live, since entity/key are LLM
        # free text, not a stable identifier). The exact-tuple check below is
        # a secondary safety net, not the primary mechanism.
        audit_prompt = AUDIT_PROMPT.format(
            document=latest["content"][:16000],
            existing_flags=current_entries if not _is_empty_placeholder(current_entries) else "(none yet)",
        )
        llm_flags = self._call_llm_json(audit_prompt, "context_audit")
        if isinstance(llm_flags, list):
            flags.extend(f for f in llm_flags if isinstance(f, dict))
        elif isinstance(llm_flags, dict):
            flags.append(llm_flags)

        new_flags = [
            f for f in flags
            if (f.get("flag_type", "ambiguous_definition"), f.get("entity", ""), f.get("key", "")) not in existing_keys
        ]
        if not new_flags:
            return []

        new_lines = "\n".join(_render_flag_line(f) for f in new_flags)
        updated_entries = new_lines if _is_empty_placeholder(current_entries) else f"{current_entries.rstrip()}\n{new_lines}"
        new_content = _replace_entries(latest["content"], OPEN_FLAGS_MARKER, updated_entries)

        next_version = latest["version"] + 1
        scope_note = f" (scope: {', '.join(scope)})" if scope else ""
        changelog = f"Audit found {len(new_flags)} new flag(s){scope_note}"
        self._insert_version(content=new_content, version=next_version, changelog_summary=changelog)
        print(f"Updated business context to version {next_version}: {changelog}")
        return new_flags

    # ============================================================
    # Resolving a flag
    # ============================================================

    def resolve_flag(self, entity: str, key: str) -> str | None:
        """Resolves an open flag matching (entity, key): asks the LLM for a
        resolution note, removes the flag line from Section 9, and writes a
        new version whose changelog records the resolution. Returns the
        resolution note, or None if no matching open flag was found (or the
        LLM call failed).
        """
        latest = self._latest_doc()
        if latest["version"] == 0:
            return None

        current_entries = _extract_entries(latest["content"], OPEN_FLAGS_MARKER)
        lines = current_entries.splitlines()
        matching = [ln for ln in lines if f"`{entity}`" in ln and f"`{key}`" in ln]
        if not matching:
            print(f"No open flag found for {entity}.{key}")
            return None

        prompt = RESOLVE_PROMPT.format(entity=entity, key=key, flag_line=matching[0])
        res = self._call_llm_json(prompt, "context_resolve")
        if res is None:
            print(f"Skipping resolution for {entity}.{key} (LLM call failed).")
            return None
        resolution_notes = str(res.get("resolution_notes", ""))

        remaining = [ln for ln in lines if ln not in matching]
        new_entries = "\n".join(remaining) if remaining else NONE_OPEN
        new_content = _replace_entries(latest["content"], OPEN_FLAGS_MARKER, new_entries)

        next_version = latest["version"] + 1
        changelog = f"Resolved flag {entity}.{key}: {resolution_notes}"
        self._insert_version(content=new_content, version=next_version, changelog_summary=changelog)
        print(f"Updated business context to version {next_version}: {changelog}")
        return resolution_notes

    # ============================================================
    # Recording AnalyticsAgent's findings
    # ============================================================

    def add_analytical_findings(self, insights: list, source: str = "") -> int | None:
        """Appends AnalyticsAgent's found insights to Section 10 (Analytical
        findings), and -- per Section 5's own mandatory rule -- checks whether
        any of them contradict a known issue there, correcting it in place if
        so. Both happen as ONE batch, ONE version. Call this ONCE after a run
        finishes -- e.g. once at the end of run_full_analysis(), or once at
        the end of an interactive session, never per-insight -- for the same
        reason update_context() batches per-spec rather than per-table: N
        insights written one at a time would mean N version bumps for a
        single analysis pass.

        The Section 10 append is purely mechanical (no LLM call): insights
        already have a title/description/severity from
        generate_narrative_insights(), so this just renders them as bullets.
        Accepts anything with those three attributes (duck-typed, so callers
        don't need to import Insight from agents.analytics.agent just to call
        this). The known-issue check is the one LLM call in this method.
        """
        if not insights:
            return None
        latest = self._latest_doc()
        if latest["version"] == 0:
            print("Warning: business context not seeded yet -- call load_v1() first. Skipping add_analytical_findings().")
            return None

        source_note = f" ({source})" if source else ""
        new_lines = "\n".join(
            f"- **[{getattr(i, 'severity', 'info')}] {getattr(i, 'title', '')}**{source_note} -- {getattr(i, 'description', '')}"
            for i in insights
        )
        if not new_lines.strip():
            return None

        content = latest["content"]
        current_entries = _extract_entries(content, FINDINGS_MARKER)
        new_entries = new_lines if _is_empty_placeholder(current_entries) else f"{current_entries.rstrip()}\n{new_lines}"
        content = _replace_entries(content, FINDINGS_MARKER, new_entries)

        corrected_kns = []
        for correction in self._check_known_issue_contradictions(insights, content):
            updated = _replace_known_issue(content, correction["kn"], correction["corrected_block"])
            if updated is not False:
                content = updated
                corrected_kns.append(f"{correction['kn']} ({correction['reason']})")

        next_version = latest["version"] + 1
        changelog = f"Added {len(insights)} analytical finding(s){source_note}"
        if corrected_kns:
            changelog += f"; corrected known issue(s): {', '.join(corrected_kns)}"
        self._insert_version(content=content, version=next_version, changelog_summary=changelog)
        print(f"Updated business context to version {next_version}: {changelog}")
        return next_version

    def _check_known_issue_contradictions(self, insights: list, content: str) -> list[dict]:
        """One LLM call, batched across the whole insight set: does any
        insight directly contradict a Section 5 known issue? Returns
        corrections with a valid kn/corrected_block; anything malformed is
        dropped rather than risking a bad splice into Section 5."""
        known_issues = _extract_section_by_heading(content, "Known-issues log")
        if not known_issues.strip():
            return []

        findings_text = "\n".join(
            f"- [{getattr(i, 'severity', 'info')}] {getattr(i, 'title', '')}: {getattr(i, 'description', '')}"
            for i in insights
        )
        prompt = KNOWN_ISSUE_CORRECTION_PROMPT.format(known_issues=known_issues, findings=findings_text)
        parsed = self._call_llm_json(prompt, "context_known_issue_check")
        if not isinstance(parsed, dict):
            return []
        corrections = parsed.get("corrections", [])
        if not isinstance(corrections, list):
            return []
        return [
            c for c in corrections
            if isinstance(c, dict) and c.get("kn") and str(c.get("corrected_block", "")).strip()
        ]


if __name__ == "__main__":
    client = clickhouse_connect.get_client(
        host="<your-service-host>", username="<user>", password="<password>", database="agent_control",
    )

    def llm_call_fn(prompt: str, span_name: str = "test") -> str:
        raise NotImplementedError("Wire to Anthropic / OpenAI API call")

    agent = ContextAgent(client, llm_call_fn)
    print("ContextAgent initialized successfully.")
