"""Appends accepted records to a local JSONL file, one file per entity."""

import json
import math
import os
from typing import Any, Dict, List

from . import Sink


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively replace non-finite floats (NaN/Infinity) with None.

    json.dumps happily emits the non-standard `NaN`/`Infinity` tokens for
    these (it never calls `default` for floats it already knows how to
    encode), which a strict JSON parser downstream would choke on. A raw
    dead-lettered record can carry these straight from a source library
    (e.g. pandas pads a short CSV row with NaN) -- sanitize unconditionally
    so every line this sink writes is always valid JSON.
    """
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


class JsonlSink(Sink):
    def __init__(self, out_dir: str, suffix: str = "valid"):
        self.out_dir = out_dir
        self.suffix = suffix
        os.makedirs(self.out_dir, exist_ok=True)

    def write(self, entity: str, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        path = os.path.join(self.out_dir, f"{entity}.{self.suffix}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(_sanitize_for_json(row), default=str) + "\n")
