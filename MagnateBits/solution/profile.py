"""Deterministic spec + event profiling. NO LLM, NO feature-specific code.

Owner: profiler lane.

    profile_spec(spec_md, events) -> SpecProfile
    derive_semantics(profile)     -> FeatureSemantics   (the seam Analytics consumes)

Everything here is inferred at runtime from (a) the spec markdown and (b) the raw NDJSON.
A feature this module has never seen produces the same quality of output as one it has,
because it contains no knowledge of any particular feature -- only of the *shape* of an
Atlys event stream.

Three things this module is deliberately careful about:

1. **The entity key is derived, not assumed.** A sharer/recipient feature's natural key is
   not `user_id`; a group feature's is not `application_id`. We score every id-like column
   on event-type coverage, row coverage, whether the spec's action bullets name it, and how
   often a single key value spans more than one step, then record a confidence and a
   rationale so a reviewer can disagree with the arithmetic rather than the conclusion.

2. **The funnel order is derived three independent ways and cross-checked** -- spec bullet
   order, descending volume, and per-entity pairwise timestamp precedence (Copeland). When
   they disagree we say so in `funnel_derivation` instead of quietly picking one.

3. **Cross-references are segment-level only.** Spec-event `user_id`/`application_id` values
   have zero overlap with the 8 pre-existing tables, so an identity join returns nothing
   silently. Any CrossRef this module emits therefore carries a *segment* join key
   (destination / country / device / day), never an identity column.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import orjson

from contracts import (
    CrossRef,
    EventFieldProfile,
    FeatureSemantics,
    MeasureSpec,
    SpecProfile,
)
from mapping import EPOCH, classify_measure, flatten_event, is_identity_name

__all__ = [
    "profile_spec",
    "derive_semantics",
    "parse_spec_markdown",
    "extract_questions",
    "feature_slug_for",
]

# --------------------------------------------------------------------------
# tunables (all generic; none of them encode a feature)
# --------------------------------------------------------------------------

MAX_DISTINCT_TRACKED = 200_000
MAX_ENTITIES_TRACKED = 500_000
LOW_CARD_MAX = 64          # a dim is "segmentable" below this many distinct values
SMALL_INT_DIM_MAX = 12     # ints below this many distinct values are buckets, not measures
SEGMENT_MIN_COVERAGE = 0.10
MAX_SEGMENT_DIMS = 12
MAX_ENTITY_CANDIDATES = 6
MAX_SHARED_DIM_HINTS = 4
EVENT_COLUMN = "event"
TS_COLUMN_NAMES = ("timestamp", "ts", "event_time", "time", "occurred_at", "created_at")

_BACKTICK = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)`")
_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")
_BULLET = re.compile(r"^\s{0,3}[-*+]\s+(.*)$")
_CONF_TAG = re.compile(r"\[confidence=([0-9.]+)\]")
_SOURCE_TAG = re.compile(r"\[source=([a-z_]+)\]")


# --------------------------------------------------------------------------
# spec.md parsing
# --------------------------------------------------------------------------


@dataclass
class ParsedSpec:
    title: str
    action_events: list[str]                 # backticked tokens leading each action bullet
    bullet_fields: list[str]                 # backticked tokens inside the action bullets
    questions: list[str]
    mention_order: dict[str, int]            # token -> index of first mention in the doc
    sections: dict[str, str]


def _sections(md: str) -> tuple[str, dict[str, str]]:
    """Split markdown into (title, {heading_lower: body})."""
    title = ""
    out: dict[str, str] = {}
    current = ""
    buf: list[str] = []
    for line in md.splitlines():
        m = _HEADING.match(line)
        if m:
            if current:
                out[current] = "\n".join(buf)
            head = m.group(1).strip()
            if not title and line.lstrip().startswith("# "):
                title = head
                current, buf = "", []
                continue
            current, buf = head.lower(), []
        else:
            buf.append(line)
    if current:
        out[current] = "\n".join(buf)
    return title, out


def _bullets(body: str) -> list[str]:
    """Bullet items, with hanging continuation lines folded back in."""
    items: list[str] = []
    for raw in body.splitlines():
        m = _BULLET.match(raw)
        if m:
            items.append(m.group(1).strip())
        elif items and raw.strip() and raw.startswith((" ", "\t")):
            items[-1] = f"{items[-1]} {raw.strip()}"
        elif not raw.strip():
            continue
    return items


def _clean_title(title: str) -> str:
    """'# Feature spec — Visa Status Sharing' -> 'Visa Status Sharing'."""
    t = title.strip()
    for sep in ("—", "–", " - ", ":"):
        if sep in t:
            head, _, tail = t.partition(sep)
            if re.search(r"\b(feature|spec|specification|prd)\b", head, re.I) and tail.strip():
                return tail.strip()
    return t


def parse_spec_markdown(md: str) -> ParsedSpec:
    """Pull title / ordered raw events / PM questions out of a feature spec.

    Heading text is matched by keyword, never by exact string, and there is a
    document-wide fallback, so an unseen spec that words its headings differently still
    yields an ordered event list.
    """
    title, secs = _sections(md)

    mention_order: dict[str, int] = {}
    for i, m in enumerate(_BACKTICK.finditer(md)):
        mention_order.setdefault(m.group(1), i)

    def pick(*keywords: str) -> str:
        for head, body in secs.items():
            if all(k in head for k in keywords):
                return body
        return ""

    actions_body = (
        pick("raw", "event")
        or pick("action")
        or pick("event", "emitted")
        or pick("event")
    )
    action_events: list[str] = []
    bullet_fields: list[str] = []
    for item in _bullets(actions_body):
        toks = _BACKTICK.findall(item)
        if not toks:
            continue
        if toks[0] not in action_events:
            action_events.append(toks[0])
        for t in toks[1:]:
            if t not in bullet_fields:
                bullet_fields.append(t)

    q_body = pick("question") or pick("pm") or pick("metric")
    questions = [q for q in _bullets(q_body) if q]

    return ParsedSpec(
        title=_clean_title(title),
        action_events=action_events,
        bullet_fields=bullet_fields,
        questions=questions,
        mention_order=mention_order,
        sections=secs,
    )


def extract_questions(spec_markdown: str) -> list[str]:
    """Verbatim 'Questions the PM will ask' bullets. Used by MV justification downstream."""
    return parse_spec_markdown(spec_markdown).questions


def feature_slug_for(spec_md: Path, title: str = "") -> str:
    """'.../07_some_feature/spec.md' -> 'some_feature'; falls back to a slugified title."""
    parent = spec_md.parent.name
    slug = re.sub(r"^\d+[_-]", "", parent).strip("_-")
    if not slug or slug in ("specs", ".", ""):
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug or "feature"


# --------------------------------------------------------------------------
# event-stream profiling
# --------------------------------------------------------------------------


@dataclass
class _FieldStat:
    name: str
    json_path: str
    types: set[str] = dc_field(default_factory=set)
    present: int = 0        # key was present in the event object
    nonnull: int = 0        # present and not JSON null
    nonblank: int = 0       # present, not null, and not the empty string
    distinct: set = dc_field(default_factory=set)
    distinct_capped: bool = False
    samples: list = dc_field(default_factory=list)
    events: set[str] = dc_field(default_factory=set)
    events_nonblank: set[str] = dc_field(default_factory=set)
    nonblank_by_event: Counter = dc_field(default_factory=Counter)
    numeric_min: float | None = None
    numeric_max: float | None = None
    raw_values: list = dc_field(default_factory=list)   # bounded, feeds ch_type_for

    def observe(self, value: Any, event_type: str) -> None:
        self.present += 1
        self.events.add(event_type)
        self.types.add(type(value).__name__)
        if value is None:
            return
        self.nonnull += 1
        if isinstance(value, str) and value == "":
            return
        self.nonblank += 1
        self.events_nonblank.add(event_type)
        self.nonblank_by_event[event_type] += 1
        if len(self.raw_values) < 5000:
            self.raw_values.append(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            v = float(value)
            self.numeric_min = v if self.numeric_min is None else min(self.numeric_min, v)
            self.numeric_max = v if self.numeric_max is None else max(self.numeric_max, v)
        key = value if isinstance(value, (str, int, float, bool)) else repr(value)
        if not self.distinct_capped:
            self.distinct.add(key)
            if len(self.distinct) > MAX_DISTINCT_TRACKED:
                self.distinct_capped = True
        if len(self.samples) < 10 and value not in self.samples:
            self.samples.append(value)


def _iter_events(path: Path) -> Iterable[dict]:
    with path.open("rb") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield orjson.loads(line)


def _ts_column(stats: dict[str, _FieldStat]) -> str:
    for cand in TS_COLUMN_NAMES:
        if cand in stats:
            return cand
    for name, st in stats.items():
        if st.types <= {"str", "NoneType"} and st.samples and isinstance(st.samples[0], str):
            if re.match(r"^\d{4}-\d{2}-\d{2}[T ]", st.samples[0]):
                return name
    return ""


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            return dt.replace(tzinfo=None)
        except ValueError:
            return EPOCH
    if isinstance(value, (int, float)):
        v = float(value)
        if v > 32503680000:
            v /= 1000.0
        return datetime.fromtimestamp(v, tz=timezone.utc).replace(tzinfo=None)
    return EPOCH


# ---- entity-key candidates ------------------------------------------------


def _is_temporal(name: str, st: "_FieldStat") -> bool:
    n = name.lower().rsplit(".", 1)[-1]
    if n in TS_COLUMN_NAMES or n.endswith(("_at", "_ts", "_time", "_date", "_timestamp")):
        return True
    return bool(
        st.samples
        and all(isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}", v) for v in st.samples)
    )


@dataclass
class _KeyCandidate:
    name: str
    n_events: int
    coverage: float
    id_named: bool
    bullet_named: bool
    distinct: int
    multistep_frac: float = 0.0
    mention_idx: int = 10_000

    def score(self) -> tuple:
        return (
            self.n_events,
            round(self.coverage, 3),
            int(self.id_named),
            int(self.bullet_named),
            round(self.multistep_frac, 3),
            -self.mention_idx,
            # last resort: deterministic, and shorter generic names sort first
            -len(self.name),
        )


_SCORE_LEVELS = (
    ("event-type coverage", 0.95),
    ("row coverage", 0.92),
    ("id-shaped name", 0.85),
    ("named in the spec's action bullets", 0.80),
    ("per-entity multi-step coherence", 0.70),
    ("first mention order in spec.md", 0.55),
    ("name length", 0.50),
)


def _candidates(
    stats: dict[str, _FieldStat],
    row_count: int,
    parsed: ParsedSpec,
) -> list[_KeyCandidate]:
    out: list[_KeyCandidate] = []
    for name, st in stats.items():
        if name == EVENT_COLUMN or st.nonblank == 0 or "." in name:
            continue
        if not (st.types <= {"str", "NoneType"}):
            continue
        if _is_temporal(name, st):
            continue  # a timestamp is high-cardinality but is not an entity
        distinct = len(st.distinct)
        if distinct < 2:
            continue
        # the per-row unique id is never an entity key (house_rules.md section 2)
        if distinct >= 0.999 * row_count:
            continue
        id_named = is_identity_name(name)
        # allow an unusually-named high-cardinality key through, at lower priority
        if not id_named and distinct < max(2, 0.02 * row_count):
            continue
        if not id_named and distinct <= LOW_CARD_MAX:
            continue
        out.append(
            _KeyCandidate(
                name=name,
                n_events=len(st.events_nonblank),
                coverage=st.nonblank / row_count if row_count else 0.0,
                id_named=id_named,
                bullet_named=name in parsed.bullet_fields,
                distinct=distinct,
                mention_idx=parsed.mention_order.get(name, 10_000),
            )
        )
    out.sort(key=lambda c: c.score(), reverse=True)
    return out[:MAX_ENTITY_CANDIDATES]


def _first_divergence(a: _KeyCandidate, b: _KeyCandidate) -> tuple[str, float]:
    sa, sb = a.score(), b.score()
    for i, (label, conf) in enumerate(_SCORE_LEVELS):
        if sa[i] != sb[i]:
            return label, conf
    return "nothing (candidates are indistinguishable)", 0.45


# ---- funnel ordering ------------------------------------------------------


def _copeland(
    pairs: Counter, events: Sequence[str], tiebreak: dict[str, int] | None = None
) -> tuple[list[str], float]:
    """Rank event types by pairwise-precedence wins; return (order, mean margin)."""
    tiebreak = tiebreak or {}
    wins: Counter = Counter({e: 0 for e in events})
    margins: list[float] = []
    for i, a in enumerate(events):
        for b in events[i + 1 :]:
            w, l = pairs[(a, b)], pairs[(b, a)]
            if w > l:
                wins[a] += 1
            elif l > w:
                wins[b] += 1
            if w + l:
                margins.append(abs(w - l) / (w + l))
    order = sorted(events, key=lambda e: (-wins[e], -tiebreak.get(e, 0), e))
    return order, (sum(margins) / len(margins) if margins else 0.0)


#: A pair of event types is an exclusive BRANCH (not two funnel steps) when almost no
#: entity has both. In a genuinely sequential funnel an entity that reached the later
#: step necessarily has the earlier one, so overlap/min(count) sits at ~1.0; alternative
#: outcomes sit at ~0.0. Measured across every spec and mock topology in this repo: 1.000
#: for eight of them, 0.420 and 0.667 for the two with a genuinely optional middle step
#: (still sequential, correctly not flagged), and 0.000 for the one real branch. A 0.05
#: cut separates those cleanly with a wide margin on both sides.
BRANCH_MAX_OVERLAP = 0.05
#: Below this many entities on the smaller arm the ratio is noise, so leave it alone.
BRANCH_MIN_ENTITIES = 30


def _exclusive_branches(
    per_entity: dict, events: Sequence[str], counts: "Counter | dict[str, int]"
) -> tuple[set[str], str]:
    """Event types that are alternative OUTCOMES, not steps -- to drop from the funnel.

    Why this matters: `windowFunnel` requires strict sequential passage, so putting a
    mutually-exclusive alternative in the middle of the step list forces every entity
    that took the *other* branch to stop there. Every step after it then reports zero --
    not "nobody converted", but "this funnel cannot be satisfied by construction". The
    numbers look like a catastrophic drop-off rather than a modelling error, which is
    the dangerous kind of wrong.

    Returns (branch_event_types, human_readable_note). The lower-volume arm is dropped
    so the funnel keeps the majority path; the dropped arm is still fully queryable on
    its own (it is only excluded from the ordered funnel, never from the table).
    """
    present: dict[str, set] = {e: set() for e in events}
    for ent, first in per_entity.items():
        for e in first:
            if e in present:
                present[e].add(ent)

    branches: set[str] = set()
    notes: list[str] = []
    for i, a in enumerate(events):
        for b in events[i + 1 :]:
            na, nb = len(present[a]), len(present[b])
            smaller = min(na, nb)
            if smaller < BRANCH_MIN_ENTITIES:
                continue
            overlap = len(present[a] & present[b])
            ratio = overlap / smaller
            if ratio <= BRANCH_MAX_OVERLAP:
                drop = a if counts.get(a, 0) <= counts.get(b, 0) else b
                keep = b if drop == a else a
                branches.add(drop)
                notes.append(
                    f"{a} and {b} share only {overlap}/{smaller} entities "
                    f"({ratio:.0%}) -- mutually exclusive outcomes, not sequential "
                    f"steps; dropped {drop} from the funnel (kept {keep}, the larger "
                    f"arm) so the steps after it are not forced to zero"
                )
    return branches, " ".join(notes)


def _kendall(a: Sequence[str], b: Sequence[str]) -> float:
    """Fraction of concordant ordered pairs between two rankings of the same set."""
    common = [x for x in a if x in b]
    if len(common) < 2:
        return 1.0
    ra = {x: i for i, x in enumerate(a)}
    rb = {x: i for i, x in enumerate(b)}
    conc = disc = 0
    for i, x in enumerate(common):
        for y in common[i + 1 :]:
            if (ra[x] - ra[y]) * (rb[x] - rb[y]) > 0:
                conc += 1
            else:
                disc += 1
    return conc / (conc + disc) if conc + disc else 1.0


def _disagreements(a: Sequence[str], b: Sequence[str]) -> list[str]:
    ra = {x: i for i, x in enumerate(a)}
    rb = {x: i for i, x in enumerate(b)}
    out = []
    common = [x for x in a if x in b]
    for i, x in enumerate(common):
        for y in common[i + 1 :]:
            if (ra[x] - ra[y]) * (rb[x] - rb[y]) < 0:
                out.append(f"{x}<->{y}")
    return out[:6]


# --------------------------------------------------------------------------
# the entry point
# --------------------------------------------------------------------------

# derive_semantics() needs a few numbers that SpecProfile has no field for
# (entity-key confidence, step-order source, per-field coverage detail). We keep them in
# a process-local cache AND encode the two scalars into the rationale strings, so a
# SpecProfile round-tripped through JSON in another lane still yields the same semantics.
_EXTRAS: dict[str, dict[str, Any]] = {}


def profile_spec(spec_md: Path, events: Path) -> SpecProfile:
    spec_md, events = Path(spec_md), Path(events)
    md = spec_md.read_text(encoding="utf-8")
    parsed = parse_spec_markdown(md)
    slug = feature_slug_for(spec_md, parsed.title)

    # ---- pass 1: field statistics ----------------------------------------
    stats: dict[str, _FieldStat] = {}
    event_counts: Counter = Counter()
    nested_paths: set[str] = set()
    row_count = 0

    for ev in _iter_events(events):
        row_count += 1
        etype = str(ev.get(EVENT_COLUMN, ""))
        event_counts[etype] += 1
        flat = flatten_event(ev)
        for path, value in flat.items():
            if "." in path:
                nested_paths.add(path)
            st = stats.get(path)
            if st is None:
                st = stats[path] = _FieldStat(name=path.replace(".", "_"), json_path=path)
            st.observe(value, etype)

    if row_count == 0:
        raise ValueError(f"{events} contains no events")

    event_types = [e for e, _ in event_counts.most_common()]
    ts_col = _ts_column(stats)

    # ---- pass 2: per-entity sequences for every entity-key candidate -------
    cands = _candidates(stats, row_count, parsed)
    if not cands:
        raise ValueError(f"{events}: no usable entity-key candidate found")

    cand_names = [c.name for c in cands]
    # candidate -> entity value -> event type -> (first_ts, first_line_index)
    seen: dict[str, dict[str, dict[str, tuple[datetime, int]]]] = {
        n: defaultdict(dict) for n in cand_names
    }
    for idx, ev in enumerate(_iter_events(events)):
        etype = str(ev.get(EVENT_COLUMN, ""))
        ts = _parse_ts(ev.get(ts_col)) if ts_col else EPOCH
        for n in cand_names:
            val = ev.get(n) if "." not in n else None
            if not isinstance(val, str) or not val:
                continue
            bucket = seen[n]
            if val not in bucket and len(bucket) >= MAX_ENTITIES_TRACKED:
                continue
            slot = bucket[val]
            prev = slot.get(etype)
            if prev is None or (ts, idx) < prev:
                slot[etype] = (ts, idx)

    for c in cands:
        bucket = seen[c.name]
        if bucket:
            c.multistep_frac = sum(1 for d in bucket.values() if len(d) > 1) / len(bucket)
    cands.sort(key=lambda c: c.score(), reverse=True)

    best = cands[0]
    entity_key = best.name
    if len(cands) > 1:
        reason, confidence = _first_divergence(best, cands[1])
        runner = cands[1]
        coextensive = [
            c.name
            for c in cands[1:]
            if c.n_events == best.n_events
            and abs(c.coverage - best.coverage) < 1e-9
            and c.distinct == best.distinct
        ]
    else:
        reason, confidence, runner, coextensive = "it is the only candidate", 0.90, None, []

    rationale_bits = [
        f"{entity_key}: present on {best.n_events}/{len(event_types)} event types, "
        f"{best.coverage:.1%} of rows, {best.distinct:,} distinct values, "
        f"{best.multistep_frac:.0%} of values span >1 step."
    ]
    if runner is not None:
        rationale_bits.append(
            f"Runner-up {runner.name} ({runner.n_events}/{len(event_types)} event types, "
            f"{runner.coverage:.1%} rows); decided on {reason}."
        )
    if coextensive:
        confidence = max(confidence, 0.80)
        rationale_bits.append(
            f"Co-extensive alternatives {', '.join(coextensive)} partition the rows "
            f"identically ({best.distinct:,} values, same coverage), so every funnel and "
            f"ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary "
            f"but harmless, hence confidence is not penalised below 0.80."
        )
    rationale_bits.append(
        "Row-unique id columns were excluded as entity keys (house_rules.md section 2)."
    )
    entity_rationale = " ".join(rationale_bits) + f" [confidence={confidence:.2f}]"

    # ---- funnel: three independent derivations ---------------------------
    obs = set(event_types)
    steps_spec = [e for e in parsed.action_events if e in obs]
    spec_covers = len(steps_spec) == len(obs)
    if not spec_covers:
        # document-wide fallback: first mention order of any observed event name
        extra = sorted(
            (e for e in obs if e not in steps_spec),
            key=lambda e: (parsed.mention_order.get(e, 10_000), -event_counts[e], e),
        )
        steps_spec = steps_spec + extra

    steps_volume = sorted(event_types, key=lambda e: (-event_counts[e], e))

    pairs: Counter = Counter()
    tie_pairs: Counter = Counter()
    for first in seen[entity_key].values():
        items = sorted(first.items())
        for i, (a, (ta, ia)) in enumerate(items):
            for b, (tb, ib) in items[i + 1 :]:
                if ta < tb:
                    pairs[(a, b)] += 1
                elif tb < ta:
                    pairs[(b, a)] += 1
                else:
                    tie_pairs[(a, b) if ia <= ib else (b, a)] += 1
    blended = Counter(pairs)
    for k, v in tie_pairs.items():          # same second -> fall back to emission order
        blended[k] += v
    steps_ts, ts_margin = _copeland(blended, event_types, dict(event_counts))

    tau_sv = _kendall(steps_spec, steps_volume)
    tau_st = _kendall(steps_spec, steps_ts)
    tau_vt = _kendall(steps_volume, steps_ts)

    if spec_covers:
        chosen, source = steps_spec, "spec"
    elif ts_margin >= 0.35:
        chosen, source = steps_ts, "timestamp_median"
    elif len(steps_spec) == len(obs):
        chosen, source = steps_spec, "spec"
    else:
        chosen, source = steps_volume, "volume"

    # A branch is excluded from the FUNNEL only. It stays in `event_types` (and so in
    # the schema, the segment dims and every non-funnel template) -- the rows are real
    # and fully queryable; they simply are not a step on the sequential path.
    branches, branch_note = _exclusive_branches(seen[entity_key], event_types, event_counts)
    observed_types = list(chosen)
    funnel_steps = [e for e in chosen if e not in branches] if branches else list(chosen)

    deriv = [
        f"[source={source}]",
        f"spec bullets named {len(set(parsed.action_events) & obs)}/{len(obs)} observed "
        f"event types"
        + ("" if spec_covers else " (incomplete -> document-order fallback used)")
        + ".",
        f"agreement spec~timestamp={tau_st:.2f}, spec~volume={tau_sv:.2f}, "
        f"volume~timestamp={tau_vt:.2f};",
        f"pairwise timestamp decisiveness={ts_margin:.2f} over "
        f"{sum(blended.values()):,} ordered entity pairs.",
    ]
    d_st = _disagreements(steps_spec, steps_ts)
    d_sv = _disagreements(steps_spec, steps_volume)
    if d_st:
        deriv.append(f"timestamp order inverts {', '.join(d_st)} vs the spec -- "
                     f"real signal, treat those two steps as concurrent.")
    if d_sv:
        deriv.append(f"volume order inverts {', '.join(d_sv)} vs the spec "
                     f"(expected where steps share a count).")
    if not d_st and not d_sv:
        deriv.append("all three signals agree exactly.")
    deriv.append(f"volume order={' > '.join(steps_volume)}.")
    deriv.append(f"timestamp order={' > '.join(steps_ts)}.")
    if branch_note:
        deriv.append("BRANCH: " + branch_note + ".")
    funnel_derivation = " ".join(deriv)

    # ---- envelope / partial-envelope events ------------------------------
    n_et = len(event_types)
    envelope = sorted(
        name
        for name, st in stats.items()
        if len(st.events) >= max(1, (n_et + 1) // 2)
        and (st.types <= {"str", "NoneType"})
        and name != EVENT_COLUMN
    )
    partial_envelope: list[str] = []
    if envelope:
        for et in event_types:
            have = sum(1 for c in envelope if et in stats[c].events)
            if have < 0.75 * len(envelope):
                partial_envelope.append(et)

    # ---- assemble ---------------------------------------------------------
    fields = [
        EventFieldProfile(
            name=st.name,
            json_path=st.json_path,
            json_types=sorted(st.types),
            null_frac=round(1.0 - (st.nonnull / row_count), 6),
            distinct_count=len(st.distinct),
            sample_values=st.samples[:10],
            present_in_events=[e for e in event_types if e in st.events],
        )
        for _, st in sorted(stats.items())
    ]

    ts_stat = stats.get(ts_col)
    ts_values = [_parse_ts(v) for v in (ts_stat.distinct if ts_stat else [])] or [EPOCH]
    ts_min, ts_max = min(ts_values), max(ts_values)

    _EXTRAS[slug] = {
        "confidence": confidence,
        "step_order_source": source,
        "steps": funnel_steps,
        "entity_key": entity_key,
        "secondary_keys": [c.name for c in cands[1:]],
        "coextensive": coextensive,
        "envelope": envelope,
        "ts_col": ts_col,
        "row_count": row_count,
        "nested_paths": sorted(nested_paths),
        "nonblank": {n: st.nonblank for n, st in stats.items()},
        "nonblank_by_event": {n: dict(st.nonblank_by_event) for n, st in stats.items()},
        "numeric_range": {
            n: (st.numeric_min, st.numeric_max)
            for n, st in stats.items()
            if st.numeric_min is not None
        },
        "raw_values": {n: st.raw_values[:200] for n, st in stats.items()},
        "distinct_values": {
            n: sorted(str(v) for v in st.distinct)
            for n, st in stats.items()
            if not st.distinct_capped and len(st.distinct) <= 256
        },
        "questions": parsed.questions,
        "steps_spec": steps_spec,
        "steps_volume": steps_volume,
        "steps_timestamp": steps_ts,
    }

    return SpecProfile(
        feature_slug=slug,
        spec_title=parsed.title,
        spec_markdown=md,
        event_types=observed_types,
        event_counts=dict(event_counts),
        fields=fields,
        row_count=row_count,
        ts_min=ts_min,
        ts_max=ts_max,
        entity_key=entity_key,
        entity_key_rationale=entity_rationale,
        derived_funnel=funnel_steps,
        funnel_derivation=funnel_derivation,
        partial_envelope_events=partial_envelope,
    )


# --------------------------------------------------------------------------
# SpecProfile -> FeatureSemantics
# --------------------------------------------------------------------------


def _field_map(profile: SpecProfile) -> dict[str, EventFieldProfile]:
    """json_path -> field profile."""
    return {f.json_path: f for f in profile.fields}


def _col(json_path: str) -> str:
    """json_path -> the ClickHouse column name the DDL lane will emit."""
    return json_path.replace(".", "_")


def _path_by_col(profile: SpecProfile) -> dict[str, str]:
    return {f.name: f.json_path for f in profile.fields}


def _coverage(f: EventFieldProfile, extras: dict, row_count: int) -> float:
    nb = extras.get("nonblank", {}).get(f.json_path)
    if nb is not None and row_count:
        return nb / row_count
    return 1.0 - f.null_frac


def _money_unit(profile: SpecProfile, fmap: dict[str, EventFieldProfile]) -> str:
    for path, f in fmap.items():
        short = path.rsplit(".", 1)[-1].lower()
        if "currency" in short and f.sample_values:
            vals = [str(v) for v in f.sample_values if v]
            if len(set(vals)) == 1:
                return vals[0]
            return "mixed_currency"
    return "currency"


def derive_semantics(
    profile: SpecProfile,
    *,
    ch: Any = None,
    database: str | None = None,
    table_fqn: str | None = None,
) -> FeatureSemantics:
    """Turn a SpecProfile into the parameter object every analytics template reads.

    `ch` is optional: without it the cross-reference probe is skipped rather than failing,
    so this function is usable offline and in unit tests.
    """
    extras = _EXTRAS.get(profile.feature_slug, {})
    row_count = profile.row_count or 1
    fmap = _field_map(profile)

    confidence = extras.get("confidence")
    if confidence is None:
        m = _CONF_TAG.search(profile.entity_key_rationale)
        confidence = float(m.group(1)) if m else 0.8
    source = extras.get("step_order_source")
    if source is None:
        m = _SOURCE_TAG.search(profile.funnel_derivation)
        source = m.group(1) if m else "spec"
    if source not in ("spec", "timestamp_median", "volume", "llm"):
        source = "spec"

    db = database or (getattr(ch, "database", None) if ch is not None else None) or "atlys"
    fqn = table_fqn or f"{db}.f_{profile.feature_slug}_events"

    entity_key = profile.entity_key
    ordered_steps = profile.derived_funnel or profile.event_types

    # ---- identity columns -------------------------------------------------
    identity = [p for p in fmap if is_identity_name(p.rsplit(".", 1)[-1])]
    row_id = [
        p for p in identity if fmap[p].distinct_count >= 0.999 * row_count
    ]
    entity_ids = [p for p in identity if p not in row_id]

    partial_identity = sorted(
        _col(p) for p in entity_ids if _coverage(fmap[p], extras, row_count) < 1.0 - 1e-9
    )

    secondary = extras.get("secondary_keys")
    if secondary is None:
        # No in-process cache (e.g. a SpecProfile loaded from a fixture): reproduce the
        # same ranking from the profile alone so both paths agree byte-for-byte.
        mention = parse_spec_markdown(profile.spec_markdown).mention_order
        secondary = [
            _col(p)
            for p in sorted(
                entity_ids,
                key=lambda p: (
                    -len(fmap[p].present_in_events),
                    -round(_coverage(fmap[p], extras, row_count), 3),
                    mention.get(p, 10_000),
                    len(p),
                    p,
                ),
            )
        ]
    secondary = [s for s in secondary if s != entity_key]

    # ---- disconnected events ---------------------------------------------
    by_event = extras.get("nonblank_by_event", {})
    user_cols = [p for p in entity_ids if "user" in p.lower()]

    def carries(col: str, et: str) -> bool:
        if col in by_event:
            return by_event[col].get(et, 0) > 0
        f = fmap.get(col)
        return bool(f and et in f.present_in_events)

    disconnected = [
        et
        for et in profile.event_types
        if not carries(entity_key, et) and not any(carries(u, et) for u in user_cols)
    ]
    anonymous = [
        et for et in profile.event_types if user_cols and not any(carries(u, et) for u in user_cols)
    ]

    # ---- segment dims -----------------------------------------------------
    # The spec's own "Questions the PM will ask" section names the columns that
    # actually matter for this feature. A dim mentioned there outranks a
    # broadly-covered envelope dim: an anonymous-recipient flag present on one
    # event type is low-coverage but is exactly what the headline question needs.
    # This is derived from the spec text, so it carries to an unseen spec.
    _q_text = " ".join(extract_questions(profile.spec_markdown)).lower()

    def _named_in_questions(col: str) -> int:
        bare = col.rsplit(".", 1)[-1].lower()
        return 0 if (bare in _q_text or bare.replace("_", " ") in _q_text) else 1

    dims: list[tuple[tuple, str]] = []
    for path, f in fmap.items():
        short = path.rsplit(".", 1)[-1].lower()
        if path == EVENT_COLUMN or is_identity_name(short):
            continue
        if short in TS_COLUMN_NAMES or short.endswith(("_at", "_ts", "_time")):
            continue
        # A cut dimension does not have to be a string. Booleans are the ideal one
        # (exactly two buckets), and small integers are what several PM questions
        # actually hinge on -- "completion by group size", "does 1h vs 24h vs 48h
        # matter", "attach rate by attempt count". Excluding non-strings silently
        # made those questions unanswerable, so gate on cardinality, not on type.
        types = set(f.json_types) - {"NoneType"}
        is_boolish = bool(types) and types <= {"bool"}
        is_small_int = bool(types) and types <= {"int"} and f.distinct_count <= SMALL_INT_DIM_MAX
        if not ("str" in f.json_types or is_boolish or is_small_int):
            continue
        if not (2 <= f.distinct_count <= LOW_CARD_MAX):
            continue
        cov = _coverage(f, extras, row_count)
        if cov < SEGMENT_MIN_COVERAGE:
            continue
        dims.append((
            (_named_in_questions(path), -len(f.present_in_events), -round(cov, 4), path),
            _col(path),
        ))
    segment_dims = [p for _, p in sorted(dims)][:MAX_SEGMENT_DIMS]

    # ---- measures ---------------------------------------------------------
    money_unit = _money_unit(profile, fmap)
    unit_for = {
        "money": money_unit,
        "duration_ms": "ms",
        "rate": "ratio",
        "count": "count",
        "score": "score",
        "other": "",
    }
    measures: list[MeasureSpec] = []
    for path in sorted(fmap):
        f = fmap[path]
        short = path.rsplit(".", 1)[-1]
        if is_identity_name(short) or path == EVENT_COLUMN:
            continue
        types = set(f.json_types) - {"NoneType"}
        if not types or not types <= {"int", "float"}:
            continue  # bool -> a flag, str -> a dim, both handled elsewhere
        vals = extras.get("raw_values", {}).get(path) or [
            v for v in f.sample_values if isinstance(v, (int, float))
        ]
        kind = classify_measure(short, vals)
        measures.append(
            MeasureSpec(
                column=path.replace(".", "_"),
                kind=kind,  # type: ignore[arg-type]
                scoped_to_events=list(f.present_in_events),
                unit=unit_for.get(kind, ""),
            )
        )

    # ---- flags ------------------------------------------------------------
    flags: list[str] = []
    nested = extras.get("nested_paths") or sorted(p for p in fmap if "." in p)
    if nested:
        flags.append("nested_fields_flattened:" + ",".join(sorted(nested)[:8]))
    if profile.partial_envelope_events:
        flags.append("partial_envelope_events:" + ",".join(profile.partial_envelope_events))
    if anonymous:
        flags.append("anonymous_events:" + ",".join(anonymous))
    if partial_identity:
        flags.append("guarded_uniq_required:" + ",".join(partial_identity))
    nulls = sorted(p for p, f in fmap.items() if "NoneType" in f.json_types)
    if nulls:
        flags.append("explicit_json_nulls:" + ",".join(nulls[:8]))
    for p in row_id:
        f = fmap[p]
        if f.sample_values and all(
            isinstance(v, str) and _HEX32.match(v) for v in f.sample_values
        ):
            flags.append(f"row_id_32char_hex_not_uuid:{_col(p)}")
    coext = extras.get("coextensive")
    if coext is None:
        ek_path = next((p for p in entity_ids if _col(p) == entity_key), None)
        ekf = fmap.get(ek_path) if ek_path else None
        coext = (
            [
                _col(p)
                for p in entity_ids
                if p != ek_path
                and len(fmap[p].present_in_events) == len(ekf.present_in_events)
                and fmap[p].distinct_count == ekf.distinct_count
                and abs(
                    _coverage(fmap[p], extras, row_count)
                    - _coverage(ekf, extras, row_count)
                )
                < 1e-9
            ]
            if ekf
            else []
        )
    if coext:
        flags.append("entity_key_coextensive_alternatives:" + ",".join(sorted(coext)))
    if float(confidence) < 0.7:
        flags.append(f"entity_key_low_confidence:{confidence:.2f}")

    semantics = FeatureSemantics(
        feature_slug=profile.feature_slug,
        table_fqn=fqn,
        event_column=EVENT_COLUMN,
        event_types=list(profile.event_types),
        entity_key=entity_key,
        entity_key_confidence=float(confidence),
        secondary_keys=secondary,
        ordered_steps=list(ordered_steps),
        step_order_source=source,  # type: ignore[arg-type]
        segment_dims=segment_dims,
        measures=measures,
        flags=flags,
        disconnected_event_types=disconnected,
        partial_identity_columns=partial_identity,
        cross_reference_hints=[],
    )
    if ch is not None:
        try:
            semantics.cross_reference_hints = detect_cross_references(
                profile, semantics, ch, database=db
            )
        except Exception as exc:  # noqa: BLE001 - a probe failure must not kill profiling
            semantics.flags.append(f"crossref_probe_failed:{type(exc).__name__}")
    return semantics


# --------------------------------------------------------------------------
# cross-references into the 8 pre-existing tables -- SEGMENT LEVEL ONLY
# --------------------------------------------------------------------------

# Identity values in spec events have zero overlap with the existing tables, so these are
# never valid join keys no matter how tempting the name match is.
_FORBIDDEN_JOIN_KEYS = ("user_id", "application_id", "id", "session_id")
_JOIN_KEY_PREFERENCE = ("destination", "geoip_country_code", "device_type", "os", "city")

# Tables this pipeline itself creates: never treated as "pre-existing production tables".
_GENERATED_PREFIXES = ("agg_", "mv_", "context_", "schema_", "pipeline_", "insights_",
                       "contradiction")


def _is_generated_table(name: str) -> bool:
    return name.startswith(_GENERATED_PREFIXES) or (
        name.startswith("f_") and name.endswith("_events")
    )


def _list_tables(ch: Any) -> list[str]:
    """ch.list_tables() queries system.tables, which ch.run_select's own guard rejects
    (`\bsystem\b` is in its forbidden-keyword list). SHOW TABLES gets the same answer
    through the guard; we still try the documented API first so a fixed ch.py wins."""
    try:
        return list(ch.list_tables())
    except Exception:  # noqa: BLE001
        return [r["name"] for r in ch.run_select("SHOW TABLES", max_rows=1000)]


def _table_columns(ch: Any, database: str, table: str) -> set[str]:
    try:
        return {n for n, _ in ch.columns(table)}
    except Exception:  # noqa: BLE001
        try:
            rows = ch.run_select(f"DESCRIBE TABLE {database}.{table}", max_rows=500)
        except Exception:  # noqa: BLE001
            return set()
        return {r["name"] for r in rows}


def detect_cross_references(
    profile: SpecProfile,
    semantics: FeatureSemantics,
    ch: Any,
    database: str = "atlys",
) -> list[CrossRef]:
    """Find segment-level links from this feature into the pre-existing tables.

    Two detectors, both deterministic:
      1. a column whose *values* are literally the names of existing tables
         (an unseen spec can encode the legacy funnel as a string enum);
      2. a shared segment vocabulary (same column name, overlapping value sets).
    """
    fmap = _field_map(profile)
    by_col = _path_by_col(profile)
    extras = _EXTRAS.get(profile.feature_slug, {})
    raw = extras.get("raw_values", {})
    dvals = extras.get("distinct_values", {})

    def values_of(path: str, f: EventFieldProfile) -> set[str]:
        return {str(v) for v in (dvals.get(path) or raw.get(path) or f.sample_values)}

    feature_tables = set(_list_tables(ch))
    ours = {t for t in feature_tables if _is_generated_table(t)}
    existing = sorted(feature_tables - ours)
    hints: list[CrossRef] = []

    # --- which existing tables carry which columns -------------------------
    cols_by_table: dict[str, set[str]] = defaultdict(set)
    for t in existing:
        cols_by_table[t] = _table_columns(ch, database, t)

    def best_join_key(targets: Sequence[str]) -> str:
        shared = set.intersection(*[cols_by_table[t] for t in targets]) if targets else set()
        for pref in _JOIN_KEY_PREFERENCE:
            if pref in semantics.segment_dims and pref in shared:
                return pref
        for d in semantics.segment_dims:
            if d in shared and d not in _FORBIDDEN_JOIN_KEYS:
                return d
        return "toDate(timestamp)"

    # --- detector 1: column values ARE existing table names ----------------
    for path, f in fmap.items():
        if path == EVENT_COLUMN or f.distinct_count > 200:
            continue
        if "str" not in f.json_types:
            continue
        vals = values_of(path, f)
        if not vals:
            continue
        matched = sorted(v for v in vals if v in set(existing))
        if len(matched) >= 2 and len(matched) >= 0.5 * len(vals):
            targets = [f"{database}.{m}" for m in matched]
            jk = best_join_key(matched)
            hints.append(
                CrossRef(
                    from_column=_col(path),
                    matches="existing_table_name",
                    targets=targets,
                    join_key=jk,
                    evidence=(
                        f"{len(matched)}/{len(vals)} distinct values of `{path}` are names of "
                        f"pre-existing tables ({', '.join(matched[:4])}"
                        f"{'...' if len(matched) > 4 else ''}). Identity columns do NOT overlap "
                        f"between this feature and those tables, so the only sound comparison is "
                        f"segment-level on `{jk}` over the overlapping date range "
                        f"{profile.ts_min:%Y-%m-%d}..{profile.ts_max:%Y-%m-%d}."
                    ),
                )
            )

    # --- detector 2: shared segment vocabulary -----------------------------
    shared: list[tuple[tuple, CrossRef]] = []
    for dim in semantics.segment_dims:
        path = by_col.get(dim, dim)
        if dim in _FORBIDDEN_JOIN_KEYS or "." in path:
            continue
        tables = [t for t in existing if dim in cols_by_table.get(t, ())]
        if not tables:
            continue
        f = fmap.get(path)
        if f is None:
            continue
        ours = values_of(path, f)
        if not ours:
            continue
        probe = min(tables, key=lambda t: (len(cols_by_table[t]), t))
        got = ch.run_select(
            f"SELECT DISTINCT toString({dim}) AS v FROM {database}.{probe} "
            f"WHERE {dim} IS NOT NULL LIMIT 200",
            max_rows=200,
        )
        theirs = {r["v"] for r in got}
        if not theirs:
            continue
        overlap = ours & theirs
        if len(overlap) >= 2 and len(overlap) >= 0.5 * len(ours):
            pref = (
                _JOIN_KEY_PREFERENCE.index(dim)
                if dim in _JOIN_KEY_PREFERENCE
                else len(_JOIN_KEY_PREFERENCE)
            )
            shared.append(((-len(overlap), pref, dim), CrossRef(
                    from_column=dim,
                    matches="existing_column_values",
                    targets=[f"{database}.{t}" for t in tables],
                    join_key=dim,
                    evidence=(
                        f"`{dim}` shares {len(overlap)}/{len(ours)} of its values with "
                        f"{database}.{probe} and the column exists on {len(tables)} pre-existing "
                        f"tables -- a shared segment vocabulary. Join on `{dim}` (+ date), never "
                        f"on user_id/application_id: those id spaces are disjoint and an identity "
                        f"join returns zero rows silently."
                    ),
                )))

    hints.extend(c for _, c in sorted(shared, key=lambda kv: kv[0])[:MAX_SHARED_DIM_HINTS])
    return hints


# --------------------------------------------------------------------------
# CLI: profile every spec under a directory, print a summary, write fixtures
# --------------------------------------------------------------------------


def profile_dir(specs_dir: Path, *, ch: Any = None) -> list[tuple[SpecProfile, FeatureSemantics]]:
    """Profile every `<n>_<slug>/spec.md` + `events.ndjson` pair under `specs_dir`."""
    out = []
    for d in sorted(p for p in Path(specs_dir).iterdir() if p.is_dir()):
        spec, events = d / "spec.md", d / "events.ndjson"
        if not (spec.exists() and events.exists()):
            continue
        prof = profile_spec(spec, events)
        out.append((prof, derive_semantics(prof, ch=ch)))
    return out


def _summary_table(pairs: list[tuple[SpecProfile, FeatureSemantics]]) -> str:
    head = (
        f"{'slug':<28}{'rows':>7} {'ev':>3} {'entity_key':<16}{'cf':>5} "
        f"{'src':<16}{'dims':>5}{'meas':>5}{'part.id':>8}{'disc':>5}{'xref':>5}  funnel"
    )
    lines = [head, "-" * len(head)]
    for p, s in pairs:
        lines.append(
            f"{p.feature_slug:<28}{p.row_count:>7} {len(p.event_types):>3} "
            f"{s.entity_key:<16}{s.entity_key_confidence:>5.2f} {s.step_order_source:<16}"
            f"{len(s.segment_dims):>5}{len(s.measures):>5}"
            f"{len(s.partial_identity_columns):>8}{len(s.disconnected_event_types):>5}"
            f"{len(s.cross_reference_hints):>5}  {' > '.join(s.ordered_steps)}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Profile feature specs (deterministic, no LLM).")
    ap.add_argument("specs_dir", nargs="?", default="../specs")
    ap.add_argument("--fixtures", default="", help="write FeatureSemantics JSON per slug here")
    ap.add_argument("--no-ch", action="store_true", help="skip the cross-reference probe")
    ap.add_argument("--detail", action="store_true", help="print rationales in full")
    args = ap.parse_args(argv)

    ch = None
    if not args.no_ch:
        try:
            from ch import CH

            ch = CH()
        except Exception as exc:  # noqa: BLE001
            print(f"! ClickHouse unavailable ({exc}); cross-reference probe skipped")

    pairs = profile_dir(Path(args.specs_dir), ch=ch)
    print(_summary_table(pairs))

    if args.detail:
        for p, s in pairs:
            print(f"\n=== {p.feature_slug} — {p.spec_title}")
            print(f"  entity_key : {p.entity_key_rationale}")
            print(f"  funnel     : {p.funnel_derivation}")
            print(f"  dims       : {', '.join(s.segment_dims)}")
            print(f"  measures   : "
                  f"{', '.join(f'{m.column}[{m.kind}]' for m in s.measures) or '-'}")
            print(f"  flags      : {'; '.join(s.flags) or '-'}")
            print(f"  partial_env: {', '.join(p.partial_envelope_events) or '-'}")
            for c in s.cross_reference_hints:
                print(f"  xref       : {c.from_column} -> {c.matches} on {c.join_key} "
                      f"({len(c.targets)} tables)")

    if args.fixtures:
        out = Path(args.fixtures)
        out.mkdir(parents=True, exist_ok=True)
        for _, s in pairs:
            path = out / f"{s.feature_slug}.json"
            path.write_text(
                orjson.dumps(s.model_dump(mode="json"), option=orjson.OPT_INDENT_2).decode(),
                encoding="utf-8",
            )
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
