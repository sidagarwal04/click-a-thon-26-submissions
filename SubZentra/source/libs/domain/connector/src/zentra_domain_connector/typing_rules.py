"""Classifying source column types for join eligibility.

ClickHouse types arrive as strings with wrappers — ``Nullable(LowCardinality(
String))`` — so the first job is unwrapping, and the second is deciding which
families could plausibly hold the same key.
"""

from __future__ import annotations

import re

from .types import TypeFamily

_WRAPPERS = ("Nullable", "LowCardinality")
_WRAPPER_RE = re.compile(
    r"^(?:" + "|".join(_WRAPPERS) + r")\((.*)\)$", flags=re.IGNORECASE
)


def unwrap_type(declared: str) -> str:
    """Strip ``Nullable`` and ``LowCardinality`` wrappers, however nested.

    Both are storage concerns rather than value concerns: a
    ``LowCardinality(String)`` joins to a ``String`` perfectly well, and a
    comparison that treated them as different types would miss most real keys
    in a warehouse that uses the optimisation at all.
    """
    current = declared.strip()
    while True:
        match = _WRAPPER_RE.match(current)
        if match is None:
            return current
        current = match.group(1).strip()


def normalise_type(declared: str) -> str:
    """A canonical spelling of a type, used for field identity.

    Case and wrappers are removed; parameters are kept. ``Decimal(10, 2)`` and
    ``Decimal(12, 2)`` really are different types for a key's purposes, so
    collapsing them would let a genuine schema change pass unnoticed.
    """
    return unwrap_type(declared).replace(" ", "").lower()


def classify(declared: str) -> TypeFamily:
    """Group a declared type into a join-relevant family."""
    base = unwrap_type(declared).lower()
    # Order matters: check the narrow names before the substrings that would
    # also match them. `datetime64` contains neither `int` nor `date` alone at
    # the start, but `int` appears inside `point`-style names in other engines,
    # so anchoring on the prefix is safer than a bare `in` test.
    if base.startswith("uuid"):
        return TypeFamily.UUID
    if base.startswith("bool"):
        return TypeFamily.BOOLEAN
    if base.startswith(("date", "time")):
        return TypeFamily.TEMPORAL
    if base.startswith(("decimal", "numeric")):
        return TypeFamily.DECIMAL
    if base.startswith(("float", "double", "real")):
        return TypeFamily.FLOAT
    if base.startswith(("int", "uint", "smallint", "bigint", "tinyint", "serial")):
        return TypeFamily.INTEGER
    if base.startswith(("string", "fixedstring", "varchar", "char", "text", "enum")):
        return TypeFamily.STRING
    return TypeFamily.OTHER


#: Families that may join to each other despite not being identical.
#:
#: A UUID stored as a String on one side is the single most common real-world
#: case. Integers and decimals are allowed together because surrogate keys are
#: routinely declared as one on one side and the other on the other.
_COMPATIBLE_PAIRS: frozenset[frozenset[TypeFamily]] = frozenset(
    {
        frozenset({TypeFamily.UUID, TypeFamily.STRING}),
        frozenset({TypeFamily.INTEGER, TypeFamily.DECIMAL}),
    }
)


def types_are_compatible(left: TypeFamily, right: TypeFamily) -> bool:
    """Whether two fields could hold the same key.

    A gate rather than a score: an incompatible pair is not a weak candidate,
    it is not a candidate. Float and temporal families are never join keys —
    float equality is unreliable, and two rows sharing a timestamp is
    coincidence rather than reference.
    """
    from .types import JOINABLE_FAMILIES

    if left not in JOINABLE_FAMILIES or right not in JOINABLE_FAMILIES:
        return False
    if left == right:
        return True
    return frozenset({left, right}) in _COMPATIBLE_PAIRS
