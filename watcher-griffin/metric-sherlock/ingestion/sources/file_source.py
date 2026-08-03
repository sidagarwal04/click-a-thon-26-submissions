"""BATCH source: reads a single parquet or CSV file and terminates.

Streams in chunks (pyarrow row-group batches for parquet, pandas chunksize
for CSV) rather than loading the whole file into memory, so this stays
data-volume agnostic against a much larger unseen-incident file.
"""

import os
from typing import Any, Dict, Iterator, List

import pandas as pd

from . import Source
from ..transformers import MALFORMED_LINE_KEY


class FileSource(Source):
    def __init__(self, path: str, chunk_size: int = 10000):
        self.path = path
        self.chunk_size = chunk_size

    def records(self) -> Iterator[Dict[str, Any]]:
        ext = os.path.splitext(self.path)[1].lower()
        if ext == ".parquet":
            yield from self._read_parquet()
        else:
            yield from self._read_csv()

    def _read_parquet(self) -> Iterator[Dict[str, Any]]:
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(self.path)
        for batch in pf.iter_batches(batch_size=self.chunk_size):
            for row in batch.to_pylist():
                yield row

    def _read_csv(self) -> Iterator[Dict[str, Any]]:
        bad_lines: List[str] = []

        def _on_bad_line(line: List[str]):
            # Capture instead of raising/silently dropping -- surfaced as a
            # rejected record downstream (transformers.MALFORMED_LINE_KEY)
            # rather than vanishing from the ingested count.
            bad_lines.append(",".join(line))
            return None

        for chunk in pd.read_csv(
            self.path,
            chunksize=self.chunk_size,
            dtype=str,
            keep_default_na=False,
            engine="python",
            on_bad_lines=_on_bad_line,
        ):
            for row in chunk.to_dict(orient="records"):
                yield row

        for line in bad_lines:
            yield {MALFORMED_LINE_KEY: line}
