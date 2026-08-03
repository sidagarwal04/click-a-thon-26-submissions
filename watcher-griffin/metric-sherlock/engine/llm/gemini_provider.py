"""Gemini narrator backend, on the supported `google-genai` SDK.

Migrated off `google-generativeai`, which is end-of-life: importing it prints
"All support for the `google.generativeai` package has ended" and its repo is
now literally named `deprecated-generative-ai-python`. That package still
reached the API when this was written, so the migration is about getting an
unmaintained dependency out of the narration path before it breaks -- it was
never the cause of a narration failure.

The thinking config is why a narration now takes ~1.4s instead of ~22s. See
engine/config.py's gemini_thinking_level for the measurement; the short version
is that this narrator is forbidden to reason about numbers (it restates what
ClickHouse already computed), so extended thinking bought nothing and cost 16x.
"""

import logging
from typing import Optional

from google import genai
from google.genai import types

from engine.llm.base import LLMProviderBase

logger = logging.getLogger(__name__)

# The sentinel meaning "send no thinking config at all" -- i.e. whatever the model
# defaults to. Kept so the pre-measurement behaviour is reachable from the
# environment (GEMINI_THINKING_LEVEL=default) rather than only by editing code.
_INHERIT = "default"


class GeminiProvider(LLMProviderBase):
    def __init__(self, api_key: str, model: str, thinking_level: str = _INHERIT,
                 max_output_tokens: Optional[int] = None):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        # One client, reused across calls. (The old implementation built a
        # model object in __init__, discarded it, and rebuilt another one on
        # every single generate() call.) engine/llm/__init__.py now caches the
        # provider itself, so this client's connection pool is reused across
        # narrations and chat turns instead of re-handshaking on each one.
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._thinking_level = (thinking_level or _INHERIT).strip().lower()
        self._max_output_tokens = max_output_tokens
        # Checked here, once, because the SDK does NOT reject an unknown level: it
        # emits a UserWarning and sends the string anyway, so a mistyped
        # GEMINI_THINKING_LEVEL would travel all the way to the API and come back as
        # a failed generation -- i.e. it would read as "narration unavailable" rather
        # than as a bad setting. The accepted values are read off the SDK's own enum
        # rather than hardcoded, so a level a future SDK adds is accepted here without
        # this list needing to be remembered.
        if self._thinking_level != _INHERIT and not self._level_is_known():
            logger.warning(
                "GEMINI_THINKING_LEVEL=%r is not a level this SDK knows; falling back "
                "to the model's own default.", self._thinking_level,
            )
            self._thinking_level = _INHERIT
        # Latched True once the configured model has told us it does not accept
        # `thinking_level` (the 2.5 generation takes `thinking_budget` instead, and
        # a future model may take neither). Per process, so a rejection is paid once
        # rather than per call, and the fallback is today's behaviour rather than a
        # failed narration.
        self._thinking_unsupported = False

    def _level_is_known(self) -> bool:
        try:
            return self._thinking_level in {str(e.value).lower() for e in types.ThinkingLevel}
        except Exception:
            # An SDK with no such enum cannot tell us; let the request decide, and the
            # rejection path below handle it.
            return True

    def _config(self, system_prompt: str, with_thinking: bool) -> types.GenerateContentConfig:
        cfg = types.GenerateContentConfig(system_instruction=system_prompt, temperature=0)
        constrained = with_thinking and self._thinking_level != _INHERIT and not self._thinking_unsupported
        if constrained:
            cfg.thinking_config = types.ThinkingConfig(thinking_level=self._thinking_level)
        # The output cap is only applied when thinking IS constrained, and that pairing
        # is not fussiness -- it was observed. Thinking tokens are drawn from the same
        # max_output_tokens budget, so a 512-token cap against unconstrained thinking
        # (which measured 6,911 thinking tokens on one narration) spends the whole
        # budget before the answer starts and returns a sentence cut off mid-word:
        # "...CPM campaign revenue falling from 698,274". A truncated narration is
        # worse than a slow one, because it still reads like an answer.
        if constrained and self._max_output_tokens:
            cfg.max_output_tokens = self._max_output_tokens
        return cfg

    def generate(self, system_prompt: str, user_content: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_content,
                config=self._config(system_prompt, with_thinking=True),
            )
        except Exception as e:
            # ONLY a rejection of the thinking knob is retried without it. Anything
            # else (bad key, quota, network) propagates untouched, so narrator.py
            # degrades to "narration unavailable" with the real reason attached
            # instead of the error being reshaped into a second, misleading one.
            if not self._is_thinking_rejection(e):
                raise
            self._thinking_unsupported = True
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_content,
                config=self._config(system_prompt, with_thinking=False),
            )
        return self._text_with_one_retry(response, system_prompt, user_content)

    def _text_with_one_retry(self, response, system_prompt: str, user_content: str):
        """`response.text`, retried ONCE when the API returns no text part.

        Observed on a real narration: two consecutive calls came back with
        finish_reason=STOP, no thinking tokens, and either None or a bare '\\n' --
        then the identical payload succeeded with 234 output tokens. So an empty
        text part is a transient upstream condition here, not a symptom of the
        prompt, and one retry converts it into the answer that was always available.

        Deliberately narrow:
          * ONE retry, not a loop -- narration is on the interactive path, and a
            provider that is genuinely returning nothing must surface quickly as
            "narration unavailable" rather than multiplying the latency.
          * MAX_TOKENS is NEVER retried. That is the thinking-budget trap in
            _config(), where the model spent the whole cap before answering; the
            identical request would spend it again. It needs a config change, so
            retrying would only hide it -- and the empty/truncated result still
            degrades safely through narrator.py's own emptiness check.
        """
        if response.text and response.text.strip():
            return response.text
        if self._finish_reason(response) == "MAX_TOKENS":
            return response.text
        retry = self._client.models.generate_content(
            model=self._model,
            contents=user_content,
            config=self._config(system_prompt, with_thinking=True),
        )
        return retry.text

    @staticmethod
    def _finish_reason(response) -> str:
        """The first candidate's finish reason as a bare string, or '' if absent.

        Defensive because it is only used to decide whether retrying is pointless:
        a driver that reshapes this field must cost us one wasted retry, never an
        AttributeError on the narration path.
        """
        try:
            candidates = getattr(response, "candidates", None) or []
            if not candidates:
                return ""
            reason = getattr(candidates[0], "finish_reason", None)
            return getattr(reason, "name", None) or str(reason or "")
        except Exception:
            return ""

    def _is_thinking_rejection(self, exc: Exception) -> bool:
        if self._thinking_level == _INHERIT or self._thinking_unsupported:
            return False
        msg = str(exc).lower()
        if "thinking" not in msg:
            return False
        return any(w in msg for w in ("not supported", "unsupported", "invalid", "unknown"))
