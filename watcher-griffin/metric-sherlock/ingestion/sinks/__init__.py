"""The Sink adapter contract -- tool-agnostic on purpose.

A future ClickHouseSink or a Kafka-producer sink implements the same
`write()` method; pipeline.py never changes.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class Sink(ABC):
    @abstractmethod
    def write(self, entity: str, rows: List[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass
