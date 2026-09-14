# -*- coding: utf-8 -*-
"""Routerul HTTP pentru scop_core — capitolul standard „Charisma ERP CORE"
al unui document de scop pe verticală (Task 5).

Fluxul din UI are doi pași, în oglindă cu `pipelines/scop_core_pipeline.py`:
  1. (opțional) `/scop-core/propune` — utilizatorul încarcă un document
     suplimentar, primește înapoi elementele segmentate de model, ca să le
     corecteze în browser.
  2. `/scop-core/genereaza` — job în fundal care construiește capitolul
     standard CORE cu elementele (eventual editate) și, dacă i se cere, o
     copie a documentului gazdă cu capitolul inserat.

Nu există parametru `engine` nicăieri: `extractie.py` rulează exclusiv pe
`llm_client` (Mistral) — un singur furnizor, un singur drum (vezi
docstring-ul de sus al `extractie.py`).

Ca și în `scenarii.py`/`mockup.py`/`training.py`, routerul NU importă
`skills.scop_core` direct — trece exclusiv prin pipeline, care face deja
conversia tolerantă a elementelor brute din browser (`_elemente_din_dicturi`)
și nu trebuie duplicată aici.
"""
from __future__ import annotations

import base64
import logging
import os
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

import jobs
from auth import verify_token
from pipelines.scop_core_pipeline import (
    DocumentInvalid,
    propune_job,
    run_scop_core_pipeline,
    valideaza_docx,
)
from storage import download_upload, upload_file

logger = logging.getLogger(__name__)
router = APIRouter()

# Mesajul e ținut aici, nu doar în docstring-ul lui `insereaza_capitol`: acolo
# explică DE CE se întâmplă (cache-ul de câmp Word, w:sdt inaccesibil din
# python-docx); aici e mesajul scurt care ajunge efectiv la utilizator, în
# rezultatul jobului — vezi `insereaza.py` pentru detaliul tehnic complet.
MESAJ_CUPRINS_INVECHIT = (
    "Capitolul a fost inserat, dar Cuprinsul documentului salvat încă arată "
    "numerotarea veche a capitolelor și nu include noul capitol CORE — Word "
    "ține Cuprinsul într-un cache care nu se actualizează automat la salvare. "
    "Deschide documentul în Word și actualizează câmpul (clic-dreapta pe "
    "Cuprins → Actualizare câmp, sau Ctrl+A apoi F9) înainte să-l trimiți "
    "clientului."
)


class PropuneRequest(BaseModel):
    storage_path: str
    filename: str


class GenerateRequest(BaseModel):
    gazda_storage_path: str
    gazda_filename: str
    client: str = ""
    elemente: list[dict] = []
    insereaza: bool = False


