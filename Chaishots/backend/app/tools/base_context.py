"""Parse the hand-maintained base context layer into a seed context document.

The challenge ships `base_context.md` as the starting semantic layer: business
entities, metric formulas, a join map, and a known-issues log. It is explicitly
described as imperfect, so it is parsed into the same typed shape the Context
Agent writes and stored as context version 1. Everything downstream then reads
one accumulated document rather than special-casing "base" versus "learned".

Parsing is deliberately structural rather than semantic: headings select a
section and only well-formed rows inside it are kept. A malformed section
yields no rows instead of raising, because a partly-parsed base layer is far
more useful to the agents than a pipeline that refuses to start.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import JsonValue

from app.schemas.features import ContextDocument

BASE_CONTEXT_PATH = (
    Path(__file__).resolve().parent.parent / "context" / "base_context.md"
)
BASE_CONTEXT_SOURCE = "base_context.md"
BASE_CONTEXT_VERSION = 1

_SECTION = re.compile(r"^##\s+\d*\.?\s*(?P<title>.+?)\s*$", re.MULTILINE)
_BOLD_TERM = re.compile(r"^\*\*(?P<name>[^*]+?)\*\*\s*(?:—|--|-)\s*(?P<body>.+)$")
_METRIC_TERM = re.compile(
    r"^\*\*(?P<name>[^*]+?)\*\*\s*(?:\((?P<qualifier>[^)]*)\))?\s*=\s*(?P<formula>.+)$"
)
_KNOWN_ISSUE = re.compile(
    r"^\d+\.\s+\*\*(?P<key>K\d+)\s*(?:—|--|-)\s*(?P<title>[^*]+?)\*\*\s*(?P<body>.*)$"
)
_TABLE_ROW = re.compile(r"^\|(?!\s*[-:| ]+\|)\s*(?P<cells>.+)\|\s*$")
_JOIN_LINE = re.compile(
    r"`(?P<source>[A-Za-z_][A-Za-z0-9_]*)\.(?P<source_column>[A-Za-z_][A-Za-z0-9_]*)`"
    r"\s*(?:→|->)\s*(?P<rest>.+)"
)
_BACKTICKED = re.compile(r"`([^`]+)`")


def _sections(text: str) -> dict[str, str]:
    """Split the document into `## <title>` bodies, keyed by lowercased title."""

    sections: dict[str, str] = {}
    matches = list(_SECTION.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = match.group("title").strip().casefold()
        sections[title] = text[match.end() : end]
    return sections


def _find_section(sections: dict[str, str], *keywords: str) -> str:
    for title, body in sections.items():
        if all(keyword in title for keyword in keywords):
            return body
    return ""


def _clean(value: str) -> str:
    """Strip markdown emphasis and backticks from prose kept as a description."""

    without_code = _BACKTICKED.sub(r"\1", value)
    return without_code.replace("**", "").strip().rstrip(".")


def _parse_entities(body: str) -> list[dict[str, JsonValue]]:
    entities: list[dict[str, JsonValue]] = []
    for block in re.split(r"\n\s*\n", body):
        collapsed = " ".join(line.strip() for line in block.strip().splitlines())
        match = _BOLD_TERM.match(collapsed)
        if match is None:
            continue
        name = match.group("name").strip()
        description = _clean(match.group("body"))
        # The identifying column is written inline as `user_id` / `application_id`.
        identifiers = _BACKTICKED.findall(block)
        primary_key = next(
            (token for token in identifiers if token.endswith("_id")),
            "",
        )
        entities.append(
            {
                "name": name,
                "primary_key": primary_key,
                "description": description,
                "source": BASE_CONTEXT_SOURCE,
            }
        )
    return entities


def _parse_metrics(body: str) -> list[dict[str, JsonValue]]:
    metrics: list[dict[str, JsonValue]] = []
    for block in re.split(r"\n\s*\n", body):
        stripped = block.strip()
        if stripped.startswith(">"):
            # Trailing blockquote notes are captured as conflicts, not metrics.
            continue
        collapsed = " ".join(line.strip() for line in stripped.splitlines())
        match = _METRIC_TERM.match(collapsed)
        if match is None:
            continue
        name = match.group("name").strip()
        formula = _clean(match.group("formula"))
        qualifier = (match.group("qualifier") or "").strip()
        metrics.append(
            {
                "name": name,
                "description": f"{name} ({qualifier})" if qualifier else name,
                "formula": formula,
                "source": BASE_CONTEXT_SOURCE,
            }
        )
    return metrics


def _parse_known_issues(body: str) -> list[dict[str, JsonValue]]:
    issues: list[dict[str, JsonValue]] = []
    for block in re.split(r"\n(?=\d+\.\s)", body):
        collapsed = " ".join(line.strip() for line in block.strip().splitlines())
        match = _KNOWN_ISSUE.match(collapsed)
        if match is None:
            continue
        issues.append(
            {
                "key": match.group("key"),
                "title": _clean(match.group("title")),
                "description": _clean(match.group("body")),
                "source": BASE_CONTEXT_SOURCE,
            }
        )
    return issues


def _parse_tables(body: str) -> list[dict[str, JsonValue]]:
    """Read the eight-table inventory so entities cover existing warehouse tables."""

    entities: list[dict[str, JsonValue]] = []
    for line in body.splitlines():
        match = _TABLE_ROW.match(line.strip())
        if match is None:
            continue
        cells = [cell.strip() for cell in match.group("cells").split("|")]
        if len(cells) < 4:
            continue
        table_names = _BACKTICKED.findall(cells[0])
        if not table_names:
            continue
        table = table_names[0]
        if table.casefold() == "table":
            continue
        entities.append(
            {
                "name": table,
                "table_name": table,
                "kind": _clean(cells[1]),
                "description": f"Emitted when {_clean(cells[2])}",
                "dimensions": _BACKTICKED.findall(cells[3]),
                "source": BASE_CONTEXT_SOURCE,
            }
        )
    return entities


def _parse_relationships(
    body: str, *, known_tables: frozenset[str]
) -> list[dict[str, JsonValue]]:
    """Read the join map, resolving each bullet against the known table list.

    Bullets wrap across lines and name targets either explicitly or as the
    catch-all "all tables", so entries are collapsed first and every backticked
    token is matched against tables the inventory actually declared.
    """

    relationships: list[dict[str, JsonValue]] = []
    seen: set[tuple[str, str, str, str]] = set()
    # Bullets continue onto indented lines; join each one before matching.
    for bullet in re.split(r"\n(?=\s*-\s)", body):
        line = " ".join(part.strip() for part in bullet.strip().splitlines())
        line = line.lstrip("-").strip()
        match = _JOIN_LINE.search(line)
        if match is None:
            continue
        source = match.group("source")
        source_column = match.group("source_column")
        rest = match.group("rest")
        tokens = _BACKTICKED.findall(rest)
        # "(on `application_id`)" names the join column; otherwise it is shared.
        target_column = next(
            (token for token in tokens if token == source_column), source_column
        )
        targets = [token for token in tokens if token in known_tables]
        if not targets and re.search(r"\ball tables\b", rest, re.IGNORECASE):
            targets = sorted(known_tables - {source})
        for target in targets:
            identity = (source, source_column, target, target_column)
            if target == source or identity in seen:
                continue
            seen.add(identity)
            relationships.append(
                {
                    "source_table": source,
                    "source_column": source_column,
                    "target_table": target,
                    "target_column": target_column,
                    "reason": _clean(line),
                    "source": BASE_CONTEXT_SOURCE,
                }
            )
    return relationships


def _parse_conventions(body: str) -> list[str]:
    conventions: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("-") and len(line) > 3:
            conventions.append(_clean(line.lstrip("-").strip()))
    return conventions


def _parse_stated_caveats(sections: dict[str, str]) -> list[str]:
    """Collect the document's own hedges so the Context Agent starts suspicious.

    Only blockquotes inside numbered sections are kept: the file's opening
    blockquote is a preamble describing the document itself, not a claim about
    the data. Consecutive quoted lines form one caveat.
    """

    caveats: list[str] = []
    for body in sections.values():
        block: list[str] = []
        for raw_line in [*body.splitlines(), ""]:
            line = raw_line.strip()
            if line.startswith(">"):
                block.append(line.lstrip(">").strip())
                continue
            if block:
                caveat = _clean(" ".join(part for part in block if part))
                if caveat:
                    caveats.append(caveat)
                block = []
    return caveats


def parse_base_context(
    markdown: str,
    *,
    version: int = BASE_CONTEXT_VERSION,
) -> ContextDocument:
    """Turn the base context markdown into the seed context document."""

    sections = _sections(markdown)
    entities = _parse_entities(_find_section(sections, "entity", "definition"))
    table_entities = _parse_tables(_find_section(sections, "raw event tables"))
    entities.extend(table_entities)
    known_tables = frozenset(
        str(entity["table_name"])
        for entity in table_entities
        if entity.get("table_name")
    )
    metrics = _parse_metrics(_find_section(sections, "metric", "definition"))
    known_issues = _parse_known_issues(_find_section(sections, "known-issues"))
    relationships = _parse_relationships(
        _find_section(sections, "entity relationships"), known_tables=known_tables
    )
    conventions = _parse_conventions(_find_section(sections, "how to analyse"))

    conflicts: list[JsonValue] = [
        f"UNVERIFIED (base_context.md): {caveat}"
        for caveat in _parse_stated_caveats(sections)
    ]
    return ContextDocument(
        version=version,
        run_id=None,
        entities=entities,
        relationships=relationships,
        metrics=metrics,
        known_issues=known_issues,
        naming_conventions=conventions,
        conflicts=conflicts,
        source=BASE_CONTEXT_SOURCE,
    )


def load_base_context(
    path: Path | None = None,
    *,
    version: int = BASE_CONTEXT_VERSION,
) -> ContextDocument | None:
    """Read and parse the vendored base context, or None when it is absent."""

    source = path or BASE_CONTEXT_PATH
    try:
        markdown = source.read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_base_context(markdown, version=version)


__all__ = [
    "BASE_CONTEXT_PATH",
    "BASE_CONTEXT_SOURCE",
    "BASE_CONTEXT_VERSION",
    "load_base_context",
    "parse_base_context",
]
