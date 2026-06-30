import asyncio
import base64
import logging
import os
import tempfile
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from auth import verify_token
from pipelines.minuta_pipeline import run_minuta_pipeline
from pipelines.minuta_free_pipeline import run_minuta_free_pipeline
from storage import upload_file

router = APIRouter()
ALLOWED_EXTENSIONS = {".vtt", ".docx"}

# In-memory job store — cleared on each Render restart/redeploy
_jobs: dict[str, dict[str, Any]] = {}


async def _run_job(
    job_id: str,
    input_path: Path,
    api_key: str,
    stem: str,
    timestamp: str,
) -> None:
    try:
        docx_path, preview_html = await run_minuta_pipeline(input_path, api_key)
        filename = f"Minuta_{stem}_{timestamp}.docx"
        user_email = _jobs[job_id].get("user_email", "anonymous")
        storage_path = upload_file(docx_path, tool="minuta", filename=filename, user_email=user_email)
        with open(docx_path, "rb") as f:
            docx_b64 = base64.b64encode(f.read()).decode()
        _jobs[job_id] = {
            "status": "done",
            "filename": filename,
            "docx_b64": docx_b64,
            "preview_html": preview_html,
            "storage_path": storage_path,
        }
        docx_path.unlink(missing_ok=True)
    except Exception as e:
        _jobs[job_id] = {
            "status": "error",
            "error": str(e) or type(e).__name__,
        }
    finally:
        input_path.unlink(missing_ok=True)


@router.post("/minuta")
async def generate_minuta(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    """Pornește procesarea minutei în fundal și returnează un job_id imediat."""
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .vtt sau .docx")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY lipsă pe server")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(await file.read())
        input_path = Path(tmp.name)

    job_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(file.filename).stem

    user_email = getattr(user, "email", None) or "anonymous"
    _jobs[job_id] = {"status": "processing", "user_email": user_email}
    background_tasks.add_task(_run_job, job_id, input_path, api_key, stem, timestamp)

    return {"job_id": job_id}


@router.get("/minuta/job/{job_id}")
async def get_minuta_job(job_id: str, user=Depends(verify_token)):
    """Returnează statusul unui job de generare minută."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job


async def _run_free_job(
    job_id: str,
    input_path: Path,
    api_key: str,
    stem: str,
    timestamp: str,
) -> None:
    async def _on_step(step: str) -> None:
        _jobs[job_id]["step"] = step

    try:
        docx_path, preview_html = await run_minuta_free_pipeline(input_path, api_key, on_step=_on_step)
        filename = f"Minuta_{stem}_{timestamp}.docx"
        user_email = _jobs[job_id].get("user_email", "anonymous")
        storage_path = upload_file(docx_path, tool="minuta", filename=filename, user_email=user_email)
        with open(docx_path, "rb") as f:
            docx_b64 = base64.b64encode(f.read()).decode()
        _jobs[job_id] = {
            "status": "done",
            "filename": filename,
            "docx_b64": docx_b64,
            "preview_html": preview_html,
            "storage_path": storage_path,
        }
        docx_path.unlink(missing_ok=True)
    except Exception as e:
        _jobs[job_id] = {
            "status": "error",
            "error": str(e) or type(e).__name__,
        }
    finally:
        input_path.unlink(missing_ok=True)


@router.post("/minuta-free")
async def generate_minuta_free(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    """Pornește generarea minutei free (Groq/Llama) în fundal și returnează job_id."""
    try:
        filename_raw = file.filename or ""
        ext = Path(filename_raw).suffix.lower() if filename_raw else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=422, detail=f"Fișierul trebuie să fie .vtt sau .docx (primit: '{filename_raw}')")

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY lipsă pe server")

        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            input_path = Path(tmp.name)

        job_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(filename_raw).stem
        user_email = getattr(user, "email", None) or "anonymous"

        _jobs[job_id] = {"status": "processing", "user_email": user_email}
        background_tasks.add_task(_run_free_job, job_id, input_path, api_key, stem, timestamp)
        return {"job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("generate_minuta_free UNEXPECTED: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Eroare neașteptată [{type(e).__name__}]: {e}")
