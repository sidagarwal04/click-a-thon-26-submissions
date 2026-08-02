from typing import Optional

from openai import OpenAI

from engine.llm.base import LLMProviderBase


class OpenAIProvider(LLMProviderBase):
    """Also used for Grok (xAI's API is OpenAI-compatible) -- pass
    base_url=settings.grok_base_url and the Grok API key/model to reuse this
    same adapter instead of a separate client implementation."""

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None,
                 max_output_tokens: Optional[int] = None):
        if not api_key:
            raise ValueError("API key is not set for this OpenAI-compatible provider")
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self._model = model
        self._max_output_tokens = max_output_tokens

    def generate(self, system_prompt: str, user_content: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            max_tokens=self._max_output_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return response.choices[0].message.content
