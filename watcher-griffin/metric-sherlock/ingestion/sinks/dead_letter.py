"""Rejected records + their full violation list -- never silently dropped."""

from .jsonl_sink import JsonlSink


class DeadLetterSink(JsonlSink):
    def __init__(self, out_dir: str):
        super().__init__(out_dir, suffix="rejected")
