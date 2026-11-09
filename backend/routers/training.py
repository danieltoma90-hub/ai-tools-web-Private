import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

import jobs
from auth import verify_token  # noqa: F401
from acces import cere_modul
from pipelines.training_pipeline import estimate_training_job, run_training_pipeline
from storage import download_upload

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
    user=Depends(cere_modul("training")),
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
    async def lucrare() -> dict:
        docx_path, xlsx_path, sumar = await run_training_pipeline(
            tip=tip, zile=zile, client=client, spec_path=spec_path, api_key=api_key,
            on_step=lambda step: jobs.set_step(job_id, step),
        )
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            eticheta = "CORE" if tip == "core" else "Productie"
            baza = f"Training_{eticheta}_{zile}zile_{timestamp}"
            storage_docx, docx_b64 = jobs.livreaza(job_id, docx_path, tool="training",
                                                   filename=f"{baza}.docx")
            _, xlsx_b64 = jobs.livreaza(job_id, xlsx_path, tool="training", filename=f"{baza}.xlsx")
        finally:
            docx_path.unlink(missing_ok=True)
            xlsx_path.unlink(missing_ok=True)
        return {
            "filename": f"{baza}.docx",
            "docx_b64": docx_b64,
            "xlsx_filename": f"{baza}.xlsx",
            "xlsx_b64": xlsx_b64,
            "summary": sumar,
            "storage_path": storage_docx,
        }

    try:
        await jobs.ruleaza(job_id, lucrare)
    finally:
        if spec_path is not None:
            spec_path.unlink(missing_ok=True)


@router.post("/training/generate")
async def generate_training(
    background_tasks: BackgroundTasks,
    tip: str = Form("core"),
    zile: int = Form(3),
    client: str = Form(""),
    storage_path: str = Form(""),
    file: UploadFile | None = File(None),
    user=Depends(cere_modul("training")),
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
    job_id = jobs.create_job(user_email, "training")
    background_tasks.add_task(_run_job, job_id, tip, zile, client, spec_path, api_key)
    return {"job_id": job_id}


@router.get("/training/job/{job_id}")
async def get_training_job(job_id: str, user=Depends(cere_modul("training"))):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
