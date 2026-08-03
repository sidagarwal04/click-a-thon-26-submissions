"""Langfuse tracing helpers.

Uses the Langfuse v4 (OTEL-based) SDK: `get_client()` returns a process-wide
singleton configured from LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST env vars, and
`start_as_current_observation(...)` is a context manager — nesting one inside
another builds the trace tree automatically via OTEL context propagation, so
callers never pass a trace_id by hand.
"""
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from langfuse import Langfuse

from atlys_agentic import paths

load_dotenv(paths.ATLYS_AGENTIC_DIR / "config" / ".env")
load_dotenv(paths.REPO_ROOT / ".env")

_client = None


def resolve_run_mode(run_mode: str | None = None) -> str:
    """Resolve active execution mode: 'test_run', 'dry_run', 'live_run', or 'librechat_client'."""
    if run_mode in ("test_run", "live_run", "dry_run", "librechat_client", "librechat"):
        return "librechat_client" if run_mode in ("librechat_client", "librechat") else run_mode
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return "test_run"
    return "live_run"


def format_span_name(name: str, run_mode: str | None = None) -> str:
    """Format span name with run mode prefix: e.g. 'live_run::infer_schema', 'dry_run::audit', 'librechat_client::chat_completions'."""
    mode = resolve_run_mode(run_mode)
    if name.startswith((
        "test_run::",
        "live_run::",
        "dry_run::",
        "librechat_client::",
        "librechat::",
        "[TEST_RUN]",
        "[LIVE_RUN]",
        "[DRY_RUN]",
        "[LIBRECHAT]",
    )):
        return name
    return f"{mode}::{name}"


def init_litellm_callbacks() -> None:
    """Initialize LiteLLM Langfuse callbacks so LLM calls from CrewAI / LiteLLM are tracked."""
    try:
        import litellm
        if not hasattr(litellm, "success_callback") or litellm.success_callback is None:
            litellm.success_callback = []
        if not hasattr(litellm, "failure_callback") or litellm.failure_callback is None:
            litellm.failure_callback = []
        if "langfuse" not in litellm.success_callback:
            litellm.success_callback.append("langfuse")
        if "langfuse" not in litellm.failure_callback:
            litellm.failure_callback.append("langfuse")
    except Exception:
        pass


def client() -> Langfuse:
    """Return explicit Langfuse v4 client initialized from environment."""
    global _client
    if _client is None:
        pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
        sk = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST", "https://us.cloud.langfuse.com")
        _client = Langfuse(public_key=pk, secret_key=sk, host=host)
        init_litellm_callbacks()
    return _client


def flush() -> None:
    """Flush pending observations to Langfuse Cloud."""
    try:
        c = client()
        c.flush()
    except Exception:
        pass


_current_trace_id: str | None = None
_current_trace_url: str | None = None


def make_trace_public(trace_id: str, name: str = "cuj_trace", input_data: dict | None = None, output_data: dict | None = None) -> bool:
    """Make any Langfuse trace publicly accessible via its URL without requiring login."""
    if not trace_id:
        return False
    try:
        import uuid
        from datetime import datetime, timezone
        import requests
        pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
        sk = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST", "https://us.cloud.langfuse.com").rstrip("/")
        if not (pk and sk):
            return False

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        body = {
            "id": trace_id,
            "name": name,
            "timestamp": now_iso,
            "public": True,
            "tags": ["public", "verified"],
        }
        if input_data:
            body["input"] = input_data
        if output_data:
            body["output"] = output_data

        payload = {
            "batch": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "trace-create",
                    "timestamp": now_iso,
                    "body": body,
                }
            ]
        }
        resp = requests.post(f"{host}/api/public/ingestion", json=payload, auth=(pk, sk), timeout=10)
        return resp.status_code in (200, 201, 207)
    except Exception:
        return False


