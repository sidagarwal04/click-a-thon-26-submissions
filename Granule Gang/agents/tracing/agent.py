"""
Tracing Agent
Langfuse v4 integration for full pipeline tracing.
"""

import sys
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Optional

from langfuse import Langfuse

import agents.config


class TracingAgent:

    def __init__(self):
        self.enabled = False
        self.client = None
        self.current_trace_id: Optional[str] = None
        self._trace_ctx = None

        try:
            _, lf_config, _ = agents.config.get_config()
        except Exception as e:
            print(f"[Tracing Notice] Could not load Langfuse config: {e}")
            return

        if lf_config.enabled and lf_config.public_key and lf_config.secret_key:
            try:
                self.client = Langfuse(
                    public_key=lf_config.public_key,
                    secret_key=lf_config.secret_key,
                    base_url=lf_config.host,
                )
                self.enabled = True
            except Exception as e:
                print(f"[Tracing Notice] Could not initialize Langfuse client: {e}")

    def _active(self) -> bool:
        return bool(self.enabled and self.client)

    def start_trace(self, name: str, metadata: Dict[str, Any] = None) -> str:
        """Open a root observation that stays active until end_span()/flush()."""
        trace_id = str(uuid.uuid4())
        self.current_trace_id = trace_id

        if self._active():
            try:
                self._trace_ctx = self.client.start_as_current_observation(
                    name=name,
                    as_type="agent",
                    input=metadata or {},
                    metadata=metadata or {},
                    end_on_exit=False,
                )
                self._trace_ctx.__enter__()
            except Exception as e:
                print(f"[Tracing Warning] start_trace '{name}' failed: {e}")
                self._trace_ctx = None

        return trace_id

    def end_span(self, trace_id: str, status: str = "success", error: str = None):
        """End the root observation opened by start_trace(), if it's still the active one."""
        if trace_id != self.current_trace_id or self._trace_ctx is None:
            return

        if self._active():
            try:
                self.client.update_current_span(
                    metadata={"status": status, **({"error": error} if error else {})},
                    level="ERROR" if status == "error" else "DEFAULT",
                    status_message=error,
                )
            except Exception as e:
                print(f"[Tracing Warning] end_span failed: {e}")

        try:
            self._trace_ctx.__exit__(None, None, None)
        except Exception:
            pass
        self._trace_ctx = None
        self.current_trace_id = None

    @contextmanager
    def trace_span(self, name: str, input_data: Dict[str, Any] = None, metadata: Dict[str, Any] = None):
        """Context manager for a nested span; safe to use bare (`with tracer.trace_span(...):`)."""
        if not self._active():
            yield None
            return

        try:
            cm = self.client.start_as_current_observation(
                name=name,
                as_type="span",
                input=input_data or {},
                metadata=metadata or {},
            )
            span = cm.__enter__()
        except Exception as e:
            print(f"[Tracing Warning] Span '{name}' failed to start: {e}")
            yield None
            return

        try:
            yield span
        except BaseException:
            cm.__exit__(*sys.exc_info())
            raise
        else:
            cm.__exit__(None, None, None)

    def log_generation(self, name: str, model: str, prompt: str, completion: str, metadata: Dict[str, Any] = None):
        if not self._active():
            return
        try:
            with self.client.start_as_current_observation(
                name=name,
                as_type="generation",
                input={"prompt": prompt},
                output={"completion": completion},
                metadata={**(metadata or {}), "model": model},
            ):
                pass
        except Exception as e:
            print(f"[Tracing Warning] log_generation '{name}' failed: {e}")

    def flush(self):
        if self._trace_ctx is not None:
            try:
                self._trace_ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._trace_ctx = None
            self.current_trace_id = None

        if self._active():
            try:
                self.client.flush()
            except Exception as e:
                print(f"[Tracing Warning] flush failed: {e}")

    def shutdown(self):
        if self.client:
            try:
                self.client.shutdown()
            except Exception:
                pass


_default_tracer: Optional[TracingAgent] = None


def get_tracer() -> TracingAgent:
    global _default_tracer
    if _default_tracer is None:
        _default_tracer = TracingAgent()
    return _default_tracer


def set_tracer(tracer: TracingAgent):
    global _default_tracer
    _default_tracer = tracer
