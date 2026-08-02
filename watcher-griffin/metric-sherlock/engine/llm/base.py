from abc import ABC, abstractmethod


class LLMProviderBase(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_content: str) -> str:
        """Returns the model's text response. Raises on any provider error --
        narrator.py is responsible for catching and degrading gracefully,
        never this adapter."""
        raise NotImplementedError
