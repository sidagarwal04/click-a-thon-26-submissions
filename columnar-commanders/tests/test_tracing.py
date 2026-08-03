"""The tracing layer's contract: it records reasoning, and it never breaks the
pipeline. Both are tested here without a running Langfuse."""

from __future__ import annotations

import logging

import pytest

from prism_ch import tracing


@pytest.fixture(autouse=True)
def _reset_tracing() -> None:
    tracing._client = None
    tracing._enabled = False


# --- the pipeline must survive tracing being unavailable ----------------------


def test_disabled_by_config_is_not_an_error(make_settings) -> None:
    assert tracing.init_tracing(make_settings(tracing_enabled=False)) is False
    assert tracing.is_enabled() is False


def test_full_run_works_with_tracing_off(make_settings) -> None:
    tracing.init_tracing(make_settings(tracing_enabled=False))

    with tracing.pipeline_run("t", spec_name="demo") as run:
        with tracing.agent_step("instrumentation", "design") as step:
            step.decision(what="ORDER BY (a, b)", why="a is the common predicate")
            step.sql("SELECT 1", purpose="probe", rows=1)
            step.score("confidence", 0.5)
            step.output({"ok": True})
        with tracing.llm_call("gen", model="m", prompt="p") as gen:
            gen.update(output="done")
        run.score("quality", 1.0)
        run.output({"ok": True})

    assert run.run_id
    assert run.trace_id is None


def test_sdk_failures_are_swallowed() -> None:
    """Whatever the SDK throws must not reach agent code."""

    def explode() -> None:
        raise RuntimeError("collector unreachable")

    assert tracing._safe(explode) is None


def test_broken_client_does_not_break_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenClient:
        def start_as_current_observation(self, **_: object) -> None:
            raise RuntimeError("boom")

        def start_as_current_span(self, **_: object) -> None:
            raise RuntimeError("boom")

        def get_current_trace_id(self) -> str:
            raise RuntimeError("boom")

        def flush(self) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(tracing, "_client", BrokenClient())
    monkeypatch.setattr(tracing, "_enabled", True)

    with tracing.pipeline_run("t", spec_name="demo") as run:
        with tracing.agent_step("analytics", "cut", context_version="v1") as step:
            step.decision(what="x", why="y")
    tracing.shutdown()

    assert run.run_id


def test_missing_sdk_degrades_quietly(monkeypatch: pytest.MonkeyPatch, make_settings) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "langfuse":
            raise ImportError("no langfuse")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert tracing.init_tracing(make_settings()) is False


# --- the recording contract ---------------------------------------------------


def test_decision_requires_a_reason(make_settings) -> None:
    """T6 is enforced by the signature: no `why`, no decision."""
    tracing.init_tracing(make_settings(tracing_enabled=False))
    with tracing.agent_step("context", "refresh") as step:
        with pytest.raises(TypeError):
            step.decision(what="something")  # type: ignore[call-arg]


def test_decisions_accumulate_with_reasoning(make_settings) -> None:
    tracing.init_tracing(make_settings(tracing_enabled=False))
    with tracing.agent_step("instrumentation", "design") as step:
        step.decision(what="a", why="because a", confidence=0.9, alternatives=["b"])
        step.decision(what="c", why="because c")

    assert [d.what for d in step.decisions] == ["a", "c"]
    assert all(d.why for d in step.decisions)
    assert step.decisions[0].as_dict()["alternatives"] == ["b"]


def test_analytics_without_context_version_warns(caplog: pytest.LogCaptureFixture, make_settings) -> None:
    """T7: a conclusion with no recorded context version is unauditable."""
    tracing.init_tracing(make_settings(tracing_enabled=False))
    with caplog.at_level(logging.WARNING, logger="prism_ch.tracing"):
        with tracing.agent_step("analytics", "segment_cut"):
            pass

    assert "context_version" in caplog.text


def test_other_agents_do_not_warn(caplog: pytest.LogCaptureFixture, make_settings) -> None:
    tracing.init_tracing(make_settings(tracing_enabled=False))
    with caplog.at_level(logging.WARNING, logger="prism_ch.tracing"):
        with tracing.agent_step("instrumentation", "design"):
            pass

    assert "context_version" not in caplog.text


def test_run_id_is_stable_when_supplied(make_settings) -> None:
    tracing.init_tracing(make_settings(tracing_enabled=False))
    with tracing.pipeline_run("t", spec_name="demo", run_id="spec6-final") as run:
        pass

    assert run.run_id == "spec6-final"


def test_unreachable_collector_disables_tracing(monkeypatch: pytest.MonkeyPatch, make_settings) -> None:
    """auth_check raising must disable tracing, not leave it half-on.

    A half-on client queues spans against a dead collector; the OTLP exporter
    then retries with backoff and stalls process shutdown.
    """
    class DeadClient:
        def auth_check(self) -> bool:
            raise OSError("Name or service not known")

    import types as _t
    fake = _t.ModuleType("langfuse")
    fake.get_client = lambda: DeadClient()  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "langfuse", fake)

    assert tracing.init_tracing(make_settings()) is False
    assert tracing.is_enabled() is False


def test_auth_check_returning_false_disables_tracing(monkeypatch: pytest.MonkeyPatch, make_settings) -> None:
    class RejectingClient:
        def auth_check(self) -> bool:
            return False

    import types as _t
    fake = _t.ModuleType("langfuse")
    fake.get_client = lambda: RejectingClient()  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "langfuse", fake)

    assert tracing.init_tracing(make_settings()) is False


