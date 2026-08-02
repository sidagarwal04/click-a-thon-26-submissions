from typing import Optional

import anthropic

from engine.llm.base import LLMProviderBase


class AnthropicProvider(LLMProviderBase):
    def __init__(self, api_key: str, model: str, max_output_tokens: Optional[int] = None):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        # settings.llm_max_output_tokens, so every provider is capped from the same
        # place rather than each carrying its own hardcoded ceiling.
        self._max_output_tokens = max_output_tokens or 1024

    def generate(self, system_prompt: str, user_content: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_output_tokens,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
