"""Skill loading, reimplemented as system-prompt injection instead of LibreChat's
server-side skill tool (which we no longer go through). LibreChat exposed skills
as a `skill` tool call whose arguments/output were both unrecoverable anyway
(same empty-arguments gap as every other tool call) -- so this isn't a downgrade,
it's the same content delivered a more direct way, plus we get real visibility
into what gets read (an actual `read_skill_file` tool call, with real arguments).

Each SKILL.md (a few KB) is small enough to inline directly into the system
prompt -- no discovery round-trip needed. clickhouse-best-practices' `rules/`
subdirectory (144KB across 33 files) is NOT inlined; the prompt already tells
proposer/reviewer to read specific rule files by name (e.g.
`rules/schema-types-avoid-nullable.md`), so we expose a `read_skill_file` tool
for that instead of paying for all 33 files on every call.
"""
from __future__ import annotations

import pathlib

_SKILL_ROOT = pathlib.Path("/Users/anshmehta/Downloads/Clickhouse Hackathon/LibreChat/skill")

# Which skills each agent gets -- unlike LibreChat's all-or-nothing
# skills_enabled toggle, we control this precisely per agent now.
SKILLS_BY_AGENT = {
    "instrumentation_proposer": ["clickhouse-best-practices", "context-engine"],
    "context_reviewer": ["clickhouse-best-practices"],
    "context_chronicler": ["context-engine", "context-update"],
    "analytics_agent": ["context-engine"],
}

LIST_SKILL_FILES_TOOL = {
    "type": "function",
    "name": "list_skill_files",
    "description": (
        "Lists every file available under one of your loaded skills, e.g. "
        "'clickhouse-best-practices'. Call this BEFORE read_skill_file if you're "
        "not certain of an exact filename -- guessing rule filenames wastes "
        "calls on files that don't exist."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "One of your loaded skill names, e.g. 'clickhouse-best-practices'",
            }
        },
        "required": ["skill_name"],
    },
}

READ_SKILL_FILE_TOOL = {
    "type": "function",
    "name": "read_skill_file",
    "description": (
        "Reads a specific file from one of your loaded skills' directories, e.g. "
        "'clickhouse-best-practices/rules/schema-types-avoid-nullable.md'. Use "
        "this for the specific rule files your instructions reference by name -- "
        "the skill's own SKILL.md is already in your system prompt, you don't "
        "need to re-read that."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the skill root, e.g. 'clickhouse-best-practices/rules/schema-pk-cardinality-order.md'",
            }
        },
        "required": ["path"],
    },
}


def inline_skill_content(agent_key: str) -> str:
    """Returns the concatenated SKILL.md content for every skill this agent has,
    formatted for direct inclusion in the system prompt."""
    names = SKILLS_BY_AGENT.get(agent_key, [])
    if not names:
        return ""
    blocks = []
    for name in names:
        skill_md = _SKILL_ROOT / name / "SKILL.md"
        if skill_md.exists():
            blocks.append(f"--- SKILL: {name} ---\n{skill_md.read_text()}")
    return "\n\n".join(blocks)


def list_skill_files(skill_name: str) -> str:
    """Executes a list_skill_files tool call -- every file under a skill's
    directory, relative paths, so the result can be fed straight into
    read_skill_file without the model having to guess names."""
    skill_dir = (_SKILL_ROOT / skill_name).resolve()
    if not skill_dir.is_relative_to(_SKILL_ROOT.resolve()) or not skill_dir.is_dir():
        return f"ERROR: no such skill: {skill_name}"
    # Prefixed with skill_name so the result can be passed straight into
    # read_skill_file's `path` argument, which is relative to the skill ROOT
    # (all skills' parent dir), not to this one skill's own directory.
    files = sorted(
        f"{skill_name}/{p.relative_to(skill_dir)}" for p in skill_dir.rglob("*") if p.is_file()
    )
    return "\n".join(files)


def read_skill_file(path: str) -> str:
    """Executes a read_skill_file tool call. Path traversal outside the skill
    root is rejected -- same guard pattern as mcp_servers/data_tools_server.py's
    scratch-file tools."""
    target = (_SKILL_ROOT / path).resolve()
    if not target.is_relative_to(_SKILL_ROOT.resolve()):
        return f"ERROR: path escapes the skill directory: {path}"
    if not target.exists():
        return f"ERROR: no such file: {path}"
    return target.read_text()
