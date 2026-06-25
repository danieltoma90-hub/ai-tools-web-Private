import pytest
from unittest.mock import patch
from main import app
from auth import verify_token


@pytest.mark.asyncio
async def test_scenarii_without_auth_returns_401(client):
    response = await client.post(
        "/api/scenarii",
        files={"file": ("spec.docx", b"PK...", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scenarii_wrong_format_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/scenarii",
            files={"file": ("spec.pdf", b"pdf", "application/pdf")},
            headers={"Authorization": "Bearer fake"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
