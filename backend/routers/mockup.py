import base64
import logging
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

import jobs
from auth import verify_token
from pipelines.mockup_pipeline import estimate_mockup_job, run_mockup_pipeline
from storage import download_upload, upload_file

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".docx"}


class EstimateRequest(BaseModel):
    storage_path: str
    filename: str


class GenerateRequest(BaseModel):
    estimate_id: str
    use_ai: bool = True


@router.post("/mockup/estimate")
async def estimate_mockup(
    req: EstimateRequest,
    user=Depends(verify_token),
):
    """Pas 1: fișierul e deja în Supabase Storage (upload direct din browser).

    Îl descărcăm local, estimăm, și-l păstrăm ~10 min pentru generate.
    """
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
        est = estimate_mockup_job(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Fișier invalid: {e}")

    estimate_id = jobs.save_estimate(input_path, req.filename, est)
    return {"estimate_id": estimate_id, **est}


async def _run_job(job_id: str, input_path: Path, orig_filename: str, use_ai: bool) -> None:
    def _on_step(step: str) -> None:
        jobs.set_step(job_id, step)

    docx_path: Path | None = None
    try:
        docx_path, html, ai_used = await run_mockup_pipeline(input_path, use_ai=use_ai, on_step=_on_step)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{Path(orig_filename).stem}_{timestamp}.docx"
        job = jobs.get_job(job_id) or {}
        storage_path = upload_file(
            docx_path, tool="mockup", filename=filename,
            user_email=job.get("user_email", "anonymous"),
        )
        with open(docx_path, "rb") as f:
            docx_b64 = base64.b64encode(f.read()).decode()
        jobs.finish(
            job_id,
            filename=filename,
            docx_b64=docx_b64,
            html=html,
            ai_used=ai_used,
            storage_path=storage_path,
        )
    except Exception as e:
        logger.error("mockup job %s FAILED: %s\n%s", job_id, e, traceback.format_exc())
        jobs.fail(job_id, str(e) or type(e).__name__)
    finally:
        input_path.unlink(missing_ok=True)
        if docx_path is not None:
            docx_path.unlink(missing_ok=True)


@router.post("/mockup/generate")
async def generate_mockup(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    user=Depends(verify_token),
):
    """Pas 2: pornește generarea (cu sau fără AI) pe fișierul din estimare."""
    est = jobs.pop_estimate(req.estimate_id)
    if est is None:
        raise HTTPException(
            status_code=404,
            detail="Estimarea a expirat sau serverul a fost repornit — reîncarcă fișierul.",
        )
    if req.use_ai and not est.get("fits_budget", False):
        Path(est["file_path"]).unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail="Fișierul necesită mai mulți tokeni decât bugetul zilnic gratuit disponibil. "
                   "Continuă fără AI, revino mâine sau mărește LLM_DAILY_TOKEN_BUDGET.",
        )

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email)
    background_tasks.add_task(_run_job, job_id, Path(est["file_path"]), est["filename"], req.use_ai)
    return {"job_id": job_id}


@router.get("/mockup/job/{job_id}")
async def get_mockup_job(job_id: str, user=Depends(verify_token)):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
