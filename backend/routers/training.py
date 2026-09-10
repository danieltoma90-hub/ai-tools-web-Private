import base64
import logging
import os
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

import jobs
from auth import verify_token
from pipelines.training_pipeline import estimate_training_job, run_training_pipeline
from storage import download_upload, upload_file

logger = logging.getLogger(__name__)
router = APIRouter()

TIPURI = ("core", "productie")
MAX_ZILE = 10


def _valideaza(tip: str, zile: int) -> None:
    if tip not in TIPURI:
        raise HTTPException(status_code=422, detail="Tipul trebuie să fie 'core' sau 'productie'")
    if not 1 <= zile <= MAX_ZILE:
        raise HTTPException(
            status_code=422,
            detail=f"Numărul de zile trebuie să fie între 1 și {MAX_ZILE}",
        )


@router.get("/training/estimate")
def estimate_training(
    tip: str = "core",
    zile: int = 3,
    cu_specificatie: bool = False,
    user=Depends(verify_token),
):
    """Cum se raportează conținutul standard la durata cerută."""
    _valideaza(tip, zile)
    return estimate_training_job(tip, zile, cu_specificatie)


async def _run_job(
    job_id: str,
    tip: str,
    zile: int,
    client: str,
    spec_path: Path | None,
    api_key: str,
) -> None:
    def _on_step(step: str) -> None:
        jobs.set_step(job_id, step)

    docx_path = xlsx_path = None
    try:
        docx_path, xlsx_path, sumar = await run_training_pipeline(
            tip=tip, zile=zile, client=client,
            spec_path=spec_path, api_key=api_key, on_step=_on_step,
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        eticheta = "CORE" if tip == "core" else "Productie"
        baza = f"Training_{eticheta}_{zile}zile_{timestamp}"
        job = jobs.get_job(job_id) or {}
        user_email = job.get("user_email", "anonymous")

        docx_name = f"{baza}.docx"
        xlsx_name = f"{baza}.xlsx"
        storage_docx = upload_file(docx_path, tool="training", filename=docx_name,
                                   user_email=user_email)
        upload_file(xlsx_path, tool="training", filename=xlsx_name, user_email=user_email)

        with open(docx_path, "rb") as f:
            docx_b64 = base64.b64encode(f.read()).decode()
        with open(xlsx_path, "rb") as f:
            xlsx_b64 = base64.b64encode(f.read()).decode()

        jobs.finish(
            job_id,
            filename=docx_name,
            docx_b64=docx_b64,
            xlsx_filename=xlsx_name,
            xlsx_b64=xlsx_b64,
            summary=sumar,
            storage_path=storage_docx,
        )
    except Exception as e:
        logger.error("training job %s FAILED: %s\n%s", job_id, e, traceback.format_exc())
        jobs.fail(job_id, str(e) or type(e).__name__)
    finally:
        for p in (spec_path, docx_path, xlsx_path):
            if p is not None:
                Path(p).unlink(missing_ok=True)


@router.post("/training/generate")
async def generate_training(
    background_tasks: BackgroundTasks,
    tip: str = Form("core"),
    zile: int = Form(3),
    client: str = Form(""),
    storage_path: str = Form(""),
    file: UploadFile | None = File(None),
    user=Depends(verify_token),
):
    """Generează agenda. Specificația e opțională la CORE, obligatorie la Producție.

    Specificația vine ca `storage_path` (încărcată direct în Supabase, ocolind
    limita de corp a proxy-ului) sau, pentru compatibilitate, ca fișier în corpul
    cererii.
    """
    _valideaza(tip, zile)

    spec_path: Path | None = None
    if storage_path:
        try:
            spec_path = download_upload(storage_path)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Specificația încărcată nu mai este disponibilă. Reîncarc-o și reia.",
            )
    elif file is not None and file.filename:
        if Path(file.filename).suffix.lower() != ".docx":
            raise HTTPException(status_code=422, detail="Specificația trebuie să fie .docx")
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp.write(await file.read())
            spec_path = Path(tmp.name)

    if tip == "productie" and spec_path is None:
        raise HTTPException(
            status_code=422,
            detail="Pentru trainingul de Producție este necesară specificația de producție (.docx).",
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if spec_path is not None and not api_key:
        spec_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY lipsă pe server — necesară pentru citirea specificației.",
        )

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email)
    background_tasks.add_task(_run_job, job_id, tip, zile, client, spec_path, api_key)
    return {"job_id": job_id}


@router.get("/training/job/{job_id}")
async def get_training_job(job_id: str, user=Depends(verify_token)):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
