"""STREAMING source, self-contained (no external broker required).

Watches `watch_dir` for new files and appended lines in existing ones -- the
same pattern Kafka Connect's FileStreamSource / Filebeat use to turn a
drop-folder into a live feed. Tracks per-file byte offsets, persisted to
`state_file`, so a restart resumes instead of reprocessing. `records()` never
terminates on its own -- it blocks (sleeps) between polls when nothing new
has arrived, which is what makes this genuinely "live" rather than a replay
of a fixed batch.

Migrating to a real broker later (Kafka, Kinesis, ...) means writing one new
class with the same `records()` contract, blocking on the consumer's own
`poll()` instead of file offsets -- nothing else in this package changes.
"""

import json
import os
import time
from typing import Any, Dict, Iterator, List, Optional

from . import Source
from ..transformers import MALFORMED_LINE_KEY


class LiveTailSource(Source):
    def __init__(
        self,
        watch_dir: str,
        poll_interval_seconds: float = 2.0,
        state_file: Optional[str] = None,
    ):
        self.watch_dir = watch_dir
        self.poll_interval_seconds = poll_interval_seconds
        self.state_file = state_file or os.path.join(watch_dir, ".ingest_state.json")
        os.makedirs(self.watch_dir, exist_ok=True)
        self._state: Dict[str, Dict[str, Any]] = self._load_state()

    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_state(self) -> None:
        tmp = self.state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._state, f)
        os.replace(tmp, self.state_file)

    def records(self) -> Iterator[Dict[str, Any]]:
        while True:
            batch: List[Dict[str, Any]] = []
            for fname in sorted(os.listdir(self.watch_dir)):
                if fname.startswith("."):
                    continue
                fpath = os.path.join(self.watch_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                batch.extend(self._drain_file(fname, fpath))
            if batch:
                yield from batch
            else:
                time.sleep(self.poll_interval_seconds)

    def _drain_file(self, fname: str, fpath: str) -> List[Dict[str, Any]]:
        file_state = self._state.get(fname, {"offset": 0, "header": None})
        size = os.path.getsize(fpath)
        if size <= file_state["offset"]:
            return []

        rows: List[Dict[str, Any]] = []
        with open(fpath, "r", encoding="utf-8", newline="") as f:
            if file_state["header"] is None:
                header_line = f.readline()
                file_state["header"] = [h.strip() for h in header_line.strip("\r\n").split(",")]
                file_state["offset"] = f.tell()
            else:
                f.seek(file_state["offset"])

            header = file_state["header"]
            for line in f:
                line = line.rstrip("\r\n")
                if not line:
                    continue
                # Naive comma-split: the watch-dir CSVs have no embedded commas,
                # so this avoids pulling in a full CSV parser for a demo source.
                values = line.split(",")
                if len(values) != len(header):
                    # Wrong column count -- surface as a rejected record
                    # instead of silently zip()-truncating/padding it.
                    rows.append({MALFORMED_LINE_KEY: line})
                else:
                    rows.append(dict(zip(header, values)))
            file_state["offset"] = f.tell()

        self._state[fname] = file_state
        self._save_state()
        return rows
