from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from pydantic.types import JsonValue


class SequenceOperationKind(StrEnum):
    """The closed v1 catalog of typed transforms a Sequence Step may apply.

    No operation outside this set can ever be constructed — Data Steward (or
    any other caller) proposes one of these five, never agent-authored SQL or
    code.
    """

    DROP_NULLS = "drop_nulls"
    CAST_TYPE = "cast_type"
    DEDUPE = "dedupe"
    FILTER_ROWS = "filter_rows"
    RENAME_COLUMN = "rename_column"


class UnknownSequenceOperationError(ValueError):
    """A requested operation name is outside the closed v1 catalog."""


class SequenceOperationValidationError(ValueError):
    """An operation's parameters do not satisfy its own typed shape."""


class DropNullsParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["drop_nulls"] = "drop_nulls"
    columns: tuple[str, ...] = Field(min_length=1)
    strategy: Literal["any", "all"] = "any"


class CastTypeParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["cast_type"] = "cast_type"
    column: str = Field(min_length=1)
    target_type: str = Field(min_length=1)


class DedupeParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["dedupe"] = "dedupe"
    # Empty means every column participates in the duplicate check.
    columns: tuple[str, ...] = ()


class FilterRowsParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["filter_rows"] = "filter_rows"
    column: str = Field(min_length=1)
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "is_null", "is_not_null"]
    value: JsonValue | None = None


class RenameColumnParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["rename_column"] = "rename_column"
    from_name: str = Field(min_length=1)
    to_name: str = Field(min_length=1)


SequenceOperation = Annotated[
    DropNullsParameters
    | CastTypeParameters
    | DedupeParameters
    | FilterRowsParameters
    | RenameColumnParameters,
    Field(discriminator="kind"),
]
SEQUENCE_OPERATION_ADAPTER = TypeAdapter(SequenceOperation)


def build_sequence_operation(
    kind: str, parameters: dict[str, JsonValue]
) -> SequenceOperation:
    """Validate and construct a typed operation from its name and raw params.

    This is the single seam every caller (a fake adapter, a real chDB
    adapter, a future Agent) must pass through — the catalog is enforced
    here, once, rather than trusted at each call site.
    """
    try:
        operation_kind = SequenceOperationKind(kind)
    except ValueError as error:
        raise UnknownSequenceOperationError(
            f"{kind!r} is not a member of the Sequence Step typed operation "
            f"catalog: {', '.join(sorted(k.value for k in SequenceOperationKind))}"
        ) from error

    try:
        return SEQUENCE_OPERATION_ADAPTER.validate_python(
            {**parameters, "kind": operation_kind.value}
        )
    except Exception as error:
        raise SequenceOperationValidationError(
            f"Parameters for {operation_kind.value!r} are invalid: {error}"
        ) from error
