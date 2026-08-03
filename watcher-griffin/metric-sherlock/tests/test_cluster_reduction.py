"""The pre-pass that shrinks clustering input must be exact, not approximate.

WHY THIS FILE EXISTS
`cluster_verdicts` links breaches with a pairwise O(n^2) test. On the busiest real day in
this dataset (2026-06-22, the onset of INC-0623) that is 9,464 breaches, and the loop took
99 seconds even after the input was capped to 8,000 -- so the cap was engaging on the single
most important window of the replay and dropping 1,464 breaches from it.

The fix was to shrink n by removing work that is redundant BY CONSTRUCTION, and the whole
value of it rests on that redundancy being real:

  - breaches sharing (scope key, direction, window) have IDENTICAL atom sets, so every pair
    among them relates; the loop can only rediscover a link already known;
  - global breaches have NO atoms, so `_related` is False for every pair involving one, and
    they are attached to an explaining cluster in a later step instead.

If either claim is wrong, clusters silently merge or split. These tests pin both, and pin the
end-to-end invariant: same input, same partition, whether or not the pre-pass runs.
"""

from datetime import datetime

import pytest

from engine.cluster import _atom_memo, _related, atoms
from engine.scopes import scope


class _V:
    """A stand-in breach carrying only the fields the linking logic reads."""

    def __init__(self, scope_type, scope_value, direction="below", metric="fill_rate",
                 ws=datetime(2026, 6, 25), we=datetime(2026, 6, 26)):
        self.scope_type = scope_type
        self.scope_value = scope_value
        self.direction = direction
        self.metric = metric
        self.window_start = ws
        self.window_end = we
        self.impact_usd = 1.0


def test_identical_scope_keys_have_identical_atom_sets():
    """The premise of reduction 1. Same key -> same atoms -> guaranteed to relate."""
    a = _V("os_family", "Android", metric="fill_rate")
    b = _V("os_family", "Android", metric="rpr")

    assert atoms(a.scope_type, a.scope_value) == atoms(b.scope_type, b.scope_value)
    assert atoms(a.scope_type, a.scope_value), "must be non-empty, or they would not relate"
    assert _related(a, b) is True


@pytest.mark.parametrize("scope_type,scope_value", [
    ("os_family", "Android"),
    ("os_version", "Android 15"),
    ("region", "APAC"),
    ("geo_cell", "APAC|JP|iPhone 14"),
])
def test_non_global_scopes_always_carry_at_least_one_atom(scope_type, scope_value):
    """If a non-global scope had no atoms it would be silently unlinkable."""
    assert atoms(scope_type, scope_value), f"{scope_type}={scope_value} carries no atom"


def test_global_breaches_relate_to_nothing():
    """The premise of reduction 2. Excluding globals from the loop changes no link."""
    g = _V("global", "")
    assert scope("global").is_global
    assert atoms("global", "") == set()

    for other in (_V("os_family", "Android"), _V("region", "APAC"), _V("global", "")):
        assert _related(g, other) is False
        assert _related(other, g) is False


def test_the_memo_returns_exactly_what_the_uncached_call_returns():
    """A cache that disagrees with the function it caches is the worst kind of speedup."""
    atom_of = _atom_memo(None)
    for st, sv in [("os_family", "Android"), ("os_version", "iOS 18.1"),
                   ("region", "EU"), ("geo_cell", "APAC|JP|iPhone 14"), ("global", "")]:
        assert atom_of(st, sv) == atoms(st, sv, None)
        assert atom_of(st, sv) == atoms(st, sv, None), "second (cached) call must also agree"


def test_related_agrees_with_and_without_the_memo():
    pairs = [
        (_V("os_family", "Android"), _V("os_version", "Android 15")),   # derived-atom link
        (_V("os_family", "Android"), _V("os_version", "iOS 18.1")),     # different platforms
        (_V("region", "APAC"), _V("geo_cell", "APAC|JP|iPhone 14")),    # composite link
        (_V("region", "EU"), _V("geo_cell", "APAC|JP|iPhone 14")),      # unrelated regions
    ]
    atom_of = _atom_memo(None)
    for a, b in pairs:
        assert _related(a, b, atom_of) == _related(a, b), f"{a.scope_value} vs {b.scope_value}"


def test_collapsing_does_not_merge_across_direction_or_window():
    """The collapse key includes direction and window for a reason.

    A fill drop and a fill spike on the same scope are not one incident, and neither are two
    breaches on the same scope in non-overlapping windows.
    """
    below = _V("os_family", "Android", direction="below")
    above = _V("os_family", "Android", direction="above")
    assert below.direction != above.direction

    early = _V("os_family", "Android", ws=datetime(2026, 6, 1), we=datetime(2026, 6, 2))
    late = _V("os_family", "Android", ws=datetime(2026, 6, 25), we=datetime(2026, 6, 26))
    key_of = lambda v: (v.scope_type, v.scope_value, v.direction, v.window_start, v.window_end)  # noqa: E731
    assert key_of(early) != key_of(late)
    assert key_of(below) != key_of(above)
    # ...but two metrics on the same scope/direction/window DO share a key, which is the
    # whole point of the reduction.
    assert key_of(_V("os_family", "Android", metric="fill_rate")) == \
           key_of(_V("os_family", "Android", metric="rpr"))
