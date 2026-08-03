from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[2]
VAULT_ROOT = REPO_ROOT / "docs"
MANAGED_FOLDERS = {
    "00_Index",
    "01_Overview",
    "02_Architecture",
    "03_Domains",
    "04_Components",
    "05_APIs",
    "06_Data",
    "07_Workflows",
    "08_Operations",
    "09_Decisions",
    "10_Runbooks",
    "11_Onboarding",
    "12_Glossary",
    "13_References",
    "14_Change",
    "adr",
}
REQUIRED_FIELDS = {
    "id",
    "title",
    "type",
    "status",
    "owner",
    "source",
    "created",
    "updated",
    "reviewed",
    "confidence",
    "tags",
}
ALLOWED_TYPES = {
    "moc",
    "overview",
    "architecture",
    "domain",
    "component",
    "api",
    "data-model",
    "workflow",
    "adr",
    "runbook",
    "incident",
    "release",
    "onboarding",
    "glossary",
    "investigation",
    "open-question",
    "reference",
}
ALLOWED_STATUSES = {"draft", "active", "deprecated", "archived"}
ALLOWED_CONFIDENCE = {"verified", "mixed", "inferred"}
ALLOWED_IMPLEMENTATION = {"current", "planned", "unknown"}
ALLOWED_PRIORITIES = {"critical", "high", "normal", "low"}
ALLOWED_SOURCES = {
    "repository",
    "context-map",
    "decision",
    "governance",
    "operations",
    "release",
    "research",
}
ID_PREFIXES = {
    "moc": "moc-",
    "overview": "overview-",
    "architecture": "arch-",
    "domain": "domain-",
    "component": "component-",
    "api": "api-",
    "data-model": "data-",
    "workflow": "workflow-",
    "adr": "adr-",
    "runbook": "runbook-",
    "incident": "incident-",
    "release": "release-",
    "onboarding": "onboarding-",
    "glossary": "glossary-",
    "investigation": "investigation-",
    "open-question": "question-",
    "reference": "reference-",
}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WIKILINK_PATTERN = re.compile(r"\[\[([^|\]#]+)(?:#[^|\]]*)?(?:\|[^\]]*)?\]\]")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def managed_notes() -> list[Path]:
    return sorted(
        path
        for path in VAULT_ROOT.rglob("*.md")
        if path.relative_to(VAULT_ROOT).parts[0] in MANAGED_FOLDERS
    )


