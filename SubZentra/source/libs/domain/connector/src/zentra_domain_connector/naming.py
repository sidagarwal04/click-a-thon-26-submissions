"""Name affinity between two fields.

The weakest of the three signals, and the one most likely to be wrong on its
own — which is why it is weighted below measured overlap and why nothing is
proposed on naming alone. It still carries real information: matching values in
correspondingly-named columns are far more likely to be a key than matching
values in unrelated ones.
"""

from __future__ import annotations

import re

from .constants import KEY_SUFFIXES, MAX_STRIPPED_PREFIX_LENGTH

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def tokenise(name: str) -> tuple[str, ...]:
    """Split a field name into lowercase tokens.

    Handles ``customerId``, ``customer_id`` and ``CUSTOMER_ID`` identically,
    because a schema will contain all three and a reviewer does not care.
    """
    spaced = _CAMEL_BOUNDARY.sub("_", name)
    parts = _NON_ALNUM.split(spaced.lower())
    return tuple(part for part in parts if part)


def _strip_key_suffix(tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Drop a trailing ``id``/``key``/``ref`` token.

    Never strips the last remaining token: a column simply called ``id`` must
    normalise to ``id`` rather than to nothing, or every bare primary key in
    the schema would compare equal to every other.
    """
    if len(tokens) > 1 and tokens[-1] in KEY_SUFFIXES:
        return tokens[:-1]
    return tokens


def _strip_table_prefix(tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Drop a leading one-or-two character prefix.

    Warehouse schemas — TPC-H among them — prefix columns with an abbreviation
    of their table: ``o_orderkey``, ``c_custkey``. The length bound is what
    stops a real word being eaten; ``order_id`` keeps its ``order``.
    """
    if len(tokens) > 1 and len(tokens[0]) <= MAX_STRIPPED_PREFIX_LENGTH:
        return tokens[1:]
    return tokens


def _singularise(token: str) -> str:
    """Crude English singularisation.

    Deliberately crude. It exists so ``customers.id`` matches ``customer_id``,
    which is the overwhelmingly common case; anything more elaborate would be
    guessing about a language the schema may not even be written in.
    """
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 2 and token.endswith("es") and not token.endswith("ses"):
        return token[:-2]
    if len(token) > 2 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def normalise_field_name(name: str) -> tuple[str, ...]:
    """Reduce a field name to the tokens that carry meaning."""
    tokens = tokenise(name)
    tokens = _strip_table_prefix(tokens)
    tokens = _strip_key_suffix(tokens)
    return tuple(_singularise(token) for token in tokens)


def _core(table: str, field_name: str) -> tuple[str, ...]:
    """The tokens a field contributes, including its table when it needs it.

    A column called ``id`` says nothing by itself, so its table name stands in
    for it. That is what lets ``customers.id`` meet ``orders.customer_id``.
    """
    tokens = normalise_field_name(field_name)
    if tokens in ((), ("id",), ("key",)):
        return tuple(_singularise(token) for token in tokenise(table))
    return tokens


def name_affinity(
    left_table: str,
    left_field: str,
    right_table: str,
    right_field: str,
) -> float:
    """Score how much two field names suggest the same key, from 0 to 1.

    Symmetric by construction — a Relation is not directional at this stage, and
    a scoring function that disagreed with itself depending on argument order
    would produce different proposals for the same pair.
    """
    left = _core(left_table, left_field)
    right = _core(right_table, right_field)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    left_set, right_set = set(left), set(right)
    shared = left_set & right_set
    if not shared:
        return 0.0
    # Jaccard rather than raw overlap count, so that a field with many tokens
    # cannot score highly just by containing another's single token.
    return len(shared) / len(left_set | right_set)
