"""Load the vendored ClickHouse best-practice rules into agent prompts.

The agent cites rule ids in its decisions, so it should reason from the rule
*text*, not from a paraphrase that has drifted. Anything in `rules/` is appended
to the system prompt verbatim - adding a rule file is all it takes for the agent
to start applying and citing it.
"""

from __future__ import annotations

import pathlib

RULES_DIR = pathlib.Path(__file__).parent / "rules"


# Which rules each agent needs. Loading all 33 into every prompt wastes tokens
# and buries the relevant ones - the Instrumentation Agent has no use for join
# algorithms, and the Analytics Agent none for partition lifecycle.
INSTRUMENTATION_PREFIXES = ("schema-", "query-mv-", "query-index-")
ANALYTICS_PREFIXES = ("query-join-", "query-index-", "agent-")


def rules_for(*prefixes: str) -> list[str]:
    """Vendored rule ids matching any prefix, sorted."""
    return [r for r in rule_ids() if r.startswith(prefixes)]


# SKILL.md's priority matrix. Rules are loaded in this order, not
# alphabetically: it tells the model which to weigh first when two pull in
# different directions, and puts the CRITICAL ones nearest the task.
PRIORITY = (
    "schema-pk-",
    "schema-types-",
    "query-join-",
    "insert-batch-",
    "insert-mutation-",
    "agent-discovery-",
    "agent-query-",
    "schema-partition-",
    "query-index-",
    "query-mv-",
    "insert-async-",
    "insert-optimize-",
    "agent-connect-",
    "schema-json-",
)

# Documentation, not rules.
NOT_RULES = ("README", "SKILL", "_sections", "_template")


def _priority(rule_id: str) -> tuple[int, str]:
    for index, prefix in enumerate(PRIORITY):
        if rule_id.startswith(prefix):
            return (index, rule_id)
    return (len(PRIORITY), rule_id)


def rule_ids() -> list[str]:
    """Every vendored rule id, in the official priority order."""
    found = [p.stem for p in RULES_DIR.glob("*.md") if p.stem not in NOT_RULES]
    return sorted(found, key=_priority)


def skill_guidance() -> str:
    """SKILL.md's `How to apply` section - the convention for citing rules."""
    path = RULES_DIR / "SKILL.md"
    return path.read_text().strip() if path.exists() else ""


def load_rules(*ids: str) -> str:
    """Concatenate rule text, each under a citable `## <id>` heading.

    With no ids, loads every vendored rule. Unknown ids are skipped rather than
    raising: a missing rule should degrade the prompt, not kill the run.
    """
    wanted = list(ids) or rule_ids()
    wanted = sorted(wanted, key=_priority)
    blocks: list[str] = []

    for rule_id in wanted:
        path = RULES_DIR / f"{rule_id}.md"
        if not path.exists():
            continue
        blocks.append(f"## {rule_id}\n\n{path.read_text().strip()}")

    if not blocks:
        return ""

    return (
        "# ClickHouse best-practice rules (verbatim)\n\n"
        "Source: github.com/ClickHouse/agent-skills. Cite the rule id shown in "
        "each heading. Where a rule applies, it overrides your general "
        "knowledge.\n\n" + "\n\n---\n\n".join(blocks)
    )
