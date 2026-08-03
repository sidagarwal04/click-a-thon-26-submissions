from __future__ import annotations

from typing import Any

import httpx
from zentra_domain_agent_execution import InvalidSemanticQueryError

#: Cube's message can quote the offending SQL fragment on some errors. The
#: reason goes back to an Agent as a prompt, and ADR-0003's guarantee is that
#: an Agent never sees SQL — so it is truncated to the sentence that names the
#: problem rather than passed through whole.
MAX_REFUSAL_REASON = 300


def _refusal_reason(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "Cube refused the query."
    message = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(message, str) or not message:
        return "Cube refused the query."
    return message.split("\n", maxsplit=1)[0][:MAX_REFUSAL_REASON]


class CubeClient:
    def __init__(self, base_url: str, api_secret: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_secret = api_secret

    def _headers(self) -> dict[str, str]:
        if not self._api_secret:
            return {}
        return {"Authorization": self._api_secret}

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self._base_url}/readyz")
            return response.is_success
        except httpx.HTTPError:
            return False

    async def meta(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self._base_url}/cubejs-api/v1/meta",
                headers=self._headers(),
            )
        response.raise_for_status()
        return response.json()

    async def load(self, query: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url}/cubejs-api/v1/load",
                headers=self._headers(),
                json={"query": query},
            )
        if response.status_code == httpx.codes.BAD_REQUEST:
            # Cube's way of saying the query is unanswerable as written — an
            # unsupported granularity, an operator a dimension does not
            # implement. That is the caller's mistake and a correctable one, so
            # it is raised as a refusal rather than left as a transport error
            # that reads like an outage. Every other status still does.
            raise InvalidSemanticQueryError(_refusal_reason(response))
        response.raise_for_status()
        return response.json()
