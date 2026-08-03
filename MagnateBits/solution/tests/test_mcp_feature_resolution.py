"""Which feature does `ask` analyse when the caller doesn't say?

The bug this pins: `ask(question)` with no `feature_slug` used to take
`tables[0]` -- whichever feature table sorted first alphabetically -- regardless of
what was asked. A question about one feature was answered about a different one,
fluently and with correctly-computed numbers from the wrong table. Internal
consistency is exactly what made it dangerous: nothing in the output looked wrong.

The list also contains the eval harness's synthetic topologies, so the silent
default could hand a PM an analysis of a mock fixture.

Ranking is data-driven (feature names + their live column names, inverse-frequency
weighted), so no feature is named in the resolver and an unseen spec ranks on the
same footing -- `tests/test_generalization.py` enforces that separately.
"""

from __future__ import annotations

import pytest

import atlys_mcp.server as server


@pytest.fixture(scope="module")
def ch():
    from ch import CH

    try:
        client = CH()
        client.run_select("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"ClickHouse not reachable: {exc}")
    if not [t for t in client.list_tables() if t.startswith("f_") and t.endswith("_events")]:
        pytest.skip("no instrumented feature tables to resolve against")
    return client


# --------------------------------------------------------------------------
# scoring -- pure, no ClickHouse
# --------------------------------------------------------------------------

TOKENS = {
    "alpha_flow": {"alpha", "flow", "widget_id", "latency_ms", "event", "user_id"},
    "beta_thing": {"beta", "thing", "basket_id", "event", "user_id"},
}


def test_a_token_unique_to_one_feature_decides_it() -> None:
    ranked = server._rank_features("what is the widget_id doing", TOKENS)
    assert ranked[0][0] == "alpha_flow"
    assert ranked[0][1] > ranked[1][1]


def test_tokens_shared_by_every_feature_decide_nothing() -> None:
    """`event` and `user_id` are on both, so a question naming only those is a tie."""
    ranked = server._rank_features("group by user_id per event", TOKENS)
    assert ranked[0][1] == pytest.approx(ranked[1][1]), "shared tokens must not break the tie"


def test_dotted_json_path_matches_the_flattened_column() -> None:
    """A PM writes `payment.latency_ms`; the column is `payment_latency_ms`."""
    ranked = server._rank_features("how bad is latency.ms here", TOKENS)
    assert ranked[0][0] == "alpha_flow"


def test_very_short_tokens_are_not_evidence() -> None:
    """`os`/`id` would otherwise match half the English language."""
    assert server._norm("os") in server._norm("what about os and ios")
    ranked = server._rank_features("os", {"a_x": {"os", "aaa"}, "b_y": {"bbb"}})
    assert ranked[0][1] == 0.0, "sub-3-char tokens must contribute nothing"


# --------------------------------------------------------------------------
# resolution -- against the live schema
# --------------------------------------------------------------------------


def test_explicit_slug_is_honoured(ch) -> None:
    slugs = sorted(server._feature_tokens(ch))
    slug, why = server._resolve_feature(ch, "anything at all", slugs[0])
    assert slug == slugs[0]
    assert why == "explicit"


def test_unknown_explicit_slug_refuses_rather_than_falling_back(ch) -> None:
    with pytest.raises(server._Ambiguous):
        server._resolve_feature(ch, "anything", "definitely_not_a_real_feature")


def test_question_naming_no_feature_refuses_instead_of_guessing(ch) -> None:
    """THE regression: this used to silently return the alphabetically-first
    feature and answer confidently about it."""
    with pytest.raises(server._Ambiguous) as exc:
        server._resolve_feature(ch, "how is it going?", "")
    assert exc.value.available, "a refusal must tell the caller what it could have asked for"


def test_question_naming_a_features_own_column_resolves_to_it(ch) -> None:
    """Pick a column unique to one feature straight from the live schema, put it in
    a question, and require the resolver to land on that feature -- without this
    test naming any feature itself."""
    tokens = server._feature_tokens(ch)
    carriers: dict[str, int] = {}
    for toks in tokens.values():
        for t in toks:
            carriers[t] = carriers.get(t, 0) + 1
    target = next(
        (s for s, toks in sorted(tokens.items())
         if any(carriers[t] == 1 and len(t) >= 6 for t in toks)),
        None,
    )
    if target is None:
        pytest.skip("no feature has a column unique to it in this database")
    unique_col = next(t for t in sorted(tokens[target]) if carriers[t] == 1 and len(t) >= 6)

    slug, why = server._resolve_feature(ch, f"break down {unique_col} by day", "")
    assert slug == target
    assert "inferred" in why
