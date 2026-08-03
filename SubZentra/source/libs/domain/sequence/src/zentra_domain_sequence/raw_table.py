"""Raw Table origins a Sequence may start from.

A self-contained union rather than importing Connector's or Data Source's own
domain types directly: Data Source has no domain library yet (CONTEXT.md
only), and this keeps Sequence from taking on either domain's full identity
model just to name where its Raw Table came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ConnectorSourceTableReference:
    """A Raw Table that is a Connector-harvested Source Table, queried where
    it already lives — never copied."""

    catalog_version_id: str
    source_table_name: str
    kind: Literal["connector_source_table"] = "connector_source_table"


@dataclass(frozen=True, slots=True)
class DatasetTableVersionReference:
    """A Raw Table that is an uploaded Data Source Dataset Table Version,
    read directly at its storage locator."""

    storage_locator: str
    file_format: Literal["csv", "parquet"]
    kind: Literal["dataset_table_version"] = "dataset_table_version"


RawTableReference = ConnectorSourceTableReference | DatasetTableVersionReference