def parse_frontmatter(path: Path) -> tuple[dict[str, str | list[str]], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, text

    metadata: dict[str, str | list[str]] = {}
    current_list: str | None = None
    for line in lines[1:end]:
        if line.startswith("  - ") and current_list:
            value = line[4:].strip().strip("\"'")
            existing = metadata.setdefault(current_list, [])
            assert isinstance(existing, list)
            existing.append(value)
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip().strip("\"'")
        if value == "":
            metadata[key] = []
            current_list = key
        elif value.startswith("[") and value.endswith("]"):
            metadata[key] = [
                item.strip().strip("\"'")
                for item in value[1:-1].split(",")
                if item.strip()
            ]
            current_list = None
        else:
            metadata[key] = value
            current_list = None
    return metadata, "\n".join(lines[end + 1 :])


def values(metadata: dict[str, str | list[str]], key: str) -> list[str]:
    value = metadata.get(key, [])
    return value if isinstance(value, list) else [value]


def resolve_wikilink(
    source: Path,
    target: str,
    by_stem: dict[str, list[Path]],
    by_relative: dict[str, Path],
) -> Path | None:
    normalized = target.strip().removesuffix(".md")
    direct = by_relative.get(normalized)
    if direct:
        return direct
    relative = (source.parent / normalized).resolve()
    try:
        relative_key = relative.relative_to(VAULT_ROOT.resolve()).as_posix()
    except ValueError:
        relative_key = ""
    if relative_key in by_relative:
        return by_relative[relative_key]
    matches = by_stem.get(Path(normalized).name, [])
    return matches[0] if len(matches) == 1 else None


def main() -> int:
    notes = managed_notes()
    all_markdown = sorted(VAULT_ROOT.rglob("*.md"))
    by_stem: dict[str, list[Path]] = defaultdict(list)
    by_relative: dict[str, Path] = {}
    for path in all_markdown:
        by_stem[path.stem].append(path)
        relative = path.relative_to(VAULT_ROOT).with_suffix("").as_posix()
        by_relative[relative] = path

    errors: list[str] = []
    ids: Counter[str] = Counter()
    incoming: Counter[Path] = Counter()
    active_notes: set[Path] = set()

    for path in notes:
        metadata, body = parse_frontmatter(path)
        relative = path.relative_to(REPO_ROOT)
        missing = REQUIRED_FIELDS - metadata.keys()
        if missing:
            errors.append(f"{relative}: missing frontmatter: {', '.join(sorted(missing))}")
            continue

        note_id = str(metadata["id"])
        ids[note_id] += 1
        note_type = str(metadata["type"])
        status = str(metadata["status"])
        confidence = str(metadata["confidence"])
        if note_type not in ALLOWED_TYPES:
            errors.append(f"{relative}: unsupported type {note_type!r}")
        elif not note_id.startswith(ID_PREFIXES[note_type]):
            errors.append(
                f"{relative}: id must start with {ID_PREFIXES[note_type]!r}"
            )
        if status not in ALLOWED_STATUSES:
            errors.append(f"{relative}: unsupported status {status!r}")
        if confidence not in ALLOWED_CONFIDENCE:
            errors.append(f"{relative}: unsupported confidence {confidence!r}")
        if metadata["source"] not in ALLOWED_SOURCES:
            errors.append(f"{relative}: unsupported source {metadata['source']!r}")
        if metadata["owner"] != "unassigned":
            errors.append(
                f"{relative}: owner must remain 'unassigned' until an ownership registry exists"
            )
        for field in ("created", "updated", "reviewed"):
            if not DATE_PATTERN.fullmatch(str(metadata[field])):
                errors.append(f"{relative}: {field} must use YYYY-MM-DD")
        implementation = metadata.get("implementation")
        if implementation and implementation not in ALLOWED_IMPLEMENTATION:
            errors.append(f"{relative}: unsupported implementation {implementation!r}")
        priority = metadata.get("priority")
        if priority and priority not in ALLOWED_PRIORITIES:
            errors.append(f"{relative}: unsupported priority {priority!r}")
        if status == "active":
            active_notes.add(path)
        if not values(metadata, "tags"):
            errors.append(f"{relative}: tags must not be empty")
        for field in ("repo_path", "code_refs"):
            for reference in values(metadata, field):
                target = reference.split("#", 1)[0]
                if target and not (REPO_ROOT / target).exists():
                    errors.append(f"{relative}: missing {field} target {reference!r}")

        text_to_check = body + "\n" + "\n".join(values(metadata, "related"))
        text_to_check += "\n" + "\n".join(values(metadata, "depends_on"))
        for target in WIKILINK_PATTERN.findall(text_to_check):
            resolved = resolve_wikilink(path, target, by_stem, by_relative)
            if resolved is None:
                errors.append(f"{relative}: unresolved or ambiguous wikilink [[{target}]]")
            else:
                incoming[resolved] += 1
        for raw_target in MARKDOWN_LINK_PATTERN.findall(body):
            target = unquote(raw_target.split("#", 1)[0])
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"{relative}: missing local Markdown link {raw_target!r}")

    for note_id, count in ids.items():
        if count > 1:
            errors.append(f"duplicate note id {note_id!r} appears {count} times")

    root_index = VAULT_ROOT / "00_Index" / "ZentraOS Knowledge Base.md"
    for path in sorted(active_notes):
        if path != root_index and incoming[path] == 0:
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: active note has no incoming wikilink"
            )

    decisions_moc = VAULT_ROOT / "09_Decisions" / "Decisions MOC.md"
    decision_text = (
        decisions_moc.read_text(encoding="utf-8") if decisions_moc.exists() else ""
    )
    for adr in sorted((VAULT_ROOT / "adr").glob("*.md")):
        if f"[[adr/{adr.stem}" not in decision_text:
            errors.append(f"docs/09_Decisions/Decisions MOC.md: does not index {adr.name}")

    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Documentation validation passed: {len(notes)} governed notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
