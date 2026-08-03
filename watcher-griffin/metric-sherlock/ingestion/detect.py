"""Entity auto-detection: filename stem first, column sniff as fallback.

`plan_path()` turns a file OR directory into an ordered ingestion plan --
dimensions before facts, because the rollup MVs enrich ad_events rows via
dictGet at insert time and must see fresh dimension labels.
"""

import os
from typing import List, Set, Tuple

from .transformers import (
    AD_EVENT_FIELDS,
    ADVERTISER_FIELDS,
    APP_FIELDS,
    GEO_DEVICE_FIELDS,
    _normalize_key,
)

# Dimensions first, facts last. Also the stem-match order: longer/more
# specific names checked before "apps" so "advertisers" never prefix-clashes.
INGEST_ORDER = ("apps", "advertisers", "geo_device", "ad_events")
_STEM_CHECK_ORDER = ("ad_events", "geo_device", "advertisers", "apps")

FIELDS_BY_ENTITY = {
    "ad_events": AD_EVENT_FIELDS,
    "apps": APP_FIELDS,
    "advertisers": ADVERTISER_FIELDS,
    "geo_device": GEO_DEVICE_FIELDS,
}


class EntityDetectionError(ValueError):
    pass


def _read_columns(path: str) -> Set[str]:
    try:
        if path.lower().endswith(".parquet"):
            import pyarrow.parquet as pq

            return set(pq.ParquetFile(path).schema_arrow.names)
        with open(path, "r", encoding="utf-8") as f:
            header = f.readline().strip("\r\n")
        return {c for c in header.split(",") if c.strip()}
    except Exception as exc:
        raise EntityDetectionError(f"cannot read columns from {path!r}: {exc}") from exc


def detect_entity_for_file(path: str) -> str:
    stem = os.path.basename(path).lower()
    for entity in _STEM_CHECK_ORDER:
        if stem.startswith(entity):
            return entity

    columns = {_normalize_key(c) for c in _read_columns(path)}
    matches = [e for e, fields in FIELDS_BY_ENTITY.items() if fields <= columns]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise EntityDetectionError(
            f"cannot detect entity for {path!r}: columns {sorted(columns)} "
            f"match no known entity"
        )
    raise EntityDetectionError(
        f"ambiguous entity for {path!r}: columns match {sorted(matches)}"
    )


def plan_path(path: str) -> List[Tuple[str, str]]:
    """(entity, file) pairs in ingestion order for a file or directory."""
    if os.path.isfile(path):
        return [(detect_entity_for_file(path), path)]
    if not os.path.isdir(path):
        raise EntityDetectionError(f"{path!r} is not a file or directory")

    found: dict = {}
    for fname in sorted(os.listdir(path)):
        if fname.startswith("."):
            continue
        fpath = os.path.join(path, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            entity = detect_entity_for_file(fpath)
        except EntityDetectionError:
            continue  # non-data file in the drop dir -- skip, don't fail the run
        if entity in found:
            raise EntityDetectionError(
                f"two files for entity '{entity}': {found[entity]!r} and {fpath!r}"
            )
        found[entity] = fpath
    if not found:
        raise EntityDetectionError(f"no recognizable data files in {path!r}")
    return [(e, found[e]) for e in INGEST_ORDER if e in found]
