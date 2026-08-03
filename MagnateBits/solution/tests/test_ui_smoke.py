"""The console must render under a REAL Streamlit runtime, not just import cleanly.

Why AppTest and not a plain function call: importing `ui/app.py` and invoking each view
in "bare mode" runs the code but registers no element ids, so a whole class of
Streamlit-only failure is invisible there. That is not hypothetical -- it shipped.
`_evidence_chain` keyed its "Run it now" button on run_id+query_name, but two findings
in one run legitimately cite the SAME query, so the page died with
StreamlitDuplicateElementKey. Bare-mode checks passed it; a user hit it immediately.

Scope, stated honestly: `AppTest.switch_page` only navigates FILE-based pages, so it
cannot reach the `st.navigation` function-pages this app uses. These tests therefore
cover the landing page (Insights -- the most element-dense one, and where the bug was)
plus a direct duplicate-key assertion. The other pages are covered by
`test_every_view_function_is_callable`, which is weaker but still catches import and
signature breakage.

Read-only against whatever is in ClickHouse, and asserting "renders without exception"
rather than specific content, so they stay meaningful on an empty database (every page
has a first-class empty state) and on a full one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "ui" / "app.py"


def _apptest():
    pytest.importorskip("streamlit.testing.v1", reason="streamlit testing API unavailable")
    from streamlit.testing.v1 import AppTest

    if not APP.exists():
        pytest.skip("ui/app.py not found")
    return AppTest.from_file(str(APP), default_timeout=180)


def _fail_text(at) -> str:
    return "\n".join(str(e.value)[:600] for e in at.exception)


def test_landing_page_renders_under_a_real_runtime() -> None:
    at = _apptest()
    at.run()
    assert not at.exception, f"landing page raised:\n{_fail_text(at)}"


def test_no_duplicate_widget_keys() -> None:
    """The shipped regression: Insights builds one button per cited query per finding,
    and findings routinely cite the same query."""
    at = _apptest()
    at.run()
    assert not at.exception, f"landing page raised:\n{_fail_text(at)}"
    keys = [w.key for w in list(at.button) + list(at.selectbox) + list(at.checkbox) if w.key]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert not dupes, f"duplicate widget keys: {dupes}"


def test_every_view_function_is_callable() -> None:
    """Weaker than a render, but catches import/signature breakage on the pages
    AppTest cannot navigate to."""
    import importlib
    import sys

    sys.path.insert(0, str(APP.parent.parent))
    mod = importlib.import_module("ui.app")
    for name in (
        "view_insights", "view_all_findings", "view_flow", "view_schema_history",
        "view_context", "view_runs", "view_run", "view_chat",
    ):
        assert callable(getattr(mod, name, None)), f"{name} missing or not callable"


def test_trace_urls_use_the_linkable_route() -> None:
    """`/trace/<id>` is not a real Langfuse route -- it 307s and dead-ends. The console
    route is `/project/<project_id>/traces/<id>`. This broke every "no trace, no credit"
    link written into artifacts and pipeline_runs before it was caught."""
    import sys

    sys.path.insert(0, str(APP.parent.parent))
    import tracing

    url = tracing.trace_url_for("deadbeef")
    if url and url != tracing.HOST:
        assert "/traces/deadbeef" in url, url
        assert "/project/" in url, url
        assert "/trace/deadbeef" not in url.replace("/traces/", "/"), url
    assert tracing.trace_url_for("") == ""
