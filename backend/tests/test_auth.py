import pytest

@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_protected_route_without_token_returns_401(client):
    response = await client.get("/api/documents")
    assert response.status_code == 401