# --- dimensions and metrics ---------------------------------------------------


def test_feature_and_surface_dimensions_are_exposed(make_settings) -> None:
    """Token spend must be sliceable by feature and by surface."""
    tracing.init_tracing(make_settings(tracing_enabled=False))
    seen = {}
    with tracing.pipeline_run("instrument", spec_name="s", surface="ui"):
        seen.update(tracing.current_dimensions())
    assert seen == {"feature": "instrument", "surface": "ui"}
    # reset after the run
    assert tracing.current_dimensions()["feature"] == "unknown"


def test_via_metadata_still_sets_the_surface(make_settings) -> None:
    tracing.init_tracing(make_settings(tracing_enabled=False))
    with tracing.pipeline_run("analyze", spec_name="s", via="mcp"):
        assert tracing.current_dimensions()["surface"] == "mcp"


def test_step_records_metrics_and_duration(make_settings) -> None:
    tracing.init_tracing(make_settings(tracing_enabled=False))
    with tracing.agent_step("analytics", "run_queries") as step:
        step.metrics_from(queries_run=6, queries_failed=1)
        step.metric("rows_returned", 42)

    assert step.metrics["queries_run"] == 6
    assert step.metrics["rows_returned"] == 42
    assert "duration_ms" in step.metrics


def test_duration_is_recorded_even_when_a_step_raises(make_settings) -> None:
    tracing.init_tracing(make_settings(tracing_enabled=False))
    step_ref = {}
    with pytest.raises(RuntimeError):
        with tracing.agent_step("instrumentation", "validate_ddl") as step:
            step_ref["s"] = step
            raise RuntimeError("rejected")
    assert "duration_ms" in step_ref["s"].metrics


def test_step_sql_reaches_the_live_progress_sink(make_settings) -> None:
    """The live UI's Activity log is driven entirely by the progress sink, not
    by Langfuse - a query pushed to ClickHouse must reach it too, or the log
    can never show "the query being executed", only step start/end."""
    tracing.init_tracing(make_settings(tracing_enabled=False))
    events: list[dict] = []
    token = tracing.set_progress_sink(events.append)
    try:
        with tracing.agent_step("analytics", "run_queries") as step:
            step.sql("SELECT count() FROM t", purpose="headline count")
            step.sql("SELECT count() FROM t", purpose="headline count", rows=1)
    finally:
        tracing.clear_progress_sink(token)

    sql_events = [e for e in events if e["type"] == "sql"]
    assert len(sql_events) == 2
    assert sql_events[0]["rows"] is None  # in flight, before the query returned
    assert sql_events[1]["rows"] == 1  # done, with the row count known
    assert all(e["query"] == "SELECT count() FROM t" for e in sql_events)
    assert all(e["agent"] == "analytics" and e["action"] == "run_queries" for e in sql_events)


def test_cost_is_computed_when_prices_are_configured(make_settings) -> None:
    """Langfuse reports $0.00 for models it has no price for, however many
    tokens it recorded - so cost is computed here instead."""
    s = make_settings(llm_price_input=0.10, llm_price_output=0.40)
    cost = s.cost_details({"input": 1_000_000, "output": 500_000})
    assert cost["input"] == 0.10
    assert cost["output"] == 0.20
    assert cost["total"] == 0.30


def test_no_prices_means_no_cost_override(make_settings) -> None:
    """Empty prices fall back to Langfuse's own model registry."""
    assert make_settings().cost_details({"input": 100, "output": 50}) == {}


def test_model_registration_uses_sdk_field_names() -> None:
    created = []

    class Models:
        def create(self, *, request: object) -> None:
            created.append(request)

    class API:
        models = Models()

    class Client:
        api = API()

    tracing._register_models(Client())

    assert created
    request = created[0]
    assert request.model_name
    assert request.match_pattern.startswith("(?i)^")
    assert request.input_price is not None


def test_llm_failure_marks_generation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    updates = []

    class Span:
        def update(self, **values: object) -> None:
            updates.append(values)

    class CM:
        def __enter__(self) -> Span:
            return Span()

        def __exit__(self, *_: object) -> None:
            return None

    class Client:
        def start_as_current_observation(self, **_: object) -> CM:
            return CM()

    monkeypatch.setattr(tracing, "_client", Client())
    monkeypatch.setattr(tracing, "_enabled", True)

    with pytest.raises(RuntimeError), tracing.llm_call("gen", model="m", prompt="p"):
        raise RuntimeError("provider failed")

    assert updates == [{"level": "ERROR", "status_message": "provider failed"}]


def test_generation_inherits_active_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    created = []

    class Span:
        def update(self, **_: object) -> None:
            return None

    class CM:
        def __enter__(self) -> Span:
            return Span()

        def __exit__(self, *_: object) -> None:
            return None

    class Client:
        def start_as_current_observation(self, **values: object) -> CM:
            created.append(values)
            return CM()

    monkeypatch.setattr(tracing, "_client", Client())
    monkeypatch.setattr(tracing, "_enabled", True)

    with tracing.agent_step("analytics", "interpret"):
        with tracing.llm_call("completion", model="m", prompt="p"):
            pass

    generation = next(item for item in created if item.get("as_type") == "generation")
    assert generation["name"] == "agent:analytics"
    assert generation["metadata"]["agent"] == "analytics"
    assert generation["metadata"]["operation"] == "completion"
    assert tracing._active_agent.get() is None
