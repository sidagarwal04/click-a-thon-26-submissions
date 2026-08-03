"""The OpenAI-compatible backend, and the bake-off's scoring shape.

Added so the pipeline can run on models other than Claude -- which is what makes a
model comparison possible at all. Network calls are not made here; the contract this
pins is request construction, error surfacing, and backend dispatch.
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

import llm


def test_openai_backend_is_dispatched() -> None:
    """A new backend that silently falls through to the Anthropic path would look like
    it worked while comparing the wrong model."""
    with mock.patch.object(llm, "BACKEND", "openai"), \
         mock.patch.object(llm, "_openai_call", return_value=("{}", {})) as m:
        llm._call("sys", "usr", "gpt-oss:20b", 1000)
    assert m.called, "BACKEND=openai must route to _openai_call"


def test_other_backends_still_dispatch_correctly() -> None:
    with mock.patch.object(llm, "BACKEND", "cli"), \
         mock.patch.object(llm, "_cli_call", return_value=("{}", {})) as m:
        llm._call("sys", "usr", "claude-sonnet-5", 1000)
    assert m.called
    with mock.patch.object(llm, "BACKEND", "api"), \
         mock.patch.object(llm, "_api_call", return_value=("{}", {})) as m:
        llm._call("sys", "usr", "claude-sonnet-5", 1000)
    assert m.called


def test_missing_key_fails_loudly_rather_than_sending_an_anonymous_request() -> None:
    with mock.patch.dict("os.environ", {"ATLYS_LLM_API_KEY": "", "OLLAMA_API_KEY": ""}, clear=False):
        with pytest.raises(RuntimeError, match="ATLYS_LLM_API_KEY"):
            llm._openai_call("sys", "usr", "gpt-oss:20b", 100)


def test_request_shape_is_openai_chat_completions() -> None:
    captured: dict = {}

    class _Resp:
        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": '{"ok":1}'}}],
                 "usage": {"prompt_tokens": 11, "completion_tokens": 22}}
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
        captured["body"] = json.loads(req.data)
        return _Resp()

    with mock.patch.dict("os.environ", {"ATLYS_LLM_API_KEY": "test-key-12345"}, clear=False), \
         mock.patch("urllib.request.urlopen", _fake_urlopen):
        text, stats = llm._openai_call("SYSTEM", "USER", "gpt-oss:20b", 500)

    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["authorization"] == "Bearer test-key-12345"
    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["system", "user"]
    assert captured["body"]["model"] == "gpt-oss:20b"
    assert text == '{"ok":1}'
    # Token accounting must map OpenAI's names onto ours, or usage silently reads zero.
    assert stats["input_tokens"] == 11 and stats["output_tokens"] == 22


def test_http_error_names_the_model_and_status() -> None:
    """A 403 here is a plan/tier restriction, not a bad key -- measured: the same key
    that serves gpt-oss:* is refused for the larger hosted models. The error has to say
    which model, or a bake-off row is unexplainable."""
    import urllib.error

    def _boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    with mock.patch.dict("os.environ", {"ATLYS_LLM_API_KEY": "k"}, clear=False), \
         mock.patch("urllib.request.urlopen", _boom):
        with pytest.raises(RuntimeError) as exc:
            llm._openai_call("s", "u", "glm-5.2", 100)
    assert "403" in str(exc.value) and "glm-5.2" in str(exc.value)


def test_bakeoff_matrix_is_well_formed() -> None:
    from tools import model_bakeoff as bo

    assert bo.DEFAULT_MODELS, "matrix must not be empty"
    for spec in bo.DEFAULT_MODELS:
        backend = spec.split(":", 1)[0]
        assert backend in {"cli", "api", "openai", "mock"}, spec
    # A DISPUTED-metric question must be in the set, or refusal behaviour is untested
    # on every model.
    assert any("conversion rate" in q.lower() for q in bo.QUESTIONS)
