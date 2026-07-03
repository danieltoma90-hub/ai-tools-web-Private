from pathlib import Path
from unittest.mock import AsyncMock, patch

from main import app
from auth import verify_token

SAMPLE = (
    Path(__file__).parent.parent
    / "skills" / "mockup" / "input"
    / "Ecran generare consum de motorina pe baza de alimentari.docx"
)
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def test_estimate_without_auth_returns_401(client):
    response = await client.post(
        "/api/mockup/estimate",
        files={"file": ("t.xlsx", b"PK...", "application/octet-stream")},
    )
    assert response.status_code == 401


async def test_estimate_wrong_format_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/mockup/estimate",
            files={"file": ("t.pdf", b"pdf", "application/pdf")},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


async def test_generate_with_expired_estimate_returns_404(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/mockup/generate",
            json={"estimate_id": "inexistent", "use_ai": False},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


async def test_estimate_then_generate_then_job_done(client):
    import pytest
    if not SAMPLE.exists():
        pytest.skip("fișierul exemplu lipsește local")

    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        est_res = await client.post(
            "/api/mockup/estimate",
            files={"file": (SAMPLE.name, SAMPLE.read_bytes(), _DOCX_MIME)},
            headers={"Authorization": "Bearer fake"},
        )
        assert est_res.status_code == 200
        est = est_res.json()
        assert est["est_tokens"] > 0

        with patch("routers.mockup.upload_file", return_value="mockup/x.docx"):
            gen_res = await client.post(
                "/api/mockup/generate",
                json={"estimate_id": est["estimate_id"], "use_ai": False},
                headers={"Authorization": "Bearer fake"},
            )
        assert gen_res.status_code == 200
        job_id = gen_res.json()["job_id"]

        job_res = await client.get(
            f"/api/mockup/job/{job_id}",
            headers={"Authorization": "Bearer fake"},
        )
        job = job_res.json()
        assert job["status"] == "done"
        assert job["ai_used"] is False
        assert job["filename"].endswith(".docx")
        assert job["docx_b64"]
        assert "<html" in job["html"].lower()
    finally:
        app.dependency_overrides.clear()
