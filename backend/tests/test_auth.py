import pytest
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_health_returns_ok(client):
    # get_supabase mock-uit: /health face acum ping real la Supabase (keep-alive)
    sb = MagicMock()
    sb.storage.list_buckets.return_value = []
    with patch("main.get_supabase", return_value=sb):
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "supabase": "ok"}

@pytest.mark.asyncio
async def test_protected_route_without_token_returns_401(client):
    response = await client.get("/api/documents")
    assert response.status_code == 401
