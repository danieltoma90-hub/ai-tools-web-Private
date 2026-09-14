import json

import httpx
import pytest

import llm_client


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    # `main.py` (importat de `tests/conftest.py`) rulează `load_dotenv()` la
    # colectare, deci `MISTRAL_MODEL` din `backend/.env` (setat separat, ca
    # model funcțional pe tier-ul gratuit) ajunge în mediul procesului de
    # test și nu doar în cel al aplicației reale. Fără curățarea de-aici,
    # testele care presupun modelul implicit ar depinde de ce are `.env` pe
    # mașina care rulează suita, nu de comportamentul din cod.
    monkeypatch.delenv("MISTRAL_MODEL", raising=False)
    monkeypatch.setattr(llm_client, "MIN_CALL_INTERVAL_S", 0)
    monkeypatch.setattr(llm_client, "RETRY_DELAYS", [0, 0, 0])
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0
    yield
    llm_client.TRANSPORT = None


def test_estimate_tokens_romanian_heuristic():
    assert llm_client.estimate_tokens("a" * 220) == 100


def test_budget_counter_and_remaining(monkeypatch):
    monkeypatch.delenv("LLM_DAILY_TOKEN_BUDGET", raising=False)
    assert llm_client.daily_budget() == 2_000_000
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
        assert body["model"] == "ministral-8b-latest"
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


def test_model_unset_uses_default(monkeypatch):
    """MISTRAL_MODEL nesetat foloseste implicitul ministral-8b-latest."""
    monkeypatch.delenv("MISTRAL_MODEL", raising=False)
    assert llm_client._model() == "ministral-8b-latest"


def test_model_empty_string_uses_default(monkeypatch):
    """MISTRAL_MODEL setat la şir gol ("") foloseste implicitul."""
    monkeypatch.setenv("MISTRAL_MODEL", "")
    assert llm_client._model() == "ministral-8b-latest"


def test_model_whitespace_only_uses_default(monkeypatch):
    """MISTRAL_MODEL setat la doar spații albe foloseste implicitul."""
    monkeypatch.setenv("MISTRAL_MODEL", "   ")
    assert llm_client._model() == "ministral-8b-latest"


def test_model_explicit_value_is_used(monkeypatch):
    """MISTRAL_MODEL setat la o valoare reală este folosit corect."""
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-7b-custom")
    assert llm_client._model() == "mistral-7b-custom"


def test_api_key_empty_string_raises(monkeypatch):
    """MISTRAL_API_KEY setat la şir gol ridică eroare clară."""
    monkeypatch.setenv("MISTRAL_API_KEY", "")
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY lipsă"):
        llm_client._api_key()
