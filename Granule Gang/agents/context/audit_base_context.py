"""
Audit checks for the business-context document (analytics_context.business_context).

Two independent passes, both feeding ContextAgent.run_audit():
1. freshness_check() -- deterministic, no LLM. Does every table
   InstrumentationAgent has ever registered still actually exist? This is the
   literal "is the business context obsolete" check the document's own
   Section 9 (Data freshness check) tells the reader to run.
2. An LLM pass over the full document text, for contradictions/ambiguity/
   staleness it can support from the text alone (things the deterministic
   check above can't catch, e.g. two metrics defined two conflicting ways).
"""

import json
import re

AUDIT_PROMPT = """You are auditing a business-context Markdown document for an analytics
system (a visa-application funnel product). Read the document below and identify ONLY
NEW issues you can support from the text itself -- do not repeat anything already listed
under "ALREADY-FLAGGED ISSUES" below, even if you would phrase or key it differently:
- contradiction        (two statements conflict, e.g. the same metric defined two ways)
- stale_metric         (a definition or fact that reads as outdated or superseded)
- missing_relationship (a table/column implies a join or entity link never stated)
- ambiguous_definition (a term used but never concretely defined)

Respond with ONLY a JSON array of objects with keys: flag_type, entity, key, description.
entity/key should name the specific table/metric/section the issue is about (e.g.
entity="metric.conversion_rate", key="session_undefined"). No prose, no markdown fences.
If there are no NEW issues, respond with an empty JSON array: []

ALREADY-FLAGGED ISSUES (do not repeat these, in any rephrasing):
{existing_flags}

DOCUMENT:
{document}
"""


def freshness_check(client) -> list[dict]:
    """Does every table InstrumentationAgent has registered still actually
    exist in atlys? A meta_context_registry entry with no matching live table
    means the business context could be describing something that's gone --
    exactly the staleness Section 9 of the document asks the reader to verify."""
    try:
        registered = client.query(
            "SELECT DISTINCT entity_name FROM atlys.meta_context_registry "
            "WHERE is_current = 1 AND entity_type = 'table'"
        )
        existing = client.query("SELECT name FROM system.tables WHERE database = 'atlys'")
    except Exception as e:
        print(f"Warning: freshness_check could not read schema metadata, skipping: {e}")
        return []

    registered_names = {r[0] for r in registered.result_rows}
    existing_names = {r[0] for r in existing.result_rows}
    missing = registered_names - existing_names

    return [
        {
            "flag_type": "stale_metric",
            "entity": name,
            "key": "table_existence",
            "description": (
                f"Table `{name}` is registered in meta_context_registry but no longer "
                f"exists in atlys -- any business context describing it is obsolete."
            ),
        }
        for name in sorted(missing)
    ]


def parse_llm_json(raw_text: str):
    """Safely extracts JSON even if the LLM wraps it in markdown blocks or extra whitespace."""
    cleaned = raw_text.strip()
    match = re.search(r'(\{.*\}|\[.*\])', cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(cleaned)
