"""
Seed (version 1) content for analytics_context.business_context.

Reads the human-authored base_context.md verbatim and appends the operational
sections ContextAgent maintains automatically from then on: the data-freshness
check, open flags, and analytical findings. Keeping these out of base_context.md
itself means the checked-in file stays a pure, hand-edited business document,
while the database copy is the one that actually evolves (each edit is a new
versioned row, never an in-place mutation -- see agents/context/agent.py).

Two agent-maintained sections (Open flags, Analytical findings) carry an
HTML-comment marker right before their entries; ContextAgent splices new
entries in right after the marker rather than replacing the whole section
body, so the section's own descriptive preamble text never has to be
reconstructed or matched against.

New tables InstrumentationAgent creates do NOT get their own section -- they're
appended as additional rows directly to Section 3's existing table (the same
"| Table | Kind | Emitted when | Key event-specific columns |" markdown table
base_context.md already ships with 8 rows of), so the document has ONE place
that lists tables, not two. That splice is structural (find the table's row
block, append), not marker-based -- see agents/context/agent.py's
_append_section3_rows()/_extract_section3_rows().
"""

from pathlib import Path

DOC_ID = "atlys_base_context"

OPEN_FLAGS_MARKER = "<!-- open-flags:entries -->"
FINDINGS_MARKER = "<!-- analytical-findings:entries -->"

_BASE_CONTEXT_PATH = Path(__file__).resolve().parent.parent.parent / "base_context.md"

NONE_YET = "_None yet._"
NONE_OPEN = "_None open._"


def _operational_sections() -> str:
    return f"""
---

## 8. Data freshness check

Before trusting any fact in this document, verify it is still current:

1. Compare this document's `version` against whatever version you last read --
   `SELECT version FROM analytics_context.business_context WHERE doc_id = '{DOC_ID}'
   ORDER BY version DESC LIMIT 1`. If it's newer, re-fetch before relying on this content.
2. Every table named in Section 3 -- including rows `ContextAgent.update_context()`
   has appended there since v1, not just the original 8 -- should still exist in
   `system.tables` (`database = 'atlys'`), and every column named should exist in
   `system.columns`. `ContextAgent.run_audit()` checks this automatically -- a
   deterministic pass against `atlys.meta_context_registry`, no LLM needed for this
   part -- and lists anything missing under Section 9. If that section is non-empty,
   treat the corresponding facts above as unverified/possibly obsolete until resolved.

---

## 9. Open flags (contradictions / gaps / obsolete facts)

_Populated by `ContextAgent.run_audit()`._

{OPEN_FLAGS_MARKER}
{NONE_OPEN}

---

## 10. Analytical findings

_Populated by `AnalyticsAgent` after each analysis run -- actionable insights found
in the data, not facts about the schema itself. These are observations as of when
they were written, not permanent truths; they can go stale as new data lands, so
weigh them against Section 8's freshness check same as anything else here._

{FINDINGS_MARKER}
{NONE_YET}
"""


def build_seed_content() -> str:
    """The full Markdown document for version 1: base_context.md verbatim,
    plus the operational sections above appended to the end."""
    base = _BASE_CONTEXT_PATH.read_text().rstrip()
    return base + "\n" + _operational_sections()


if __name__ == "__main__":
    print(build_seed_content())
