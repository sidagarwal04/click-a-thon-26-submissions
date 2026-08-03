"""The tools an Agent may be granted, and the registry that gates them.

Every tool here reaches data through `SemanticLayerPort` and nothing else.
`semantic_query` enforces the governed-catalog restriction (ADR-003);
`raw_query` deliberately does not, for a tenant that has opted out of it —
still scoped to that tenant's own Data Connection through Cube, never
cross-tenant.

`AgentDescriptor.tool_permissions` is the gate. A tool outside a descriptor's
permissions is never offered to the model *and* is refused if named anyway,
because a model can hallucinate a tool name it was never shown.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic.types import JsonValue
from zentra_domain_agent_execution import (
    AgentDescriptor,
    InvalidSemanticQueryError,
    SemanticLayerPort,
    SemanticQuery,
    ToolAccess,
    ToolDefinition,
    ToolPort,
    ToolResult,
    ToolScope,
    UnauthorizedToolError,
    UnknownSemanticMemberError,
)

from .schemas import (
    SEMANTIC_QUERY_SCHEMA,
    MalformedAgentResponseError,
    render_dimension,
    render_measure,
    semantic_query_from_json,
)

#: Above this a search is not narrowing anything and the reply stops being
#: cheaper than the whole catalog.
MAX_SEARCH_RESULTS = 40

#: Rows come back to the model, so this bounds a prompt as much as a payload.
#: The Analyst asks for aggregates; a result this long means the query grouped
#: by something it should not have.
MAX_QUERY_ROWS = 200


class SemanticCatalogSearchTool:
    """Find governed members by term, instead of reading the whole catalog.

    The reason the loop exists at all. One demo cube fits in a prompt; a
    tenant's harvested warehouse does not, and an Agent given a truncated
    catalog does not know what it was not shown.
    """

    name = "semantic_catalog_search"

    def __init__(self, semantic_layer: SemanticLayerPort) -> None:
        self._semantic_layer = semantic_layer

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=(
                "Search the governed catalog, grouped by dataset. Returns "
                "each matching member's name, type, description, and — for "
                "dimensions holding few enough values — the values "
                "themselves. Pass an empty term to list every dataset with "
                "its size; that is the fastest way to see what exists. A "
                "wide match returns dataset names and counts instead of "
                "members, so narrow the term to see inside one."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": (
                            "Words to match against member names and "
                            "descriptions; any word may match. Empty lists "
                            "every dataset."
                        ),
                    }
                },
                "required": ["term"],
                "additionalProperties": False,
            },
        )

    @property
    def scope(self) -> ToolScope:
        return ToolScope(tool_name=self.name, access=ToolAccess.READ)

    async def invoke(self, arguments: dict[str, JsonValue]) -> ToolResult:
        term = str(arguments.get("term", "")).strip().casefold()
        catalog = await self._semantic_layer.catalog()

        measures = [
            m for m in catalog.measures if _matches(term, m.name, m.description)
        ]
        dimensions = [
            d for d in catalog.dimensions if _matches(term, d.name, d.description)
        ]
        if not measures and not dimensions:
            return ToolResult(
                call_id="",
                content=(
                    f"No governed member matches {term!r}. "
                    "Search a broader term, or an empty one to list every "
                    "dataset."
                ),
            )

        # Grouped by dataset, and summarised rather than enumerated once the
        # match is wide. A flat list of every matching member was both the
        # wrong shape for "what is here?" and enormous — a real tenant catalog
        # has hundreds of members, and an Agent asked to find its way around
        # one spent nine searches guessing single words because no single
        # answer ever showed it the shape of the whole thing.
        by_dataset: dict[str, list[str]] = {}
        for measure in measures:
            by_dataset.setdefault(_dataset_of(measure.name), []).append(
                render_measure(measure)
            )
        for dimension in dimensions:
            by_dataset.setdefault(_dataset_of(dimension.name), []).append(
                render_dimension(dimension)
            )

        total = len(measures) + len(dimensions)
        if total > MAX_SEARCH_RESULTS:
            lines = [
                f"{total} members across {len(by_dataset)} datasets. "
                "Search a narrower term to see members.",
                "",
                "Datasets:",
            ]
            lines.extend(
                f"- {dataset} ({len(members)} members)"
                for dataset, members in sorted(by_dataset.items())
            )
            return ToolResult(call_id="", content="\n".join(lines))

        # Narrow enough to show members, so it is worth learning what the
        # string dimensions among them actually contain — an agent filtering
        # on a value that is spelled differently gets zero rows and no error.
        # Only here, and only for these few: probing the whole catalog is what
        # made a real tenant's first question time out.
        by_dataset = {}
        for measure in measures:
            by_dataset.setdefault(_dataset_of(measure.name), []).append(
                render_measure(measure)
            )
        for dimension in await self._with_values(dimensions):
            by_dataset.setdefault(_dataset_of(dimension.name), []).append(
                render_dimension(dimension)
            )

        lines = []
        for dataset, members in sorted(by_dataset.items()):
            lines.append(f"{dataset}:")
            lines.extend(members)
        return ToolResult(call_id="", content="\n".join(lines))

    async def _with_values(self, dimensions):
        """Value lists for these dimensions, where the layer can supply them."""
        source = getattr(self._semantic_layer, "values_for", None)
        if source is None:
            return dimensions
        return [await source(dimension) for dimension in dimensions]


class SemanticQueryTool:
    """Run one governed query and return its rows.

    The same `SemanticLayerPort.query` the Agent always had. What is new is
    that it can be called again after seeing the answer.

    Remembers the last query it actually ran, and its rows. Evidence Citations
    are built from that rather than from anything the model says afterwards: a
    citation has to rest on the query that executed, and a model asked to
    restate its own query at the end of a long conversation will sometimes
    restate a different one. One instance per Agent Execution, so "last" is
    unambiguous.
    """

    name = "semantic_query"

    def __init__(self, semantic_layer: SemanticLayerPort) -> None:
        self._semantic_layer = semantic_layer
        self.last_query: SemanticQuery | None = None
        self.last_rows: tuple[dict[str, JsonValue], ...] = ()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=(
                "Run a governed query against the semantic layer and return "
                "the rows. Every member must appear verbatim in the catalog."
            ),
            input_schema=SEMANTIC_QUERY_SCHEMA,
        )

    @property
    def scope(self) -> ToolScope:
        return ToolScope(tool_name=self.name, access=ToolAccess.READ)

    async def invoke(self, arguments: dict[str, JsonValue]) -> ToolResult:
        try:
            query = semantic_query_from_json(dict(arguments))
        except MalformedAgentResponseError as error:
            return _refusal(str(error))

        try:
            result = await self._semantic_layer.query(query)
        except (UnknownSemanticMemberError, InvalidSemanticQueryError) as error:
            # Reported to the model rather than raised past it. Reaching for a
            # member the catalog does not define is a mistake the Agent can
            # correct on the next turn, and telling it which member was wrong
            # is the difference between a retry and a failed investigation.
            return _refusal(str(error))

        self.last_query = query
        self.last_rows = result.rows
        rows = list(result.rows)
        if not rows:
            return ToolResult(
                call_id="",
                content=(
                    "The query returned no rows. Check the filter values "
                    "against the ones the catalog lists for that dimension."
                ),
            )
        head = rows[:MAX_QUERY_ROWS]
        body = "\n".join(str(row) for row in head)
        if len(rows) > MAX_QUERY_ROWS:
            body += (
                f"\n({len(rows) - MAX_QUERY_ROWS} more rows withheld — "
                "aggregate further or add a limit.)"
            )
        return ToolResult(call_id="", content=body)


class RawQueryTool:
    """Run one query with no governed-catalog restriction and return its rows.

    Same shape as `SemanticQueryTool`, calling `SemanticLayerPort.query_raw`
    instead of `query`: any member Cube has compiled — not only ones already
    known to be governed — is queryable. Only offered to an Agent whose
    tenant has opted out of ADR-003's restriction. Still tenant-scoped: this
    reaches the same Cube security context as every other tool here, never
    another tenant's data.
    """

    name = "raw_query"

    def __init__(self, semantic_layer: SemanticLayerPort) -> None:
        self._semantic_layer = semantic_layer
        self.last_query: SemanticQuery | None = None
        self.last_rows: tuple[dict[str, JsonValue], ...] = ()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=(
                "Run a query against any table, column, or measure this "
                "tenant's connected sources expose — not limited to the "
                "governed catalog. Use semantic_catalog_search first to see "
                "what is available, by name."
            ),
            input_schema=SEMANTIC_QUERY_SCHEMA,
        )

    @property
    def scope(self) -> ToolScope:
        return ToolScope(tool_name=self.name, access=ToolAccess.READ)

    async def invoke(self, arguments: dict[str, JsonValue]) -> ToolResult:
        try:
            query = semantic_query_from_json(dict(arguments))
        except MalformedAgentResponseError as error:
            return _refusal(str(error))

        try:
            result = await self._semantic_layer.query_raw(query)
        except InvalidSemanticQueryError as error:
            return _refusal(str(error))

        self.last_query = query
        self.last_rows = result.rows
        rows = list(result.rows)
        if not rows:
            return ToolResult(call_id="", content="The query returned no rows.")
        head = rows[:MAX_QUERY_ROWS]
        body = "\n".join(str(row) for row in head)
        if len(rows) > MAX_QUERY_ROWS:
            body += (
                f"\n({len(rows) - MAX_QUERY_ROWS} more rows withheld — "
                "aggregate further or add a limit.)"
            )
        return ToolResult(call_id="", content=body)


class ToolRegistry:
    """The tools this deployment has, filtered per Agent by its descriptor."""

    def __init__(self, tools: Sequence[ToolPort]) -> None:
        self._tools = {tool.definition.name: tool for tool in tools}

    def definitions_for(
        self, descriptor: AgentDescriptor
    ) -> tuple[ToolDefinition, ...]:
        """What this Agent may be offered. Never the whole registry."""
        return tuple(
            tool.definition
            for name, tool in self._tools.items()
            if name in _permitted(descriptor)
        )

    def resolve(self, descriptor: AgentDescriptor, name: str) -> ToolPort:
        """The tool by that name, if this Agent holds it.

        Checked again on call rather than trusting that only offered tools get
        named: a model can invent a tool name it was never shown, and on a
        long conversation it can name one from an earlier, differently-scoped
        turn.
        """
        if name not in _permitted(descriptor):
            raise UnauthorizedToolError(
                f"{descriptor.agent_id} holds no permission for tool {name!r}"
            )
        tool = self._tools.get(name)
        if tool is None:
            raise UnauthorizedToolError(f"No tool named {name!r} is registered")
        return tool


def _permitted(descriptor: AgentDescriptor) -> frozenset[str]:
    return frozenset(scope.tool_name for scope in descriptor.tool_permissions)


def _dataset_of(member: str) -> str:
    """The cube a member belongs to. `Commerce.refundAmount` -> `Commerce`."""
    return member.split(".", maxsplit=1)[0] if "." in member else member


def _searchable(value: str) -> str:
    """Fold camelCase, dots and underscores into space-separated words.

    `Commerce.netRevenue` becomes "commerce net revenue", so an Agent
    searching the words a human would use finds it. Observed live: a plain
    substring match on "net revenue" found nothing, and the Agent spent six of
    its twelve steps guessing synonyms before stumbling onto the member.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return re.sub(r"[._\-]+", " ", spaced).casefold()


def _matches(term: str, name: str, description: str | None) -> bool:
    """Any word of the term appearing in the member's words or its description.

    Any rather than all: an Agent searching "net revenue by country" should
    find the revenue measure, not nothing. Over-returning costs a few lines of
    prompt; under-returning costs the Agent a step and a guess.
    """
    if not term:
        return True
    haystack = f"{_searchable(name)} {(description or '').casefold()}"
    words = [word for word in _searchable(term).split() if word]
    return any(word in haystack for word in words)


def _refusal(message: str) -> ToolResult:
    return ToolResult(call_id="", content=message, is_error=True)
