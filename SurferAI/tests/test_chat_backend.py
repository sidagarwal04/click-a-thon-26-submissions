from unittest.mock import patch

from atlys_agentic.run_chat import app


def test_chat_completions_returns_openai_shaped_response():
    fake_result = {
        "answer_md": "Express lifts conversion 8% overall.",
        "confidence": {"score": 0.75, "rationale": "r"},
        "known_issue_match": False,
        "cuts": {"device_type": []},
        "trace_id": "trace-42",
    }
    with patch("atlys_agentic.run_chat.analysis_flow.run", return_value=fake_result) as mock_run:
        try:
            from fastapi.testclient import TestClient
            client = TestClient(app)
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "atlys-analyst",
                    "messages": [{"role": "user", "content": "Does Express lift conversion?"}],
                },
            )
            assert response.status_code == 200
            body = response.json()
        except ImportError:
            # Direct handler invocation if testclient is not available
            from atlys_agentic.run_chat import ChatCompletionRequest, ChatMessage, chat_completions
            body = chat_completions(ChatCompletionRequest(
                model="atlys-analyst",
                messages=[ChatMessage(role="user", content="Does Express lift conversion?")]
            ))

    content = body["choices"][0]["message"]["content"]
    assert fake_result["answer_md"] in content
    assert "0.75" in content
    assert "trace-42" in content
    assert body["object"] == "chat.completion"
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["question"] == "Does Express lift conversion?"


def test_healthz_endpoint():
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    except ImportError:
        from atlys_agentic.run_chat import healthz
        assert healthz() == {"status": "ok"}
