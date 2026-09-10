import asyncio
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
async def test_minuta_endpoint_returns_job_id(client):
    """POST /minuta returnează job_id imediat; procesarea rulează în background."""
    app.dependency_overrides[verify_token] = lambda: {"id": "user1", "email": "test@test.com"}
    try:
        # Patch _run_job sa nu faca nimic (job ramane in 'processing')
        with patch("routers.minuta._run_job", new_callable=AsyncMock):
            response = await client.post(
                "/api/minuta",
                files={"file": ("transcript.vtt", b"WEBVTT\n\n", "text/vtt")},
                headers={"Authorization": "Bearer fake"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert isinstance(body["job_id"], str)
    assert len(body["job_id"]) == 36  # UUID format


@pytest.mark.asyncio
async def test_minuta_preia_fisierul_din_storage(client, tmp_path):
    """Traseul normal: transcriptul urcat direct în Supabase, nu prin proxy.

    Corpul cererii rămâne mic, deci nu mai poate lovi limita de 4,5MB a
    funcțiilor Vercel prin care trece proxy-ul.
    """
    transcript = tmp_path / "abc.vtt"
    transcript.write_bytes(b"WEBVTT\n\n")
    app.dependency_overrides[verify_token] = lambda: {"id": "u1", "email": "t@t.com"}
    try:
        with patch("routers.minuta._run_job", new_callable=AsyncMock) as rulat, \
             patch("routers.minuta.download_upload", return_value=transcript) as descarcat:
            response = await client.post(
                "/api/minuta",
                data={"storage_path": "minuta/abc.vtt", "filename": "Sedinta Godac.vtt"},
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    descarcat.assert_called_once_with("minuta/abc.vtt")
    # numele documentului final vine din numele original, nu din cel din storage
    assert rulat.call_args[0][3] == "Sedinta Godac"


@pytest.mark.asyncio
async def test_minuta_din_storage_cu_extensie_gresita_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/minuta",
            data={"storage_path": "minuta/abc.pdf", "filename": "raport.pdf"},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_minuta_fara_fisier_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/minuta", data={}, headers={"Authorization": "Bearer fake"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_minuta_din_storage_disparut_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        with patch("routers.minuta.download_upload", side_effect=Exception("not found")):
            response = await client.post(
                "/api/minuta",
                data={"storage_path": "minuta/lipsa.vtt", "filename": "x.vtt"},
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "Reîncarcă" in response.json()["detail"]


@pytest.mark.asyncio
async def test_minuta_job_status_done(client, tmp_path):
    """GET /minuta/job/{id} returnează rezultatul când job-ul e done."""
    import jobs
    fake_docx = tmp_path / "out.docx"
    Document().save(str(fake_docx))

    job_id = "test-job-123"
    jobs.finish(
        job_id,
        filename="Minuta_test.docx",
        docx_b64="AAAA",
        preview_html="<html>preview</html>",
        storage_path="minuta/test.docx",
    )

    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        response = await client.get(
            f"/api/minuta/job/{job_id}",
            headers={"Authorization": "Bearer fake"}
        )
    finally:
        app.dependency_overrides.clear()
        jobs._jobs.pop(job_id, None)
        jobs._job_meta.pop(job_id, None)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["docx_b64"] == "AAAA"
    assert body["preview_html"] == "<html>preview</html>"


@pytest.mark.asyncio
async def test_minuta_job_not_found(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "user1"}
    try:
        response = await client.get(
            "/api/minuta/job/nonexistent-id",
            headers={"Authorization": "Bearer fake"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
