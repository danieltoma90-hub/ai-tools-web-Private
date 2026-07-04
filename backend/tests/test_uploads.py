from unittest.mock import patch

from main import app
from auth import verify_token


async def test_sign_without_auth_returns_401(client):
    response = await client.post(
        "/api/uploads/sign", json={"filename": "spec.docx", "tool": "scenarii"}
    )
    assert response.status_code == 401


async def test_sign_returns_signed_url(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        with patch(
            "routers.uploads.create_upload_url",
            return_value={
                "storage_path": "scenarii/abc.docx",
                "signed_url": "https://x/upload?token=T",
                "token": "T",
            },
        ) as mock_sign:
            response = await client.post(
                "/api/uploads/sign",
                json={"filename": "spec.docx", "tool": "scenarii"},
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["storage_path"] == "scenarii/abc.docx"
    assert body["token"] == "T"
    mock_sign.assert_called_once_with("scenarii", "spec.docx")


async def test_sign_invalid_tool_or_ext_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        with patch("routers.uploads.create_upload_url", side_effect=ValueError("Extensie neacceptată")):
            response = await client.post(
                "/api/uploads/sign",
                json={"filename": "spec.pdf", "tool": "scenarii"},
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "neacceptat" in response.json()["detail"].lower()
