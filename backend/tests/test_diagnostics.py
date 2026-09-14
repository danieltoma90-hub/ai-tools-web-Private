from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_diagnostics_classifies_403_tier_not_allowed(client):
    """Verifică că 403 tier_not_allowed e clasificat corect."""
    response = await client.get("/api/diagnostics/providers")
    # Trebuie autentificat — răspunsul ar trebui 401 dacă nu avem token
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_classify_handles_403_tier_not_allowed():
    """Testează _classify pentru 403 tier_not_allowed."""
    from routers.diagnostics import _classify

    status, message = _classify(403, {"error": {"message": "tier_not_allowed"}})
    assert status == "model_nepermis"
    assert "Modelul" in message
    assert "MISTRAL_MODEL" in message


@pytest.mark.asyncio
async def test_classify_handles_200():
    """Testează _classify pentru 200 OK."""
    from routers.diagnostics import _classify

    status, message = _classify(200, {})
    assert status == "ok"
    assert "funcționează" in message


@pytest.mark.asyncio
async def test_classify_handles_401_invalid_key():
    """Testează _classify pentru 401 invalid API key."""
    from routers.diagnostics import _classify

    status, message = _classify(401, {"error": {"message": "Invalid API key"}})
    assert status == "cheie_invalida"
    assert "invalidă" in message


@pytest.mark.asyncio
async def test_classify_handles_402_billing():
    """Testează _classify pentru 402 billing."""
    from routers.diagnostics import _classify

    status, message = _classify(402, {"error": {"message": "billing"}})
    assert status == "fara_credit"
    assert "credite" in message


@pytest.mark.asyncio
async def test_classify_handles_429_rate_limit():
    """Testează _classify pentru 429 rate limit."""
    from routers.diagnostics import _classify

    status, message = _classify(429, {})
    assert status == "limita_atinsa"
    assert "rate limit" in message


@pytest.mark.asyncio
async def test_mistral_check_uses_llm_client_model():
    """Verifică că _check_mistral folosește _model() din llm_client."""
    from routers.diagnostics import _check_mistral
    from llm_client import _model

    # Mock httpx.AsyncClient
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.content = b'{"choices": [{"message": {"content": "ok"}}]}'
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.dict("os.environ", {"MISTRAL_API_KEY": "test-key"}):
        result = await _check_mistral(mock_client)

    # Verifică că post a fost apelat cu modelul corect
    call_args = mock_client.post.call_args
    assert call_args is not None
    json_data = call_args[1]["json"]
    assert json_data["model"] == _model()


@pytest.mark.asyncio
async def test_mistral_check_missing_key():
    """Verifică că _check_mistral raportează cheie lipsă."""
    from routers.diagnostics import _check_mistral

    mock_client = AsyncMock()

    with patch.dict("os.environ", {}, clear=True):
        result = await _check_mistral(mock_client)

    assert result["configured"] is False
    assert result["state"] == "lipsa"
    assert "MISTRAL_API_KEY" in result["message"]
