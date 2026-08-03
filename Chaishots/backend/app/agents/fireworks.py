from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

AgentOutput = TypeVar("AgentOutput", bound=BaseModel)


class FireworksAgentError(RuntimeError):
    """Raised when Fireworks cannot return a validated structured response."""


class FireworksAgentClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: int,
    ) -> None:
        self._model = model
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def complete(
        self,
        output_type: type[AgentOutput],
        *,
        name: str,
        system_prompt: str,
        input_payload: object,
        max_tokens: int = 4096,
    ) -> AgentOutput:
        prompt = (
            "Return JSON only. Follow the response schema exactly.\n\n"
            + json.dumps(input_payload, ensure_ascii=False, separators=(",", ":"))
        )
        last_error: Exception | None = None
        for _attempt in range(3):
            try:
                response = self._client.post(
                    "/chat/completions",
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": name,
                                "schema": output_type.model_json_schema(),
                            },
                        },
                        "temperature": 0.1,
                        "max_tokens": max_tokens,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise TypeError("Fireworks response content is not text")
                return output_type.model_validate_json(content)
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                TypeError,
                ValidationError,
            ) as exc:
                last_error = exc
        assert last_error is not None
        raise FireworksAgentError(
            f"Fireworks failed to return valid {name} output: {last_error}"
        ) from last_error

    def close(self) -> None:
        self._client.close()
