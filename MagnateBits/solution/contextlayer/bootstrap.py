"""base_context.md -> ContextEntry rows. Deterministic markdown parsing, no LLM.

Why no LLM here: the context layer is the thing every other agent is judged against.
A parser that occasionally paraphrases a metric definition would make contradiction
detection non-reproducible -- we would be diffing model noise, not documentation drift.
This parser is a pure function of the markdown, so `bootstrap()` is idempotent and the
version number only moves when the *document* moves.

The parser is structural, not document-specific. It reads:

    ## <heading>                 -> a section, classified into a ContextKind by keyword
    **Term** — definition        -> one entry, key=Term
    **Term** = formula           -> one entry, key=Term, formula captured separately
    | markdown | table |         -> one entry per row, keyed on the first column
    1. **K1 — title.** body      -> one entry per list item, keyed on the leading code
    - bullet                     -> one entry per bullet
    > blockquote                 -> a note; if it restates a metric it becomes its own
                                    metric entry so the two definitions can be compared
    ```fenced```                 -> a diagram entry

Nothing below mentions any feature, metric or table by name.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

# Words that never carry meaning in a slug or a term lookup.
STOPWORDS = frozenset(
    """
a an the and or of to in on for from by with within at as is are was were be been being
this that these those it its their our we us you your they them he she his her not no
per each every all any some other others than then so if when while which who whom whose
one two three four five up down out over under again further more most such only own same
very can will just should now do does did doing have has had having but because until
about into through during before after above below between both few nor too also may might
""".split()
)

# Suffix words that describe the *shape* of a metric rather than its subject. Stripping
# them is what lets "Conversion rate" and "conversion" land in the same cluster.
METRIC_SHAPE_WORDS = frozenset(
    "rate ratio pct percent percentage share fraction index score count number avg average"
    " median total sum value amount".split()
)

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_BOLD_LEAD_RE = re.compile(r"^\*\*(?P<term>[^*]+?)\s*:?\*\*\s*:?\s*(?P<sep>[—–\-=])?\s*(?P<rest>.*)$")
_BOLD_SPAN_RE = re.compile(r"\*\*([^*]+)\*\*")
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")
DIVIDERS = ("÷", "/")


# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------


def strip_markup(text: str) -> str:
    """Drop backticks and bold/italic asterisks. Underscores are load-bearing: they are
    inside every column name in this schema, so they are never stripped."""
    return re.sub(r"[`*]", "", text).strip()


def slug(text: str, drop_parens: bool = True) -> str:
    if drop_parens:
        text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[`*]", "", text).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:60]


def slug_words(text: str, n: int = 4) -> str:
    words = [w for w in re.split(r"[^a-z0-9]+", strip_markup(text).lower()) if w]
    keep = [w for w in words if w not in STOPWORDS][:n] or words[:n]
    return "_".join(keep)[:60] or "entry"


def normalize_term(term: str) -> str:
    """Lowercase, de-marked, crudely singularised."""
    t = strip_markup(term).lower().strip(" .,:;()")
    t = re.sub(r"\s+", " ", t)
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("sses") or t.endswith("shes") or t.endswith("ches"):
        return t[:-2]
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def metric_subject(key: str) -> frozenset[str]:
    """Token-set identity of a metric, ignoring shape words. Used to cluster definitions."""
    words = [w for w in re.split(r"[^a-z0-9]+", slug(key).replace("_", " ")) if w]
    core = [normalize_term(w) for w in words if w not in STOPWORDS and w not in METRIC_SHAPE_WORDS]
    return frozenset(core or [normalize_term(w) for w in words])


def split_formula(formula: str) -> tuple[str, str] | None:
    """Split a formula on the first division operator -> (numerator, denominator)."""
    for div in DIVIDERS:
        if div in formula:
            left, _, right = formula.partition(div)
            if left.strip() and right.strip():
                return left.strip(), right.strip()
    return None


def code_identifiers(text: str) -> list[str]:
    """Identifiers appearing inside `backticks`, including dotted table.column forms."""
    out: list[str] = []
    for span in _CODE_SPAN_RE.findall(text):
        for tok in re.split(r"[^A-Za-z0-9_.]+", span):
            tok = tok.strip(".")
            if not tok:
                continue
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*", tok):
                out.append(tok)
    return out


def bold_terms(text: str, exclude: str = "", max_words: int = 3) -> list[str]:
    """Bolded phrases inside a body, minus the leading key and trivia.

    A bolded phrase is treated as a *reference to another definition*, so it must look
    like a term (<= max_words words). Longer bold spans are restatements of the whole
    definition, not term references.
    """
    ex = normalize_term(exclude)
    out = []
    for raw in _BOLD_SPAN_RE.findall(text):
        term = strip_markup(raw)
        if not term or normalize_term(term) == ex:
            continue
        if len(term.split()) > max_words:
            continue
        out.append(term)
    return out


# --------------------------------------------------------------------------
# block parsing
# --------------------------------------------------------------------------


def _split_sections(md: str) -> list[tuple[str, str]]:
    matches = list(_SECTION_RE.finditer(md))
    sections: list[tuple[str, str]] = []
    if not matches:
        return [("", md)]
    preamble = md[: matches[0].start()]
    # drop the H1
    preamble = re.sub(r"^#\s+.*$", "", preamble, count=1, flags=re.M)
    if preamble.strip():
        sections.append(("", preamble))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        sections.append((m.group(1).strip(), md[m.end() : end]))
    return sections


def _blocks(body: str) -> list[tuple[str, Any]]:
    lines = body.split("\n")
    blocks: list[tuple[str, Any]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            j = i + 1
            while j < n and not lines[j].strip().startswith("```"):
                j += 1
            blocks.append(("code", "\n".join(lines[i + 1 : j]).strip()))
            i = j + 1
        elif s.startswith("|"):
            j = i
            while j < n and lines[j].strip().startswith("|"):
                j += 1
            blocks.append(("table", lines[i:j]))
            i = j
        elif s.startswith(">"):
            j = i
            parts = []
            while j < n and lines[j].strip().startswith(">"):
                parts.append(lines[j].strip().lstrip(">").strip())
                j += 1
            blocks.append(("quote", " ".join(p for p in parts if p)))
            i = j
        elif _LIST_ITEM_RE.match(line):
            items: list[str] = []
            cur: str | None = None
            j = i
            while j < n:
                l = lines[j]
                if _LIST_ITEM_RE.match(l):
                    if cur is not None:
                        items.append(cur)
                    cur = _LIST_ITEM_RE.sub("", l).strip()
                elif not l.strip():
                    nxt = lines[j + 1] if j + 1 < n else ""
                    if not _LIST_ITEM_RE.match(nxt):
                        break
                elif cur is not None and l.startswith((" ", "\t")):
                    cur += " " + l.strip()
                else:
                    break
                j += 1
            if cur is not None:
                items.append(cur)
            blocks.append(("list", items))
            i = j
        elif not s or s.startswith("---"):
            i += 1
        else:
            j = i
            para: list[str] = []
            while j < n:
                l = lines[j]
                if not l.strip() or l.strip().startswith(("|", ">", "```", "---")):
                    break
                if _LIST_ITEM_RE.match(l) and j > i:
                    break
                para.append(l.strip())
                j += 1
            blocks.append(("para", " ".join(para)))
            i = max(j, i + 1)
    return blocks


SECTION_KIND_RULES: list[tuple[tuple[str, ...], str]] = [
    (("known", "issue"), "known_issue"),
    (("relationship",), "relationship"),
    (("join",), "relationship"),
    (("metric",), "metric"),
    (("table",), "table_doc"),
    (("entity",), "entity"),
    (("glossary",), "entity"),
    (("definition",), "entity"),
]


def classify_section(heading: str) -> str:
    h = heading.lower()
    for tokens, kind in SECTION_KIND_RULES:
        if all(t in h for t in tokens):
            return kind
    return "business_def"


def _prefix_for(kind: str) -> str:
    """Prose entries keep their kind as the id prefix. Only real rows of a markdown table
    of tables get the short `table.<name>` id (see _emit_table_block)."""
    return kind


_MARKUP_ONLY = re.compile(r"^\s*</?[A-Za-z][A-Za-z0-9_-]*\s*/?>\s*$")


# --------------------------------------------------------------------------
# entry construction
# --------------------------------------------------------------------------


def _refs(text: str, known_tables: set[str], known_columns: set[str]) -> list[str]:
    out: set[str] = set()
    for tok in code_identifiers(text):
        head, _, tail = tok.partition(".")
        if head in known_tables:
            out.add(head)
            if tail:
                out.add(tok)
        elif tok in known_columns:
            out.add(tok)
        elif "_" in tok and tok.islower():
            out.add(tok)
    # bare (unbackticked) table names mentioned in prose still count as references
    for tok in _IDENT_RE.findall(text):
        if tok in known_tables:
            out.add(tok)
    return sorted(out)


class _Builder:
    def __init__(self, source_ref: str, known_tables: set[str], known_columns: set[str]) -> None:
        self.source_ref = source_ref
        self.known_tables = known_tables
        self.known_columns = known_columns
        self.entries: list[dict[str, Any]] = []
        self._used: set[str] = set()

    def _unique(self, entry_id: str) -> str:
        if entry_id not in self._used:
            self._used.add(entry_id)
            return entry_id
        i = 2
        while f"{entry_id}_{i}" in self._used:
            i += 1
        self._used.add(f"{entry_id}_{i}")
        return f"{entry_id}_{i}"

    def add(
        self,
        kind: str,
        entry_id: str,
        key: str,
        body: str,
        formula: str = "",
        section: str = "",
        extra_refs: Sequence[str] = (),
    ) -> dict[str, Any]:
        refs = set(_refs(f"{key} {body} {formula}", self.known_tables, self.known_columns))
        refs.update(extra_refs)
        entry = {
            "entry_id": self._unique(entry_id),
            "kind": kind,
            "key": key.strip(),
            "body": " ".join(body.split()),
            "formula": " ".join(formula.split()),
            "refs": sorted(refs),
            "source": "base_context.md",
            "source_ref": f"{self.source_ref}#{section}" if section else self.source_ref,
            "status": "active",
            "confidence": 1.0,
        }
        self.entries.append(entry)
        return entry


def parse_base_context(
    md: str,
    known_tables: Iterable[str] = (),
    known_columns: Iterable[str] = (),
    source_ref: str = "base_context.md",
) -> list[dict[str, Any]]:
    """Parse the base context markdown into ContextEntry-shaped dicts."""
    tables = set(known_tables)
    columns = set(known_columns)

    # First pass: any markdown table whose first column is a code-spanned identifier
    # contributes table names, so prose in the same document can reference them.
    for heading, body in _split_sections(md):
        for btype, payload in _blocks(body):
            if btype == "table":
                for name in _table_first_column(payload):
                    tables.add(name)

    b = _Builder(source_ref, tables, columns)

    for heading, body in _split_sections(md):
        kind = classify_section(heading)
        prefix = _prefix_for(kind)
        section_slug = slug(heading) or "preamble"
        blocks = _blocks(body)
        # Tables named by a markdown table in this section become the section's scope,
        # inherited by prose entries that name no table of their own.
        section_tables = sorted(
            {
                name
                for btype, payload in blocks
                if btype == "table"
                for name in _table_first_column(payload)
                if name in tables
            }
        )
        metric_keys_here: list[tuple[str, str]] = []  # (entry_id, key)

        for btype, payload in blocks:
            if btype == "table":
                _emit_table_block(b, payload, kind, prefix, section_slug, tables)
            elif btype == "code":
                if payload:
                    b.add(
                        kind,
                        f"{prefix}.{section_slug}_diagram",
                        f"{heading or 'context'} diagram",
                        payload,
                        section=section_slug,
                        extra_refs=section_tables,
                    )
            elif btype == "list":
                for idx, item in enumerate(payload, start=1):
                    e = _emit_list_item(b, item, kind, prefix, section_slug, idx, section_tables)
                    if kind == "metric" and e:
                        metric_keys_here.append((e["entry_id"], e["key"]))
            elif btype == "quote":
                e = _emit_quote(b, payload, kind, prefix, section_slug, section_tables)
                if kind == "metric" and e:
                    metric_keys_here.append((e["entry_id"], e["key"]))
            elif btype == "para":
                e = _emit_para(b, payload, kind, prefix, section_slug, section_tables)
                if kind == "metric" and e:
                    metric_keys_here.append((e["entry_id"], e["key"]))

    return b.entries


def _table_first_column(lines: Sequence[str]) -> list[str]:
    out = []
    for raw in lines[2:]:  # skip header + separator
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        name = strip_markup(cells[0])
        if re.fullmatch(r"[a-z_][a-z0-9_]*", name):
            out.append(name)
    return out


def _emit_table_block(
    b: _Builder,
    lines: Sequence[str],
    kind: str,
    prefix: str,
    section_slug: str,
    tables: set[str],
) -> None:
    if len(lines) < 3:
        return
    headers = [strip_markup(c) for c in lines[0].strip().strip("|").split("|")]
    for raw in lines[2:]:
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        name = strip_markup(cells[0])
        body = "; ".join(
            f"{h}: {c}" for h, c in zip(headers[1:], cells[1:]) if c
        )
        is_identifier = bool(re.fullmatch(r"[a-z_][a-z0-9_]*", name))
        entry_id = f"table.{name}" if is_identifier else f"{prefix}.{slug(name)}"
        b.add(
            kind,
            entry_id,
            name,
            body,
            section=section_slug,
            extra_refs=[name] if name in tables else [],
        )


def _split_definition(text: str) -> tuple[str, str, str] | None:
    """`**Term** — body` / `**Term** = formula` -> (term, separator, rest)."""
    m = _BOLD_LEAD_RE.match(text.strip())
    if not m:
        return None
    term = strip_markup(m.group("term"))
    sep = m.group("sep") or ""
    rest = m.group("rest").strip()
    if not term or len(term) > 90:
        return None
    return term, sep, rest


def _first_sentence(text: str) -> str:
    parts = _SENTENCE_SPLIT.split(text.strip(), maxsplit=1)
    return parts[0].rstrip(" .")


def _emit_para(
    b: _Builder, text: str, kind: str, prefix: str, section_slug: str, section_tables: Sequence[str]
) -> dict[str, Any] | None:
    text = text.strip()
    if not text or _MARKUP_ONLY.match(text):
        return None
    d = _split_definition(text)
    if d:
        term, sep, rest = d
        formula = _first_sentence(rest) if sep == "=" else ""
        return b.add(
            kind,
            f"{prefix}.{slug(term)}",
            term,
            rest or term,
            formula=formula,
            section=section_slug,
            extra_refs=section_tables,
        )
    return b.add(
        kind,
        f"{prefix}.{slug_words(text)}",
        _first_sentence(text)[:120],
        text,
        section=section_slug,
        extra_refs=section_tables,
    )


def _emit_list_item(
    b: _Builder,
    item: str,
    kind: str,
    prefix: str,
    section_slug: str,
    idx: int,
    section_tables: Sequence[str],
) -> dict[str, Any] | None:
    item = item.strip()
    if not item:
        return None
    d = _split_definition(item)
    if d:
        term, sep, rest = d
        # "K1 — iOS WebKit OTP autofill regression." -> code K1, title the rest
        code_m = re.match(r"^([A-Z]{1,3}\d{1,3})\s*[—–\-:]\s*(.+)$", term)
        if code_m:
            code, title = code_m.group(1), code_m.group(2).rstrip(".")
            return b.add(
                kind,
                f"{prefix}.{code}",
                title,
                f"{title}. {rest}".strip(),
                section=section_slug,
                extra_refs=section_tables,
            )
        formula = _first_sentence(rest) if sep == "=" else ""
        return b.add(
            kind,
            f"{prefix}.{slug(term)}",
            term,
            rest or term,
            formula=formula,
            section=section_slug,
            extra_refs=section_tables,
        )
    idents = code_identifiers(item)
    lead = idents[0].replace(".", "_") if item.lstrip().startswith("`") and idents else None
    entry_id = f"{prefix}.{lead or slug_words(item)}"
    return b.add(
        kind,
        entry_id,
        _first_sentence(item)[:120],
        item,
        section=section_slug,
        extra_refs=section_tables,
    )


def _emit_quote(
    b: _Builder, text: str, kind: str, prefix: str, section_slug: str, section_tables: Sequence[str]
) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    # A blockquote inside a metric section that restates a metric in a *different* way is
    # the single most common shape of documentation drift. Promote it to its own metric
    # entry so the two definitions are directly comparable (check C1).
    if kind == "metric":
        for span in _BOLD_SPAN_RE.finditer(text):
            inner = span.group(1).strip()
            if not any(d in inner for d in DIVIDERS):
                continue
            m = re.split(r"\s+(?:as|=|is|means)\s+", inner, maxsplit=1)
            if len(m) != 2:
                continue
            name, formula = m[0].strip(), m[1].strip()
            tail = text[span.end() :].lstrip()
            paren = re.match(r"^\((?P<p>[^)]*)\)", tail)
            if paren:
                formula = f"{formula} ({paren.group('p')})"
            return b.add(
                kind,
                f"{prefix}.{slug(name)}",
                f"{name} (note)",
                text,
                formula=formula,
                section=section_slug,
                extra_refs=section_tables,
            )
    return b.add(
        kind if kind != "metric" else "business_def",
        f"{prefix if kind != 'metric' else 'business_def'}.{slug_words(text)}",
        _first_sentence(text)[:120],
        text,
        section=section_slug,
        extra_refs=section_tables,
    )


# --------------------------------------------------------------------------
# entries derived from the live database, not from the markdown
# --------------------------------------------------------------------------


def table_doc_entries(
    table: str,
    columns: Sequence[tuple[str, str]],
    source: str = "context_agent",
    note: str = "",
    row_count: int | None = None,
) -> list[dict[str, Any]]:
    """Auto-documentation for a table that exists in ClickHouse but not in the markdown."""
    body_bits = [f"{len(columns)} columns"]
    if row_count is not None:
        body_bits.append(f"{row_count:,} rows at first observation")
    if note:
        body_bits.append(note)
    entries: list[dict[str, Any]] = [
        {
            "entry_id": f"table.{table}",
            "kind": "table_doc",
            "key": table,
            "body": (
                f"Auto-documented from the live schema: {'; '.join(body_bits)}. "
                f"Columns: {', '.join(n for n, _ in columns)}."
            ),
            "formula": "",
            "refs": [table],
            "source": source,
            "source_ref": "system.columns",
            "status": "active",
            "confidence": 1.0,
        }
    ]
    for name, ctype in columns:
        entries.append(
            {
                "entry_id": f"column.{table}.{name}",
                "kind": "column_doc",
                "key": f"{table}.{name}",
                "body": f"{name} {ctype} on {table}.",
                "formula": "",
                "refs": [table, name],
                "source": source,
                "source_ref": "system.columns",
                "status": "active",
                "confidence": 1.0,
            }
        )
    return entries
