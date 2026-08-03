"""The Tenant-configured slice of the governed catalog Intake may resolve a
question against.

See ADR-0027: this replaces the two-scenario keyword whitelist. An
Analytical Scope can only narrow what a Tenant may be asked about — it is
validated against, and can never widen past, `SemanticCatalog.reject_ungoverned`
(`libs/domain/agent-execution/.../ports.py`), which stays the absolute floor.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from zentra_domain_agent_execution import SemanticCatalog


@dataclass(frozen=True, slots=True)
class AnalyticalScope:
    """A cube allowlist, with optional member-level overrides, for one Tenant.

    `cubes` names which Cube cubes (the part of a member name before its
    first `.`) are visible in full. `member_overrides` adds individual
    members from cubes not otherwise in scope — it never removes a member an
    allowed cube already grants.
    """

    tenant_id: UUID
    cubes: frozenset[str] = frozenset()
    member_overrides: frozenset[str] = frozenset()

    @classmethod
    def unrestricted(cls, tenant_id: UUID) -> AnalyticalScope:
        """The default: no cube list narrows the governed catalog.

        This is the demo Tenant's configuration, so local and demo chat can
        ask about anything the catalog already governs without a separate
        scope-configuration step.
        """
        return cls(tenant_id=tenant_id)

    @property
    def is_unrestricted(self) -> bool:
        return not self.cubes and not self.member_overrides

    def narrow(self, catalog: SemanticCatalog) -> SemanticCatalog:
        """The catalog Intake and analytical Agents may actually see.

        Never adds a member `catalog` does not already have — a Scope can
        only subtract, so a cube or member this Scope does not name is
        simply absent, exactly as if the Tenant's governed model never
        defined it.
        """
        if self.is_unrestricted:
            return catalog
        allowed = self.member_overrides | frozenset(
            name for name in catalog.member_names() if _cube_of(name) in self.cubes
        )
        return SemanticCatalog(
            measures=tuple(
                measure for measure in catalog.measures if measure.name in allowed
            ),
            dimensions=tuple(
                dimension
                for dimension in catalog.dimensions
                if dimension.name in allowed
            ),
        )


def _cube_of(member_name: str) -> str:
    return member_name.split(".", maxsplit=1)[0]
