from pathlib import Path
from unittest.mock import patch

from main import app
from auth import verify_token

SAMPLE = (
    Path(__file__).parent.parent
    / "skills" / "mockup" / "input"
    / "Ecran generare consum de motorina pe baza de alimentari.docx"
)


def _sample_tempfile() -> Path:
    import os as _os, tempfile as _tf
    fd, name = _tf.mkstemp(suffix=".docx")
    _os.close(fd)
    p = Path(name)
    p.write_bytes(SAMPLE.read_bytes())
    return p


async def test_estimate_without_auth_returns_401(client):
    response = await client.post(
        "/api/mockup/estimate",
        json={"storage_path": "mockup/x.docx", "filename": "t.xlsx"},
    )
    assert response.status_code == 401


async def test_estimate_wrong_format_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/mockup/estimate",
            json={"storage_path": "mockup/x.pdf", "filename": "t.pdf"},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


async def test_estimate_missing_upload_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        with patch("routers.mockup.download_upload", side_effect=Exception("object not found")):
            response = await client.post(
                "/api/mockup/estimate",
                json={"storage_path": "mockup/lipsa.docx", "filename": "spec.docx"},
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "nu a fost găsit" in response.json()["detail"]


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
        with patch("routers.mockup.download_upload", return_value=_sample_tempfile()):
            est_res = await client.post(
                "/api/mockup/estimate",
                json={"storage_path": "mockup/x.docx", "filename": SAMPLE.name},
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


async def test_generate_ai_over_budget_returns_422(client, monkeypatch):
    import pytest
    if not SAMPLE.exists():
        pytest.skip("fișierul exemplu lipsește local")
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "10")
    import llm_client
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0

    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        with patch("routers.mockup.download_upload", return_value=_sample_tempfile()):
            est_res = await client.post(
                "/api/mockup/estimate",
                json={"storage_path": "mockup/x.docx", "filename": SAMPLE.name},
                headers={"Authorization": "Bearer fake"},
            )
        est = est_res.json()
        assert est["fits_budget"] is False

        response = await client.post(
            "/api/mockup/generate",
            json={"estimate_id": est["estimate_id"], "use_ai": True},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "buget" in response.json()["detail"].lower()
