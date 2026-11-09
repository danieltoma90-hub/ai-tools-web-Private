import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

import jobs
from auth import verify_token  # noqa: F401
from acces import cere_modul
from pipelines.scenarii_pipeline import run_scenarii_pipeline, verifica_specificatia
from storage import download_upload

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateRequest(BaseModel):
    storage_path: str
    filename: str


async def _run_job(job_id: str, input_path: Path, orig_filename: str) -> None:
    async def lucrare() -> dict:
        xlsx_path, summary = await run_scenarii_pipeline(
            input_path, on_step=lambda step: jobs.set_step(job_id, step),
        )
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Scenarii_{Path(orig_filename).stem}_{timestamp}.xlsx"
            storage_path, xlsx_b64 = jobs.livreaza(job_id, xlsx_path, tool="scenarii", filename=filename)
        finally:
            xlsx_path.unlink(missing_ok=True)
        return {
            "filename": filename,
            "xlsx_b64": xlsx_b64,
            "summary": summary,
            "storage_path": storage_path,
        }

    try:
        await jobs.ruleaza(job_id, lucrare)
    finally:
        input_path.unlink(missing_ok=True)


@router.post("/scenarii/generate")
async def generate_scenarii(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    user=Depends(cere_modul("scenarii")),
):
    """Specificația e deja în Supabase Storage (urcată direct din browser): o citim
    pe loc, ca un fișier invalid să primească răspuns imediat, apoi pornim
    generarea în fundal."""
    if Path(req.filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .docx")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY lipsă pe server")

    try:
        input_path = download_upload(req.storage_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Fișierul încărcat nu a fost găsit în storage — reîncarcă fișierul.",
        )

    try:
        verifica_specificatia(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Fișier .docx invalid: {e}")

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email, "scenarii")
    background_tasks.add_task(_run_job, job_id, input_path, req.filename)
    return {"job_id": job_id}


@router.get("/scenarii/job/{job_id}")
async def get_scenarii_job(job_id: str, user=Depends(cere_modul("scenarii"))):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
