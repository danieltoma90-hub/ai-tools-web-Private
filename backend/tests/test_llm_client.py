import json

import httpx
import pytest

import llm_client


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "MIN_CALL_INTERVAL_S", 0)
    monkeypatch.setattr(llm_client, "RETRY_DELAYS", [0, 0, 0])
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0
    yield
    llm_client.TRANSPORT = None


def test_estimate_tokens_romanian_heuristic():
    assert llm_client.estimate_tokens("a" * 220) == 100


def test_budget_counter_and_remaining(monkeypatch):
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "1000")
    assert llm_client.remaining_budget() == 1000
    llm_client.add_usage(300)
    assert llm_client.remaining_budget() == 700


def _mock_response(content: str, total_tokens: int = 50):
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"total_tokens": total_tokens},
    }


async def test_chat_success_returns_content_and_counts_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "mistral-large-latest"
        assert body["response_format"] == {"type": "json_object"}
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json=_mock_response('{"ok": true}', 42))

    llm_client.TRANSPORT = httpx.MockTransport(handler)
    result = await llm_client.chat("sistem", "utilizator")
    assert result == '{"ok": true}'
    assert llm_client._usage["tokens"] == 42


async def test_chat_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"message": "rate limited"})
        return httpx.Response(200, json=_mock_response("ok", 10))

    llm_client.TRANSPORT = httpx.MockTransport(handler)
    result = await llm_client.chat("s", "u", json_mode=False)
    assert result == "ok"
    assert calls["n"] == 2


async def test_chat_raises_after_retry_exhaustion():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "rate limited"})

    llm_client.TRANSPORT = httpx.MockTransport(handler)
    with pytest.raises(RuntimeError, match="429"):
        await llm_client.chat("s", "u")


async def test_chat_without_key_raises(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        await llm_client.chat("s", "u")


def test_parse_json_strips_markdown_fences():
    assert llm_client.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm_client.parse_json('{"a": 1}') == {"a": 1}
