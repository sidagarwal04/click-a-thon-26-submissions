from __future__ import annotations

from typing import Any, Protocol

from zentra_domain_agent_execution import (
    SemanticCatalog,
    SemanticDimension,
    SemanticMeasure,
    SemanticQuery,
    SemanticResult,
)


class SemanticValueSource(Protocol):
    """A semantic layer that can also say what a dimension contains."""

    async def values_for(self, dimension: SemanticDimension) -> SemanticDimension: ...


class CubeMetaLoader(Protocol):
    async def meta(self) -> dict[str, Any]: ...

    async def load(self, query: dict[str, Any]) -> dict[str, Any]: ...


def _catalog_from_meta(meta: dict[str, Any]) -> SemanticCatalog:
    measures: list[SemanticMeasure] = []
    dimensions: list[SemanticDimension] = []
    for cube in meta.get("cubes", []):
        for measure in cube.get("measures", []):
            measures.append(
                SemanticMeasure(
                    name=measure["name"],
                    type=measure.get("type", "number"),
                    format=measure.get("format"),
                    description=measure.get("description"),
                )
            )
        for dimension in cube.get("dimensions", []):
            dimensions.append(
                SemanticDimension(
                    name=dimension["name"],
                    type=dimension.get("type", "string"),
                    description=dimension.get("description"),
                )
            )
    return SemanticCatalog(
        measures=tuple(measures),
        dimensions=tuple(dimensions),
    )


def _to_cube_query(request: SemanticQuery) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if request.measures:
        query["measures"] = list(request.measures)
    if request.dimensions:
        query["dimensions"] = list(request.dimensions)
    if request.time_dimensions:
        query["timeDimensions"] = [
            {
                key: value
                for key, value in (
                    ("dimension", time_dimension.dimension),
                    ("granularity", time_dimension.granularity),
                    (
                        "dateRange",
                        list(time_dimension.date_range)
                        if time_dimension.date_range
                        else None,
                    ),
                )
                if value is not None
            }
            for time_dimension in request.time_dimensions
        ]
    if request.filters:
        query["filters"] = [
            {
                "member": semantic_filter.member,
                "operator": semantic_filter.operator,
                "values": list(semantic_filter.values),
            }
            for semantic_filter in request.filters
        ]
    if request.limit is not None:
        query["limit"] = request.limit
    return query


# Above this a dimension is an identifier, not a vocabulary, and listing it
# would bloat every prompt without helping an agent choose.
MAX_LISTED_VALUES = 25


class CubeSemanticLayer:
    """Reads metrics through Cube.

    `query()` enforces the governed-catalog restriction; `query_raw()` and
    `load_raw()` do not, for tenants/agents that have opted out of it."""

    def __init__(self, client: CubeMetaLoader) -> None:
        self._client = client
        self._catalog: SemanticCatalog | None = None
        self._values: dict[str, tuple[str, ...]] = {}

    async def catalog(self) -> SemanticCatalog:
        """The governed vocabulary. Names and types only — no value probing.

        Value discovery used to happen here, one query per string dimension.
        That was invisible against a demo cube with eight dimensions and fatal
        against a real tenant catalog: 284 dimensions meant ~200 sequential
        round trips to ClickHouse Cloud before a single question could be
        read, and the request timed out. Values are now fetched per dimension,
        by whoever is about to need them — see `values_for`.
        """
        if self._catalog is None:
            self._catalog = _catalog_from_meta(await self._client.meta())
        return self._catalog

    async def values_for(self, dimension: SemanticDimension) -> SemanticDimension:
        """Read what one string dimension actually contains.

        Discovered rather than declared: a hand-written list drifts from the
        warehouse, and a permitted value that is not in the data is worse than
        no list at all. Cached per dimension, so a caller that asks twice pays
        once.
        """
        if dimension.type != "string" or dimension.values:
            return dimension
        cached = self._values.get(dimension.name)
        if cached is not None:
            return dimension.model_copy(update={"values": cached})

        payload = await self._client.load(
            {"dimensions": [dimension.name], "limit": MAX_LISTED_VALUES + 1}
        )
        rows = payload.get("data", [])
        if len(rows) > MAX_LISTED_VALUES:
            # An identifier, not a vocabulary. Remembered as empty so the same
            # dimension is not probed again.
            self._values[dimension.name] = ()
            return dimension
        values = tuple(
            sorted(
                str(row[dimension.name])
                for row in rows
                if row.get(dimension.name) is not None
            )
        )
        self._values[dimension.name] = values
        return dimension.model_copy(update={"values": values})

    async def query(self, request: SemanticQuery) -> SemanticResult:
        catalog = await self.catalog()
        catalog.reject_ungoverned(request)
        payload = await self._client.load(_to_cube_query(request))
        return SemanticResult(
            query=request,
            rows=tuple(payload.get("data", [])),
        )

    async def query_raw(self, request: SemanticQuery) -> SemanticResult:
        """Like `query`, but skips `reject_ungoverned`.

        For tenants that have opted out of the governed-catalog restriction:
        any member Cube has compiled is queryable, not only ones a caller
        already knows to be governed. Still scoped by this layer's own
        tenant/Data Connection security context — never cross-tenant.
        """
        payload = await self._client.load(_to_cube_query(request))
        return SemanticResult(
            query=request,
            rows=tuple(payload.get("data", [])),
        )

    async def load_raw(self, query: dict[str, Any]) -> dict[str, Any]:
        """Call Cube's `/load` with a hand-built query, skipping `reject_ungoverned`.

        For call sites that build their own query from data they already
        trust — never from caller input — and have their own documented
        reason `query()`'s governance gate does not apply. Everything else
        must keep using `query()`.
        """
        return await self._client.load(query)
