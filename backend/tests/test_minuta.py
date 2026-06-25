import pytest
from unittest.mock import patch, AsyncMock
from docx import Document
from main import app
from auth import verify_token


@pytest.mark.asyncio
async def test_minuta_endpoint_without_auth_returns_401(client):
    response = await client.post("/api/minuta", files={"file": ("t.vtt", b"WEBVTT", "text/vtt")})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_minuta_endpoint_wrong_format_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        response = await client.post(
            "/api/minuta",
            files={"file": ("doc.pdf", b"pdf content", "application/pdf")},
            headers={"Authorization": "Bearer fake"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "vtt" in response.json()["detail"].lower() or "docx" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_minuta_endpoint_returns_docx_and_html(client, tmp_path):
    fake_docx = tmp_path / "out.docx"
    Document().save(str(fake_docx))

    app.dependency_overrides[verify_token] = lambda: {"id": "user1", "email": "test@test.com"}
    try:
        with patch("routers.minuta.run_minuta_pipeline", new_callable=AsyncMock,
                   return_value=(fake_docx, "<html>preview</html>")), \
             patch("routers.minuta.upload_file", return_value="minuta/test.docx"):
            response = await client.post(
                "/api/minuta",
                files={"file": ("transcript.vtt", b"WEBVTT\n\n", "text/vtt")},
                headers={"Authorization": "Bearer fake"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "docx_b64" in body
    assert "preview_html" in body
    assert "filename" in body
    assert body["preview_html"] == "<html>preview</html>"
