from engine.llm.base import LLMProviderBase


class StubProvider(LLMProviderBase):
    """No real LLM call -- used by tests and by LLM_PROVIDER=stub dry runs so
    the pipeline's wiring can be exercised without an API key or cost."""

    def generate(self, system_prompt: str, user_content: str) -> str:
        return f"[stub narration -- no LLM configured] evidence length={len(user_content)} chars"
