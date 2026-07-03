import base64
import logging
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

import jobs
from auth import verify_token
from pipelines.scenarii_pipeline import estimate_scenarii_job, run_scenarii_pipeline
from storage import upload_file

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateRequest(BaseModel):
    estimate_id: str
    use_ai: bool = True


@router.post("/scenarii/estimate")
async def estimate_scenarii(
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    """Pas 1: încarcă spec-ul, întoarce estimarea de tokeni. Fișierul se păstrează ~10 min."""
    filename_raw = file.filename or ""
    if Path(filename_raw).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .docx")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(await file.read())
        input_path = Path(tmp.name)

    try:
        est = estimate_scenarii_job(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Fișier .docx invalid: {e}")

    estimate_id = jobs.save_estimate(input_path, filename_raw, est)
    return {"estimate_id": estimate_id, **est}


async def _run_job(job_id: str, input_path: Path, orig_filename: str, use_ai: bool) -> None:
    def _on_step(step: str) -> None:
        jobs.set_step(job_id, step)

    xlsx_path: Path | None = None
    try:
        xlsx_path, scenarios = await run_scenarii_pipeline(input_path, use_ai=use_ai, on_step=_on_step)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Scenarii_{Path(orig_filename).stem}_{timestamp}.xlsx"
        job = jobs.get_job(job_id) or {}
        storage_path = upload_file(
            xlsx_path, tool="scenarii", filename=filename,
            user_email=job.get("user_email", "anonymous"),
        )
        with open(xlsx_path, "rb") as f:
            xlsx_b64 = base64.b64encode(f.read()).decode()
        ai_used = use_ai and any(s.get("ai") for s in scenarios)
        jobs.finish(
            job_id,
            filename=filename,
            xlsx_b64=xlsx_b64,
            scenarios=scenarios,
            ai_used=ai_used,
            storage_path=storage_path,
        )
    except Exception as e:
        logger.error("scenarii job %s FAILED: %s\n%s", job_id, e, traceback.format_exc())
        jobs.fail(job_id, str(e) or type(e).__name__)
    finally:
        input_path.unlink(missing_ok=True)
        if xlsx_path is not None:
            xlsx_path.unlink(missing_ok=True)


@router.post("/scenarii/generate")
async def generate_scenarii(
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
            detail="Bugetul zilnic gratuit de tokeni nu ajunge pentru acest fișier. "
                   "Continuă fără AI sau revino mâine.",
        )

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email)
    background_tasks.add_task(_run_job, job_id, Path(est["file_path"]), est["filename"], req.use_ai)
    return {"job_id": job_id}


@router.get("/scenarii/job/{job_id}")
async def get_scenarii_job(job_id: str, user=Depends(verify_token)):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
