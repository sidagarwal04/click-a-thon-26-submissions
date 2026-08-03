"""Turning an uploaded file into a Data Source.

Split from ``service.py``, which crossed the repository's 600-line limit once
every resource group landed in it. Uploads are the natural seam: they are the
only operations that hold state between two calls — a previewed file waits for a
commit — and the only ones that write customer data into ZentraOS storage.

Mixed into ``ConnectorService`` rather than standing alone, because an upload
*becomes* a Data Source and the two halves share the source repository, the
clock, and the permission rules. A separate collaborator would have needed all
three passed to it to do the same job.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from uuid import UUID, uuid4

from zentra_domain_connector import (
    DataSource,
    SourceHealth,
    SourceKind,
    UploadFormat,
)
from zentra_domain_connector.constants import MAX_UPLOAD_BYTES

from .dto import (
    HARVEST_ROLES,
    AuthenticatedActor,
    SourceSummary,
    UploadPreview,
    UploadRejectedError,
)
from .views import to_summary


class UploadOperations:
    """The upload half of ``ConnectorService``.

    Relies on the attributes the service establishes in its constructor. Kept as
    a mixin rather than a free-standing class so that ``commit_upload`` can add
    the resulting Data Source through the same repository every other source
    goes through.
    """

    #: Previewed but uncommitted uploads, held until the reviewer accepts or
    #: abandons them. In process memory deliberately: an upload nobody committed
    #: is not worth a storage round trip, and losing it on restart costs the
    #: user one re-upload rather than any confirmed work.
    _pending_uploads: dict[UUID, tuple[UploadPreview, bytes]]

    async def preview_upload(
        self,
        actor: AuthenticatedActor,
        *,
        filename: str,
        upload_format: UploadFormat,
        stream: AsyncIterator[bytes],
        preview_rows: int = 20,
    ) -> UploadPreview:
        """Parse a file and show what it looks like, committing to nothing.

        Preview before commit exists because a mis-parsed column discovered
        afterwards has already poisoned every profile and every Relation
        downstream of it.

        The size check runs as chunks arrive rather than after collection, so an
        oversized file is refused partway through rather than after it has all
        been held in memory.
        """
        self._require(actor, HARVEST_ROLES)
        buffered = bytearray()
        async for chunk in stream:
            buffered.extend(chunk)
            if len(buffered) > MAX_UPLOAD_BYTES:
                raise UploadRejectedError(
                    f"Upload exceeds the {MAX_UPLOAD_BYTES} byte limit"
                )

        columns, rows, total = await self._landing.inspect(
            _replay(bytes(buffered)),
            upload_format=upload_format,
            preview_rows=preview_rows,
        )
        preview = UploadPreview(
            upload_id=uuid4(),
            filename=filename,
            upload_format=upload_format,
            columns=tuple(columns),
            rows=tuple(tuple(r) for r in rows),
            total_bytes=len(buffered),
            truncated=total > preview_rows,
        )
        self._pending_uploads[preview.upload_id] = (preview, bytes(buffered))
        return preview

    async def commit_upload(
        self,
        actor: AuthenticatedActor,
        upload_id: UUID,
        *,
        name: str,
        columns: Sequence[object] | None = None,
    ) -> SourceSummary:
        """Land a previewed file and turn it into a Data Source.

        The result is an ordinary Data Source of kind ``uploaded``, not a
        parallel concept — which is what lets it be harvested, profiled and
        relation-inferred by exactly the same code as a connected warehouse, and
        what makes a join between it and that warehouse discoverable at all.
        """
        self._require(actor, HARVEST_ROLES)
        pending = self._pending_uploads.pop(upload_id, None)
        if pending is None:
            raise UploadRejectedError("No pending upload with that id")

        preview, payload = pending
        chosen = tuple(columns) if columns else preview.columns
        landed = await self._landing.land(
            _replay(payload),
            tenant_id=actor.tenant_id,
            upload_id=upload_id,
            upload_format=preview.upload_format,
            columns=chosen,  # type: ignore[arg-type]
        )
        now = self._clock.now()
        source = DataSource(
            data_source_id=uuid4(),
            tenant_id=actor.tenant_id,
            name=name,
            kind=SourceKind.UPLOADED,
            description=f"Uploaded from {preview.filename}",
            health=SourceHealth.REACHABLE,
            last_verified_at=now,
            created_at=now,
            landed_table=landed.qualified_name,
            metadata={"rows": str(landed.row_count), "filename": preview.filename},
        )
        await self._sources.add(source)
        return to_summary(source)


async def _replay(payload: bytes) -> AsyncIterator[bytes]:
    """Re-present collected bytes as a stream.

    The landing zone takes a stream so a real adapter can process incrementally.
    A previewed file has already been read whole to size-check it, so it is
    handed back in one chunk rather than being re-read from a source that no
    longer exists.
    """
    yield payload
