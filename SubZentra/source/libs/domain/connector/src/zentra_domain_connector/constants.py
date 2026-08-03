"""Tuning constants for connector discovery and relation inference.

Gathered here rather than inlined so that the numbers a reviewer will argue
about are all in one place, and so that the natural home for per-Tenant
configuration later is obvious.

The ceiling tables deliberately mirror the shape of
``zentra_domain_investigation._SAMPLE_CEILINGS``: this codebase already decided
that confidence is bounded by the evidence behind it rather than asserted, and
relation inference is the same problem wearing different clothes.
"""

from __future__ import annotations

#: The most confidence an overlap measurement taken over this many sampled rows
#: may claim. Overlap measured on a handful of rows is a coincidence waiting to
#: be believed, so the floor is deliberately low.
SAMPLE_CEILINGS: tuple[tuple[int, float], ...] = (
    (100, 0.50),
    (1_000, 0.70),
    (10_000, 0.85),
)
UNKNOWN_SAMPLE_CEILING = 0.40

#: The most confidence a relation between fields of this distinct-value count
#: may claim. This is the rule that stops two boolean columns overlapping
#: perfectly from being offered as a join: with two distinct values, perfect
#: overlap carries almost no information about whether the fields are related.
CARDINALITY_CEILINGS: tuple[tuple[int, float], ...] = (
    (2, 0.10),
    (10, 0.35),
    (100, 0.60),
    (1_000, 0.80),
)
UNKNOWN_CARDINALITY_CEILING = 0.40

#: Below this measured overlap fraction a candidate is not proposed at all.
#: Not a ceiling — a floor. A relation whose values mostly do not match is not
#: a weak relation, it is a wrong one.
MIN_OVERLAP_FRACTION = 0.50

#: Below this combined score a candidate is not proposed, so that reviewers are
#: not handed a list padded with noise they must reject one by one.
MIN_PROPOSAL_CONFIDENCE = 0.20

#: How the two positive signals combine into a raw score before ceilings apply.
#: Overlap outweighs naming because names lie and data does not, but naming
#: still carries real information: matching values in identically-named columns
#: is more likely a key than matching values in unrelated ones.
NAME_AFFINITY_WEIGHT = 0.35
OVERLAP_WEIGHT = 0.65

#: A field whose distinct count is this close to its row count is treated as
#: unique, which is what lets a Relation state its direction.
UNIQUENESS_TOLERANCE = 0.99

#: Suffixes stripped when normalising a field name, so that ``customer_id``,
#: ``customer_key`` and ``customerId`` compare equal to ``customer``.
KEY_SUFFIXES: tuple[str, ...] = ("id", "key", "code", "no", "num", "fk", "ref")

#: Single-token prefixes of the ``o_orderkey`` / ``c_custkey`` variety, common
#: in warehouse schemas including TPC-H. Stripped only when they are one or two
#: characters, so a real word is never eaten.
MAX_STRIPPED_PREFIX_LENGTH = 2

#: Default ceiling on rows a single profiling or overlap query may scan.
DEFAULT_SAMPLE_ROWS = 10_000

#: Default number of queries one Harvest Run may issue before it must stop.
DEFAULT_QUERY_BUDGET = 500

#: Default wall-clock seconds one Harvest Run may consume.
DEFAULT_TIME_BUDGET_SECONDS = 900.0

#: Upload ceiling. Stated rather than discovered, so that exceeding it fails
#: predictably instead of at whatever point memory happens to run out.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
