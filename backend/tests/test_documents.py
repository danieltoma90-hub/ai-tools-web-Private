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


class _FakeUser:
    """Ca obiectul supabase User din productie: are .email, NU are .get()."""
    email = "ana@totalsoft.ro"


@pytest.mark.asyncio
async def test_delete_document_works_with_user_object(client):
    app.dependency_overrides[verify_token] = lambda: _FakeUser()
    try:
        with patch("routers.documents.delete_file") as mock_del:
            response = await client.delete(
                "/api/documents?storage_path=mockup/ana@totalsoft.ro/x.docx",
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_del.assert_called_once_with("mockup/ana@totalsoft.ro/x.docx")


@pytest.mark.asyncio
async def test_delete_document_foreign_owner_returns_403(client):
    app.dependency_overrides[verify_token] = lambda: _FakeUser()
    try:
        with patch("routers.documents.delete_file") as mock_del:
            response = await client.delete(
                "/api/documents?storage_path=mockup/altcineva@totalsoft.ro/x.docx",
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    mock_del.assert_not_called()
