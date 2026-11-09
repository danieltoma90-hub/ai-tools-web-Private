import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

import jobs
from auth import verify_token  # noqa: F401
from acces import cere_modul
from pipelines.mockup_pipeline import run_mockup_pipeline, verifica_fisierul
from storage import download_upload

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".docx"}


class GenerateRequest(BaseModel):
    storage_path: str
    filename: str


async def _run_job(job_id: str, input_path: Path, orig_filename: str) -> None:
    async def lucrare() -> dict:
        docx_path, html, ai_used, motiv_fara_ai = await run_mockup_pipeline(
            input_path, on_step=lambda step: jobs.set_step(job_id, step),
        )
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{Path(orig_filename).stem}_{timestamp}.docx"
            storage_path, docx_b64 = jobs.livreaza(job_id, docx_path, tool="mockup", filename=filename)
        finally:
            docx_path.unlink(missing_ok=True)
        return {
            "filename": filename,
            "docx_b64": docx_b64,
            "html": html,
            "ai_used": ai_used,
            "motiv_fara_ai": motiv_fara_ai,
            "storage_path": storage_path,
        }

    try:
        await jobs.ruleaza(job_id, lucrare)
    finally:
        input_path.unlink(missing_ok=True)


@router.post("/mockup/generate")
async def generate_mockup(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    user=Depends(cere_modul("mockup")),
):
    """Fișierul e deja în Supabase Storage (urcat direct din browser): îl citim pe
    loc, ca un ecran nerecunoscut să primească răspuns imediat, apoi pornim
    generarea în fundal."""
    if Path(req.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .xlsx sau .docx")

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
        verifica_fisierul(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Fișier invalid: {e}")

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email, "mockup")
    background_tasks.add_task(_run_job, job_id, input_path, req.filename)
    return {"job_id": job_id}


@router.get("/mockup/job/{job_id}")
async def get_mockup_job(job_id: str, user=Depends(cere_modul("mockup"))):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
