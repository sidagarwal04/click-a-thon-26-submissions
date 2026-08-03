"""The Source adapter contract — tool-agnostic on purpose.

A Source's `records()` generator may terminate after a fixed set of rows
(batch: a file, an export dump) or run indefinitely, blocking between yields
as new data arrives (streaming: a live feed). pipeline.py consumes either
kind identically and never needs to know which one it's driving.

Kafka, Kinesis, Pub/Sub, RabbitMQ, a webhook receiver, or a batch file drop
all plug in here the same way: implement `records()` to yield one raw dict
per record. Nothing in transformers.py, validators.py, or pipeline.py knows
or cares where a record came from.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator


class Source(ABC):
    @abstractmethod
    def records(self) -> Iterator[Dict[str, Any]]:
        """Yield raw records as plain dicts, one per event/row."""
        raise NotImplementedError
