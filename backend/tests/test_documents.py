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
        {"name": "Minuta_Test.docx", "storage_path": "minuta/ana/Minuta_Test.docx",
         "created_at": "2026-06-25T14:00:00", "metadata": {"size": 5000}},
    ]
    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        with patch("routers.documents.list_files", return_value=mock_files), \
             patch("routers.documents.get_signed_urls",
                   return_value={"minuta/ana/Minuta_Test.docx": "https://supabase.co/signed"}):
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


def _fisiere(n: int) -> list[dict]:
    return [
        {
            "name": f"Doc_{i}.docx",
            "storage_path": f"minuta/ana/Doc_{i}.docx",
            "created_at": f"2026-06-{25 - i:02d}T14:00:00",
            "metadata": {"size": 5000},
        }
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_limit_taie_lista_inainte_de_semnare(client):
    """Panoul „Recent" cere 5: semnarea celorlalte ar fi munca aruncata."""
    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        with patch("routers.documents.list_files", return_value=_fisiere(40)), \
             patch("routers.documents.get_signed_urls", return_value={}) as mock_sign:
            response = await client.get(
                "/api/documents?tool=minuta&limit=5",
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 5
    assert len(mock_sign.call_args[0][0]) == 5


@pytest.mark.asyncio
async def test_fara_limit_intoarce_tot(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        with patch("routers.documents.list_files", return_value=_fisiere(12)), \
             patch("routers.documents.get_signed_urls", return_value={}):
            response = await client.get(
                "/api/documents", headers={"Authorization": "Bearer fake"}
            )
    finally:
        app.dependency_overrides.clear()
    assert len(response.json()) == 12


@pytest.mark.asyncio
async def test_tool_necunoscut_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        response = await client.get(
            "/api/documents?tool=../secret", headers={"Authorization": "Bearer fake"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_limit_zero_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        response = await client.get(
            "/api/documents?limit=0", headers={"Authorization": "Bearer fake"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_storage_usage_returns_percent(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        with patch(
            "routers.documents.get_storage_usage",
            return_value={"used_bytes": 950, "quota_bytes": 1000, "percent": 95.0},
        ):
            response = await client.get(
                "/api/storage/usage",
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["percent"] == 95.0
    assert data["quota_bytes"] == 1000


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