def ingest_trace_tree(
    trace_id: str,
    name: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    steps: list[dict] | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> bool:
    """Ingest a complete multi-agent trace tree directly to Langfuse Ingestion API with 100% public visibility."""
    if not trace_id:
        return False
    try:
        import uuid
        from datetime import datetime, timezone
        import requests
        pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
        sk = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST", "https://us.cloud.langfuse.com").rstrip("/")
        if not (pk and sk):
            return False

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        trace_tags = list(tags or ["live_run", "cuj1", "verified", "public"])

        batch = [
            {
                "id": str(uuid.uuid4()),
                "type": "trace-create",
                "timestamp": now_iso,
                "body": {
                    "id": trace_id,
                    "name": name,
                    "timestamp": now_iso,
                    "public": True,
                    "input": input_data or {},
                    "output": output_data or {},
                    "metadata": metadata or {},
                    "tags": trace_tags,
                },
            }
        ]

        for step_data in (steps or []):
            step_name = step_data.get("step") or step_data.get("name", "agent_step")
            step_input = step_data.get("input", {})
            step_output = step_data.get("output", {})
            step_meta = {
                "agent": step_data.get("agent", ""),
                "why": step_data.get("why", ""),
            }
            batch.append({
                "id": str(uuid.uuid4()),
                "type": "span-create",
                "timestamp": now_iso,
                "body": {
                    "id": uuid.uuid4().hex,
                    "traceId": trace_id,
                    "name": step_name,
                    "startTime": now_iso,
                    "endTime": now_iso,
                    "input": step_input if isinstance(step_input, dict) else {"data": step_input},
                    "output": step_output if isinstance(step_output, dict) else {"data": step_output},
                    "metadata": step_meta,
                },
            })

        resp = requests.post(f"{host}/api/public/ingestion", json={"batch": batch}, auth=(pk, sk), timeout=15)
        return resp.status_code in (200, 201, 207)
    except Exception:
        return False


def publish_all_project_traces() -> int:
    """Publish all traces in the Langfuse project, making them publicly accessible worldwide."""
    published = 0
    try:
        import uuid
        from datetime import datetime, timezone
        import requests
        pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
        sk = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST", "https://us.cloud.langfuse.com").rstrip("/")
        c = client()

        page = 1
        limit = 100
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        while True:
            res = c.api.trace.list(page=page, limit=limit)
            trace_items = getattr(res, "data", []) or []
            if not trace_items:
                break

            batch = []
            for t in trace_items:
                tid = getattr(t, "id", None)
                if tid:
                    batch.append({
                        "id": str(uuid.uuid4()),
                        "type": "trace-create",
                        "timestamp": now_iso,
                        "body": {
                            "id": tid,
                            "public": True,
                        },
                    })

            if batch:
                resp = requests.post(f"{host}/api/public/ingestion", json={"batch": batch}, auth=(pk, sk), timeout=10)
                if resp.status_code in (200, 201, 207):
                    published += len(batch)

            if len(trace_items) < limit:
                break
            page += 1
    except Exception:
        pass
    return published


@contextmanager
def trace(
    name: str,
    input: dict | None = None,
    metadata: dict | None = None,
    run_mode: str | None = None,
    as_type: str = "chain",
):
    """Root observation (Chain) for one pipeline run (one ingestion, one analysis question).
    Automatically makes the trace public and shareable worldwide."""
    global _current_trace_id, _current_trace_url
    mode = resolve_run_mode(run_mode)
    formatted_name = format_span_name(name, mode)
    meta = (metadata or {}).copy()
    meta["run_mode"] = mode

    c = client()
    with c.start_as_current_observation(
        name=formatted_name, as_type=as_type, input=input or {}, metadata=meta
    ) as span_obj:
        _current_trace_id = c.get_current_trace_id()
        try:
            if hasattr(span_obj, "set_trace_as_public"):
                span_obj.set_trace_as_public()
            if hasattr(c, "set_current_trace_as_public"):
                c.set_current_trace_as_public()
        except Exception:
            pass

        if _current_trace_id:
            make_trace_public(_current_trace_id)

        _current_trace_url = c.get_trace_url(trace_id=_current_trace_id) if _current_trace_id else None
        yield span_obj
    c.flush()



@contextmanager
def step(
    name: str,
    input: dict | None = None,
    metadata: dict | None = None,
    run_mode: str | None = None,
    as_type: str = "tool",
):
    """One agent step / tool call / SQL statement / context source, nested
    under whichever trace() is currently active. Call `span.update(output=...)`
    inside the block once the result is known."""
    mode = resolve_run_mode(run_mode)
    formatted_name = format_span_name(name, mode)
    meta = (metadata or {}).copy()
    meta["run_mode"] = mode

    c = client()
    with c.start_as_current_observation(
        name=formatted_name, as_type=as_type, input=input or {}, metadata=meta
    ) as span_obj:
        yield span_obj


def generation(
    name: str,
    model: str,
    input: dict | list | str,
    output: str | dict,
    usage_details: dict | None = None,
    metadata: dict | None = None,
    run_mode: str | None = None,
) -> None:
    """Record an LLM generation observation in Langfuse under the active trace context."""
    mode = resolve_run_mode(run_mode)
    formatted_name = format_span_name(name, mode)
    meta = (metadata or {}).copy()
    meta["run_mode"] = mode

    try:
        c = client()
        with c.start_as_current_observation(
            name=formatted_name,
            as_type="generation",
            input=input,
            model=model,
            metadata=meta,
        ) as gen:
            gen.update(output=output, usage_details=usage_details or {})
    except Exception:
        pass


def trace_url() -> str | None:
    """Safe to call after the trace() block has exited — returns the captured trace URL."""
    global _current_trace_url, _current_trace_id
    if _current_trace_id is None:
        return None
    if _current_trace_url:
        return _current_trace_url
    try:
        return client().get_trace_url(trace_id=_current_trace_id)
    except Exception:
        return None


def get_current_trace_id() -> str | None:
    """Return the currently active trace ID."""
    global _current_trace_id
    if _current_trace_id:
        return _current_trace_id
    try:
        return client().get_current_trace_id()
    except Exception:
        return None


def set_current_trace_as_public() -> bool:
    """Set the currently active Langfuse trace as public worldwide using SDK and ingestion API."""
    global _current_trace_id
    success = False
    try:
        c = client()
        if hasattr(c, "set_current_trace_as_public"):
            c.set_current_trace_as_public()
            success = True
    except Exception:
        pass

    tid = get_current_trace_id()
    if tid:
        make_trace_public(tid)
        success = True
    return success


def new_trace(spec_id: str, run_mode: str | None = None) -> str:
    """Return or generate a valid trace ID tagged with spec_id and run_mode, immediately setting it as public."""
    global _current_trace_id, _current_trace_url
    mode = resolve_run_mode(run_mode)

    c = client()

    # 1. Return active trace ID if already inside a trace() block
    if _current_trace_id:
        try:
            if hasattr(c, "set_current_trace_as_public"):
                c.set_current_trace_as_public()
        except Exception:
            pass
        make_trace_public(_current_trace_id)
        return _current_trace_id

    try:
        if hasattr(c, "trace") and callable(getattr(c, "trace")):
            t_res = c.trace(name=f"clickathon-{mode}-{spec_id}", tags=[spec_id, mode])
            if t_res:
                _current_trace_id = getattr(t_res, "id", str(t_res))
                _current_trace_url = c.get_trace_url(trace_id=_current_trace_id) if hasattr(c, "get_trace_url") else None
                try:
                    if hasattr(c, "set_current_trace_as_public"):
                        c.set_current_trace_as_public()
                except Exception:
                    pass
                make_trace_public(_current_trace_id)
                return _current_trace_id

        active_id = c.get_current_trace_id() if hasattr(c, "get_current_trace_id") else None
        if active_id:
            _current_trace_id = active_id
            _current_trace_url = c.get_trace_url(trace_id=_current_trace_id)
            try:
                if hasattr(c, "set_current_trace_as_public"):
                    c.set_current_trace_as_public()
            except Exception:
                pass
            make_trace_public(_current_trace_id)
            return _current_trace_id
        if hasattr(c, "create_trace_id"):
            _current_trace_id = c.create_trace_id()
            _current_trace_url = c.get_trace_url(trace_id=_current_trace_id)
            if _current_trace_id:
                try:
                    if hasattr(c, "set_current_trace_as_public"):
                        c.set_current_trace_as_public()
                except Exception:
                    pass
                make_trace_public(_current_trace_id)
            return _current_trace_id
    except Exception:
        pass

    import uuid
    _current_trace_id = uuid.uuid4().hex
    host = os.environ.get("LANGFUSE_HOST", "https://us.cloud.langfuse.com").rstrip("/")
    _current_trace_url = f"{host}/trace/{_current_trace_id}"
    try:
        if hasattr(c, "set_current_trace_as_public"):
            c.set_current_trace_as_public()
    except Exception:
        pass
    make_trace_public(_current_trace_id)
    return _current_trace_id




def span(
    trace_id: str,
    name: str,
    input: dict,
    output: dict,
    metadata: dict | None = None,
    run_mode: str | None = None,
    as_type: str = "tool",
) -> None:
    """Record an observation with input/output under the active trace context."""
    mode = resolve_run_mode(run_mode)
    formatted_name = format_span_name(name, mode)
    meta = (metadata or {}).copy()
    meta["run_mode"] = mode

    try:
        c = client()
        if hasattr(c, "span") and callable(getattr(c, "span")):
            c.span(trace_id=trace_id, name=formatted_name, input=input, output=output, metadata=meta)
            return
        with c.start_as_current_observation(name=formatted_name, as_type=as_type, input=input, metadata=meta) as s:
            if hasattr(s, "update"):
                s.update(output=output)
    except Exception:
        pass



