import json
from collections.abc import Iterator
from queue import Queue
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import JsonValue

from app.schemas.asklys import (
    AsklysContextResponse,
    AsklysQueryRequest,
    AsklysQueryResponse,
)
from app.services.asklys import (
    AsklysError,
    AsklysNotConfiguredError,
    AsklysQueryError,
    AsklysService,
    get_asklys_service,
)

router = APIRouter(prefix="/asklys", tags=["asklys"])


def provide_asklys() -> AsklysService:
    try:
        return get_asklys_service()
    except AsklysNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/context", response_model=AsklysContextResponse)
def get_context_suggestions(
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=30, ge=1, le=100),
    service: AsklysService = Depends(provide_asklys),
) -> AsklysContextResponse:
    try:
        return service.context(q, limit)
    except AsklysError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/query", response_model=AsklysQueryResponse)
def query_asklys(
    request: AsklysQueryRequest,
    service: AsklysService = Depends(provide_asklys),
) -> AsklysQueryResponse:
    try:
        return service.ask(request)
    except AsklysQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except AsklysError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/query/stream")
def stream_asklys(
    request: AsklysQueryRequest,
    service: AsklysService = Depends(provide_asklys),
) -> StreamingResponse:
    """Stream observable agent actions without exposing private chain-of-thought."""

    def events() -> Iterator[str]:
        queue: Queue[dict[str, JsonValue] | object] = Queue()
        done = object()

        def run() -> None:
            try:
                result = service.ask(request, progress=queue.put)
                queue.put(
                    {
                        "type": "complete",
                        "data": result.model_dump(mode="json"),
                    }
                )
            except AsklysError as exc:
                queue.put({"type": "error", "message": str(exc)})
            except Exception:
                queue.put(
                    {
                        "type": "error",
                        "message": "Asklys hit an unexpected error while answering.",
                    }
                )
            finally:
                queue.put(done)

        Thread(target=run, daemon=True).start()
        while True:
            event = queue.get()
            if event is done:
                break
            yield json.dumps(event, separators=(",", ":")) + "\n"

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