@router.post("/scop-core/propune")
async def propune_scop_core(
    req: PropuneRequest,
    user=Depends(verify_token),
):
    """Descarcă documentul suplimentar deja încărcat în storage, îl
    segmentează prin model și întoarce elementele propuse — utilizatorul le
    corectează în browser înainte de `/scop-core/genereaza`."""
    if Path(req.filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .docx")

    if not os.environ.get("MISTRAL_API_KEY"):
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY lipsă pe server")

    try:
        supliment_path = download_upload(req.storage_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Fișierul încărcat nu a fost găsit în storage — reîncarcă fișierul.",
        )

    try:
        elemente = await propune_job(supliment_path)
    except DocumentInvalid as e:
        # Fișierul are extensia .docx dar conținutul nu e un document Word
        # valid (ex. un .xlsx redenumit) — vina e a fișierului încărcat, nu a
        # furnizorului de model. Mesajul lui `DocumentInvalid` e mereu curat
        # (fără nicio cale de fișier de pe server) — sigur de arătat direct.
        raise HTTPException(status_code=422, detail=str(e))
    except (ValueError, RuntimeError) as e:
        # Model/rețea: JSON invalid întors de model sau eroare la `llm_client`
        # (cheie respinsă, 429/5xx după reîncercări epuizate) — vina nu e a
        # fișierului încărcat, ci a furnizorului din amonte.
        raise HTTPException(
            status_code=502,
            detail=f"Nu s-a putut extrage conținutul din documentul suplimentar: {e}",
        )
    except Exception as e:
        # Orice altă excepție neprevăzută e tratată tot ca fișier invalid,
        # nu ca eroare de server.
        raise HTTPException(status_code=422, detail=f"Fișier .docx invalid: {e}")
    finally:
        supliment_path.unlink(missing_ok=True)

    return {"propunere_id": str(uuid.uuid4()), "elemente": elemente}


async def _run_job(
    job_id: str,
    gazda_path: Path,
    gazda_filename: str,
    client: str,
    elemente: list[dict],
    insereaza_in_gazda: bool,
) -> None:
    def _on_step(step: str) -> None:
        jobs.set_step(job_id, step)

    capitol_path: Path | None = None
    gazda_out_path: Path | None = None
    try:
        capitol_path, gazda_out_path, sumar = await run_scop_core_pipeline(
            gazda_path, client, elemente, insereaza_in_gazda, on_step=_on_step,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(gazda_filename).stem
        job = jobs.get_job(job_id) or {}
        user_email = job.get("user_email", "anonymous")

        capitol_filename = f"Capitol_CORE_{stem}_{timestamp}.docx"
        capitol_storage_path = upload_file(
            capitol_path, tool="scop-core", filename=capitol_filename, user_email=user_email,
        )
        with open(capitol_path, "rb") as f:
            capitol_b64 = base64.b64encode(f.read()).decode()

        gazda_filename_out: str | None = None
        gazda_b64: str | None = None
        gazda_storage_path: str | None = None
        cuprins_avertisment: str | None = None
        if gazda_out_path is not None:
            gazda_filename_out = f"Gazda_cu_CORE_{stem}_{timestamp}.docx"
            gazda_storage_path = upload_file(
                gazda_out_path, tool="scop-core", filename=gazda_filename_out, user_email=user_email,
            )
            with open(gazda_out_path, "rb") as f:
                gazda_b64 = base64.b64encode(f.read()).decode()
            cuprins_avertisment = MESAJ_CUPRINS_INVECHIT

        jobs.finish(
            job_id,
            filename=capitol_filename,
            docx_b64=capitol_b64,
            storage_path=capitol_storage_path,
            gazda_filename=gazda_filename_out,
            gazda_b64=gazda_b64,
            gazda_storage_path=gazda_storage_path,
            summary=sumar,
            cuprins_avertisment=cuprins_avertisment,
        )
    except Exception as e:
        logger.error("scop-core job %s FAILED: %s\n%s", job_id, e, traceback.format_exc())
        jobs.fail(job_id, str(e) or type(e).__name__)
    finally:
        gazda_path.unlink(missing_ok=True)
        if capitol_path is not None:
            capitol_path.unlink(missing_ok=True)
        if gazda_out_path is not None:
            gazda_out_path.unlink(missing_ok=True)


@router.post("/scop-core/genereaza")
async def genereaza_scop_core(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    user=Depends(verify_token),
):
    """Pornește jobul de fundal care construiește capitolul CORE — și,
    opțional, îl inserează într-o copie a documentului gazdă.

    Funcționează și cu `elemente: []`, fără niciun apel prealabil la
    `/scop-core/propune` — pasul de propunere e opțional în flux.
    """
    if Path(req.gazda_filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Documentul gazdă trebuie să fie .docx")

    try:
        gazda_path = download_upload(req.gazda_storage_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Documentul gazdă încărcat nu a fost găsit în storage — reîncarcă fișierul.",
        )

    # Validare sincronă a conținutului, înainte de a porni jobul de fundal —
    # un fișier cu extensia .docx dar conținut invalid (ex. un .xlsx redenumit)
    # trebuie să dea 422 imediat, nu un job care eșuează mai târziu cu un mesaj
    # tehnic (vezi `stil.DocumentInvalid` / `valideaza_docx`).
    try:
        valideaza_docx(gazda_path)
    except DocumentInvalid as e:
        gazda_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email)
    background_tasks.add_task(
        _run_job, job_id, gazda_path, req.gazda_filename, req.client, req.elemente, req.insereaza,
    )
    return {"job_id": job_id}


@router.get("/scop-core/job/{job_id}")
async def get_scop_core_job(job_id: str, user=Depends(verify_token)):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
