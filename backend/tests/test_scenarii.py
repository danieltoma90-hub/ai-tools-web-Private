import io
from unittest.mock import AsyncMock, patch

from docx import Document

from main import app
from auth import verify_token


def _spec_bytes() -> bytes:
    doc = Document()
    doc.add_heading("Modul Test", level=1)
    doc.add_heading("Capitol Unu", level=2)
    doc.add_paragraph("Descriere functionalitate.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def test_estimate_without_auth_returns_401(client):
    response = await client.post(
        "/api/scenarii/estimate",
        files={"file": ("spec.docx", _spec_bytes(), _DOCX_MIME)},
    )
    assert response.status_code == 401


async def test_estimate_wrong_format_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/scenarii/estimate",
            files={"file": ("spec.pdf", b"pdf", "application/pdf")},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


async def test_estimate_then_generate_then_job_done(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        est_res = await client.post(
            "/api/scenarii/estimate",
            files={"file": ("spec.docx", _spec_bytes(), _DOCX_MIME)},
            headers={"Authorization": "Bearer fake"},
        )
        assert est_res.status_code == 200
        est = est_res.json()
        assert est["modules"] == 1
        assert "estimate_id" in est

        with patch("routers.scenarii.upload_file", return_value="scenarii/x.xlsx"):
            gen_res = await client.post(
                "/api/scenarii/generate",
                json={"estimate_id": est["estimate_id"], "use_ai": False},
                headers={"Authorization": "Bearer fake"},
            )
        assert gen_res.status_code == 200
        job_id = gen_res.json()["job_id"]

        job_res = await client.get(
            f"/api/scenarii/job/{job_id}",
            headers={"Authorization": "Bearer fake"},
        )
        assert job_res.status_code == 200
        job = job_res.json()
        assert job["status"] == "done"
        assert job["ai_used"] is False
        assert job["filename"].endswith(".xlsx")
        assert len(job["scenarios"]) >= 1
        assert job["xlsx_b64"]
    finally:
        app.dependency_overrides.clear()


async def test_generate_with_expired_estimate_returns_404(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/scenarii/generate",
            json={"estimate_id": "inexistent", "use_ai": False},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


async def test_generate_ai_over_budget_returns_422(client, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "10")
    import llm_client
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0

    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        est_res = await client.post(
            "/api/scenarii/estimate",
            files={"file": ("spec.docx", _spec_bytes(), _DOCX_MIME)},
            headers={"Authorization": "Bearer fake"},
        )
        est = est_res.json()
        assert est["fits_budget"] is False

        response = await client.post(
            "/api/scenarii/generate",
            json={"estimate_id": est["estimate_id"], "use_ai": True},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "buget" in response.json()["detail"].lower() or "cota" in response.json()["detail"].lower()


async def test_job_not_found_returns_404(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.get(
            "/api/scenarii/job/nu-exista",
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
