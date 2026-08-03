"""Orchestrates source -> transform -> validate -> sink, agnostic to whether
the source is a finite batch or a never-ending live stream.

Flushes whenever a micro-batch hits BATCH_MAX_ROWS or BATCH_MAX_SECONDS
elapses, instead of waiting for the source iterator to exhaust -- required
for streaming sources, which may never exhaust. A KeyboardInterrupt (Ctrl+C
against a live stream) is treated as a clean stop: flush whatever's buffered
and return, never lose already-processed records.

source.records() runs on a background thread feeding a queue, and the main
loop does a bounded queue.get() rather than iterating the generator directly
-- a plain `for raw in source.records()` would block on the *next record*,
so a quiet stream (nothing new arriving) would never reach the time-based
flush check below it and buffered-but-unflushed rows would sit invisible
until more data showed up.
"""

import queue
import threading
import time
from typing import Any, Dict

import pydantic

from . import schemas, transformers, validators
from .config import Config
from .sinks import Sink
from .sources import Source

_SENTINEL = object()


class IngestionPipeline:
    def __init__(
        self,
        source: Source,
        valid_sink: Sink,
        dead_letter_sink: Sink,
        entity: str,
        cfg: Config,
    ):
        if entity not in schemas.MODEL_BY_ENTITY:
            raise ValueError(f"unknown entity '{entity}'")
        self.source = source
        self.valid_sink = valid_sink
        self.dead_letter_sink = dead_letter_sink
        self.entity = entity
        self.cfg = cfg
        self.model_cls = schemas.MODEL_BY_ENTITY[entity]

    def run(self) -> Dict[str, Any]:
        stats = {"accepted": 0, "rejected": 0, "skipped": 0}
        extra_fields_seen: set = set()
        valid_buf = []
        dead_buf = []
        last_flush = time.monotonic()

        record_queue: "queue.Queue" = queue.Queue(maxsize=1000)
        producer_errors = []

        def _produce() -> None:
            try:
                for raw in self.source.records():
                    record_queue.put(raw)
            except Exception as exc:  # noqa: BLE001 -- surfaced to the main thread below
                producer_errors.append(exc)
            finally:
                record_queue.put(_SENTINEL)

        producer = threading.Thread(target=_produce, daemon=True)
        producer.start()

        try:
            while True:
                try:
                    item = record_queue.get(timeout=self.cfg.BATCH_MAX_SECONDS)
                except queue.Empty:
                    item = None  # nothing new arrived this interval -- fall through to the time check below

                if item is _SENTINEL:
                    break
                if item is not None:
                    outcome, payload, extra_fields = self._process(item)
                    extra_fields_seen.update(extra_fields)
                    if outcome == "skipped":
                        stats["skipped"] += 1
                    elif outcome == "rejected":
                        dead_buf.append(payload)
                        stats["rejected"] += 1
                    else:
                        valid_buf.append(payload)
                        stats["accepted"] += 1

                now = time.monotonic()
                due_by_size = len(valid_buf) + len(dead_buf) >= self.cfg.BATCH_MAX_ROWS
                due_by_time = now - last_flush >= self.cfg.BATCH_MAX_SECONDS
                if valid_buf or dead_buf:
                    if due_by_size or due_by_time:
                        self._flush(valid_buf, dead_buf)
                        valid_buf, dead_buf = [], []
                        last_flush = now
        except KeyboardInterrupt:
            pass
        finally:
            self._flush(valid_buf, dead_buf)

        if producer_errors:
            raise producer_errors[0]
        stats["extra_fields_seen"] = sorted(extra_fields_seen)
        return stats

    def _process(self, raw: Dict[str, Any]):
        cleaned, transform_errors, extra_fields = transformers.normalize(self.entity, raw)

        if cleaned is None:
            if transform_errors:
                return "rejected", {"record": raw, "errors": transform_errors}, extra_fields
            return "skipped", None, extra_fields

        if transform_errors:
            return "rejected", {"record": raw, "errors": transform_errors}, extra_fields

        model = None
        schema_errors = []
        try:
            model = self.model_cls(**cleaned)
        except pydantic.ValidationError as exc:
            schema_errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]

        business_errors = []
        if model is not None:
            business_errors = validators.validate(self.entity, model.model_dump(), self.cfg)

        all_errors = schema_errors + business_errors
        if all_errors:
            return "rejected", {"record": raw, "errors": all_errors}, extra_fields
        return "accepted", model.model_dump(), extra_fields

    def _flush(self, valid_buf, dead_buf) -> None:
        if valid_buf:
            self.valid_sink.write(self.entity, valid_buf)
        if dead_buf:
            self.dead_letter_sink.write(self.entity, dead_buf)
