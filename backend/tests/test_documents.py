import pytest
from unittest.mock import patch
from main import app
from auth import verify_token


@pytest.mark.asyncio
async def test_documents_without_auth_returns_401(client):
    response = await client.get("/api/documents")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_documents_returns_list(client):
    mock_files = [
        {"name": "Minuta_Test.docx", "created_at": "2026-06-25T14:00:00", "metadata": {"size": 5000}},
    ]
    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        with patch("routers.documents.list_files", return_value=mock_files), \
             patch("routers.documents.get_signed_url", return_value="https://supabase.co/signed"):
            response = await client.get(
                "/api/documents",
                headers={"Authorization": "Bearer fake"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Minuta_Test.docx"
    assert "download_url" in data[0]
