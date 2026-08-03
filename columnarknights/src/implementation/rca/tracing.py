"""Traceability for the investigation pipeline.

Every stage of an investigation (detect -> decompose -> drill-down queries ->
narrate) is wrapped in a span. Two things happen regardless of whether
Langfuse credentials are configured:

  1. A local JSON trace tree is always written to traces/, so "what was
     checked, in what order, with what inputs/outputs" is on disk and
     diffable even with no external service.
  2. If LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY are set, the same span tree
     is mirrored into Langfuse (nested automatically, since spans are opened
     as nested `with` blocks and Langfuse's v3 SDK tracks nesting via the
     current OpenTelemetry context) so it can be inspected in the Langfuse UI.
"""

import contextlib
import json
import time
from dataclasses import is_dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .config import settings


def _json_default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    return str(o)


class SpanHandle:
    def __init__(self, node: dict, lf_obs=None):
        self._node = node
        self._lf_obs = lf_obs

    def set_output(self, output: Any) -> None:
        self._node["output"] = output
        if self._lf_obs is not None:
            try:
                self._lf_obs.update(output=json.loads(json.dumps(output, default=_json_default)))
            except Exception:
                pass


class Tracer:
    def __init__(self, name: str, input: Any = None, trace_dir: str = "traces"):
        self.name = name
        self._root: dict = {"name": name, "input": input, "output": None, "children": []}
        self._stack: list[dict] = [self._root]
        self._lf_obs_stack: list[Any] = []
        self._lf_cm_stack: list[Any] = []
        self.trace_dir = Path(trace_dir)
        self._langfuse = None
        self.trace_url: str | None = None
        self.local_trace_path: Path | None = None

        if settings.langfuse_public_key and settings.langfuse_secret_key:
            from langfuse import Langfuse

            self._langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )

    def __enter__(self) -> "Tracer":
        self._root["start"] = time.time()
        if self._langfuse is not None:
            cm = self._langfuse.start_as_current_observation(
                name=self.name, as_type="span", input=self._root["input"]
            )
            obs = cm.__enter__()
            self._lf_cm_stack.append(cm)
            self._lf_obs_stack.append(obs)
            try:
                self.trace_url = self._langfuse.get_trace_url()
            except Exception:
                self.trace_url = None
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._root["end"] = time.time()
        self._root["duration_s"] = round(self._root["end"] - self._root["start"], 4)
        if self._lf_cm_stack:
            if self._root.get("output") is not None:
                try:
                    self._lf_obs_stack[-1].update(output=self._root["output"])
                except Exception:
                    pass
            self._lf_cm_stack[-1].__exit__(exc_type, exc, tb)
        if self._langfuse is not None:
            self._langfuse.flush()
        self._dump()

    def set_output(self, output: Any) -> None:
        self._root["output"] = output

    @contextlib.contextmanager
    def span(self, name: str, input: Any = None, as_type: str = "span", model: str | None = None):
        node: dict = {"name": name, "input": input, "output": None, "children": [], "start": time.time()}
        self._stack[-1].setdefault("children", []).append(node)
        self._stack.append(node)

        lf_cm = None
        obs = None
        if self._langfuse is not None:
            kwargs: dict = {"name": name, "as_type": as_type, "input": input}
            if model:
                kwargs["model"] = model
            lf_cm = self._langfuse.start_as_current_observation(**kwargs)
            obs = lf_cm.__enter__()

        handle = SpanHandle(node, obs)
        try:
            yield handle
        finally:
            node["end"] = time.time()
            node["duration_s"] = round(node["end"] - node["start"], 4)
            if lf_cm is not None:
                lf_cm.__exit__(None, None, None)
            self._stack.pop()

    def _dump(self) -> Path:
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        path = self.trace_dir / f"{int(self._root['start'])}_{self.name}.json"
        payload = json.loads(json.dumps(self._root, default=_json_default))
        if self.trace_url:
            payload["langfuse_trace_url"] = self.trace_url
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        self.local_trace_path = path
        return path
