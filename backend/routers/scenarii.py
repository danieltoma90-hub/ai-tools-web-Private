import base64
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

import jobs
from auth import verify_token
from pipelines.scenarii_pipeline import estimate_scenarii_job, run_scenarii_pipeline
from storage import download_upload, upload_file

logger = logging.getLogger(__name__)
router = APIRouter()


class EstimateRequest(BaseModel):
    storage_path: str
    filename: str


class GenerateRequest(BaseModel):
    estimate_id: str
    engine: str = "claude"  # "claude" (credite API) | "groq" (gratuit)


@router.post("/scenarii/estimate")
async def estimate_scenarii(
    req: EstimateRequest,
    user=Depends(verify_token),
):
    """Pas 1: fișierul e deja în Supabase Storage (upload direct din browser).

    Îl descărcăm local, estimăm, și-l păstrăm ~10 min pentru generate.
    """
    if Path(req.filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .docx")

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
        est = estimate_scenarii_job(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Fișier .docx invalid: {e}")

    estimate_id = jobs.save_estimate(input_path, req.filename, est)
    return {"estimate_id": estimate_id, **est}


async def _run_job(job_id: str, input_path: Path, orig_filename: str, engine: str) -> None:
    def _on_step(step: str) -> None:
        jobs.set_step(job_id, step)

    xlsx_path: Path | None = None
    try:
        xlsx_path, summary = await run_scenarii_pipeline(input_path, engine=engine, on_step=_on_step)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Scenarii_{Path(orig_filename).stem}_{timestamp}.xlsx"
        job = jobs.get_job(job_id) or {}
        storage_path = upload_file(
            xlsx_path, tool="scenarii", filename=filename,
            user_email=job.get("user_email", "anonymous"),
        )
        with open(xlsx_path, "rb") as f:
            xlsx_b64 = base64.b64encode(f.read()).decode()
        jobs.finish(
            job_id,
            filename=filename,
            xlsx_b64=xlsx_b64,
            summary=summary,
            engine=engine,
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
    """Pas 2: pornește generarea (Claude sau Groq gratuit) pe fișierul din estimare."""
    if req.engine not in ("claude", "groq"):
        raise HTTPException(status_code=422, detail="engine trebuie să fie 'claude' sau 'groq'")

    est = jobs.pop_estimate(req.estimate_id)
    if est is None:
        raise HTTPException(
            status_code=404,
            detail="Estimarea a expirat sau serverul a fost repornit — reîncarcă fișierul.",
        )

    key_env = "ANTHROPIC_API_KEY" if req.engine == "claude" else "GROQ_API_KEY"
    if not os.environ.get(key_env):
        Path(est["file_path"]).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"{key_env} lipsă pe server")

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email)
    background_tasks.add_task(_run_job, job_id, Path(est["file_path"]), est["filename"], req.engine)
    return {"job_id": job_id}


@router.get("/scenarii/job/{job_id}")
async def get_scenarii_job(job_id: str, user=Depends(verify_token)):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
