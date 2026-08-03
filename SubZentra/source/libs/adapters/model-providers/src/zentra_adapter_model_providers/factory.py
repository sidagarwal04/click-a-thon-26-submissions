from __future__ import annotations

from collections.abc import Mapping

from zentra_domain_agent_execution import ModelPort

from .anthropic_client import AnthropicModelClient
from .openai_compatible import OpenAICompatibleModelClient
from .providers import PROVIDERS, Provider


class ProviderClients:
    """Every provider we hold a key for.

    A provider with no key is simply absent, so the router skips its rung. That
    is what lets the whole system run on `ANTHROPIC_API_KEY` alone, exactly as
    it did before routing existed.
    """

    def __init__(self, clients: dict[Provider, ModelPort]) -> None:
        self._clients = clients

    @classmethod
    def from_keys(cls, keys: Mapping[str, str | None]) -> ProviderClients:
        clients: dict[Provider, ModelPort] = {}
        for provider, config in PROVIDERS.items():
            api_key = keys.get(config.env_key)
            if not api_key:
                continue
            if provider is Provider.ANTHROPIC:
                clients[provider] = AnthropicModelClient.from_api_key(api_key)
            else:
                clients[provider] = OpenAICompatibleModelClient.from_api_key(
                    config, api_key
                )
        return cls(clients)

    @property
    def available(self) -> frozenset[Provider]:
        return frozenset(self._clients)

    def as_dict(self) -> dict[Provider, ModelPort]:
        return dict(self._clients)

    async def close(self) -> None:
        for client in self._clients.values():
            close = getattr(client, "close", None)
            if close is not None:
                await close()
