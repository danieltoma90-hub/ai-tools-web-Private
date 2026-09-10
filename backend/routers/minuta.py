import asyncio
import base64
import logging
import os
import sys
import tempfile
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile,
)

from fastapi.responses import FileResponse

import jobs
from auth import verify_token
from pipelines.minuta_pipeline import run_minuta_pipeline
from pipelines.minuta_free_pipeline import estimate_free_job, run_minuta_free_pipeline
from storage import download_document, list_files, upload_file

SKILL_DIR = Path(__file__).parent.parent / "skills" / "minuta"
CONTEXT_TEMPLATE = SKILL_DIR / "template" / "Context_Proiect_Template.docx"

router = APIRouter()
ALLOWED_EXTENSIONS = {".vtt", ".docx"}


@router.get("/minuta/context-template")
def download_context_template(user=Depends(verify_token)):
    """Template-ul de Context Proiect, gata de completat."""
    if not CONTEXT_TEMPLATE.exists():
        raise HTTPException(status_code=500, detail="Template-ul de context lipsește pe server")
    return FileResponse(
        str(CONTEXT_TEMPLATE),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Context_Proiect_Template.docx",
    )


@router.get("/minuta/contexts")
def list_contexts(user=Depends(verify_token)):
    """Contextele salvate, pentru a fi reutilizate la ședințele următoare."""
    files = list_files(tool="context")
    return [
        {
            "name": f["name"],
            "owner": f.get("owner", "—"),
            "storage_path": f.get("storage_path", ""),
            "created_at": f.get("created_at", ""),
        }
        for f in files
    ]


@router.post("/minuta/contexts")
async def upload_context(
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    """Salvează un fișier de Context Proiect pentru reutilizare."""
    filename_raw = file.filename or ""
    if Path(filename_raw).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Contextul trebuie să fie un fișier .docx")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        # Validare inainte de salvare: un formular necompletat nu e context.
        sys.path.insert(0, str(SKILL_DIR / "scripts"))
        from context_parser import parse_context

        ctx = parse_context(tmp_path)
        if ctx.is_empty():
            raise HTTPException(
                status_code=422,
                detail="Fișierul de context nu conține nimic completat. "
                       "Completați cel puțin un capitol din template și reîncărcați.",
            )
        user_email = getattr(user, "email", None) or "anonymous"
        storage_path = upload_file(
            tmp_path, tool="context", filename=Path(filename_raw).name, user_email=user_email
        )
        return {
            "storage_path": storage_path,
            "name": Path(filename_raw).name,
            "summary": {
                "participanti": len(ctx.participanti),
                "glosar": len(ctx.glosar),
                "decizii": len(ctx.decizii),
                "actiuni_deschise": len(ctx.actiuni_deschise),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Fișier de context invalid: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

async def _run_job(
    job_id: str,
    input_path: Path,
    api_key: str,
    stem: str,
    timestamp: str,
    context_storage_path: str = "",
) -> None:
    context_path: Path | None = None
    try:
        if context_storage_path:
            try:
                context_path = download_document(context_storage_path)
            except Exception as e:
                # Contextul e un plus, nu o conditie: daca nu poate fi citit,
                # minuta se genereaza fara el in loc sa esueze.
                logger.warning("context %s indisponibil: %s", context_storage_path, e)
        docx_path, preview_html = await run_minuta_pipeline(
            input_path, api_key, context_path=context_path
        )
        filename = f"Minuta_{stem}_{timestamp}.docx"
        user_email = (jobs.get_job(job_id) or {}).get("user_email", "anonymous")
        storage_path = upload_file(docx_path, tool="minuta", filename=filename, user_email=user_email)
        with open(docx_path, "rb") as f:
            docx_b64 = base64.b64encode(f.read()).decode()
        jobs.finish(
            job_id,
            filename=filename,
            docx_b64=docx_b64,
            preview_html=preview_html,
            storage_path=storage_path,
        )
        docx_path.unlink(missing_ok=True)
    except Exception as e:
        jobs.fail(job_id, str(e) or type(e).__name__)
    finally:
        input_path.unlink(missing_ok=True)
        if context_path is not None:
            context_path.unlink(missing_ok=True)


@router.post("/minuta")
async def generate_minuta(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    context_path: str = Form(""),
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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(file.filename).stem

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email)
    background_tasks.add_task(
        _run_job, job_id, input_path, api_key, stem, timestamp, context_path
    )

    return {"job_id": job_id}


@router.get("/minuta/job/{job_id}")
async def get_minuta_job(job_id: str, user=Depends(verify_token)):
    """Returnează statusul unui job de generare minută."""
    job = jobs.get_job(job_id)
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
        jobs.set_step(job_id, step)

    try:
        docx_path, preview_html = await run_minuta_free_pipeline(input_path, api_key, on_step=_on_step)
        filename = f"Minuta_{stem}_{timestamp}.docx"
        user_email = (jobs.get_job(job_id) or {}).get("user_email", "anonymous")
        storage_path = upload_file(docx_path, tool="minuta", filename=filename, user_email=user_email)
        with open(docx_path, "rb") as f:
            docx_b64 = base64.b64encode(f.read()).decode()
        jobs.finish(
            job_id,
            filename=filename,
            docx_b64=docx_b64,
            preview_html=preview_html,
            storage_path=storage_path,
        )
        docx_path.unlink(missing_ok=True)
    except Exception as e:
        jobs.fail(job_id, str(e) or type(e).__name__)
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

        # Pre-check: fisierul incape in bugetul zilnic gratuit Groq?
        est = estimate_free_job(input_path)
        if not est["fits_free_tier"]:
            input_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Fișierul este prea mare pentru versiunea Free "
                    f"(~{est['est_tokens']:,} tokens necesari, peste limita zilnică gratuită). "
                    f"Folosiți versiunea „Cu AI (Claude)” — procesează întâlniri oricât de lungi."
                ),
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(filename_raw).stem
        user_email = getattr(user, "email", None) or "anonymous"

        job_id = jobs.create_job(user_email)
        background_tasks.add_task(_run_free_job, job_id, input_path, api_key, stem, timestamp)
        return {
            "job_id": job_id,
            "est_minutes": est["est_minutes"],
            "chunks": est["chunks"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("generate_minuta_free UNEXPECTED: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Eroare neașteptată [{type(e).__name__}]: {e}")
