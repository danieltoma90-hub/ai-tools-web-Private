import asyncio
import base64
import json
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
from acces import cere_modul, nume_utilizator
from pipelines.minuta_pipeline import run_minuta_pipeline
from storage import download_document, download_upload, list_files, upload_file

SKILL_DIR = Path(__file__).parent.parent / "skills" / "minuta"
CONTEXT_TEMPLATE = SKILL_DIR / "template" / "Context_Proiect_Template.docx"

router = APIRouter()
ALLOWED_EXTENSIONS = {".vtt", ".docx"}
# înregistrările aceleiași zile peste prima: Teams împarte o zi de ședințe în mai multe fișiere
MAX_INREGISTRARI_SUPLIMENTARE = 4
# notițele echipei din ședință: câteva pagini de text, nu un al doilea transcript
MAX_NOTITE = 30_000

sys.path.insert(0, str(SKILL_DIR / "scripts"))
from limba import LANGS  # noqa: E402
from reguli import DETALII, STRUCTURI  # noqa: E402


def _optiuni(marcaje: str, limba: str, structura: str = "standard", detaliu: str = "standard") -> dict:
    """Opțiunile din pagină, validate. Implicit: marcaje pentru revizie, română, structura standard."""
    limba, structura, detaliu = (limba or "ro").lower(), (structura or "standard").lower(), (detaliu or "standard").lower()
    if limba not in LANGS:
        raise HTTPException(status_code=422, detail=f"Limba minutei trebuie să fie una din {LANGS}")
    if structura not in STRUCTURI:
        raise HTTPException(status_code=422, detail=f"Structura trebuie să fie una din {STRUCTURI}")
    if detaliu not in DETALII:
        raise HTTPException(status_code=422, detail=f"Detaliul trebuie să fie unul din {DETALII}")
    return {"marcaje": (marcaje or "").strip().lower() not in ("", "0", "false", "nu", "off"),
            "limba": limba, "structura": structura, "detaliu": detaliu}


def _nume_fisier(stem: str, timestamp: str, optiuni: dict | None) -> str:
    optiuni = optiuni or {}
    prefix = "Minutes" if optiuni.get("limba") == "en" else "Minuta"
    sufix = "_FitGap" if optiuni.get("structura") == "fitgap" else ""
    return f"{prefix}_{stem}{sufix}_{timestamp}.docx"


@router.get("/minuta/context-template")
def download_context_template(user=Depends(cere_modul("minuta"))):
    """Template-ul de Context Proiect, gata de completat."""
    if not CONTEXT_TEMPLATE.exists():
        raise HTTPException(status_code=500, detail="Template-ul de context lipsește pe server")
    return FileResponse(
        str(CONTEXT_TEMPLATE),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Context_Proiect_Template.docx",
    )


@router.get("/minuta/contexts")
def list_contexts(user=Depends(cere_modul("minuta"))):
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
    user=Depends(cere_modul("minuta")),
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
    optiuni: dict | None = None,
    autor: str = "TotalSoft",
    alte_inregistrari: list[tuple[Path, str]] | None = None,
    notite: str = "",
) -> None:
    """Rulează minuta în fundal. `alte_inregistrari` — fișierele aceleiași zile de după
    `input_path`, ca (cale locală, nume original); `notite` — notițele echipei din ședință."""
    context_path: Path | None = None
    alte_inregistrari = alte_inregistrari or []
    try:
        if context_storage_path:
            try:
                context_path = download_document(context_storage_path)
            except Exception as e:
                # Contextul e un plus, nu o conditie: daca nu poate fi citit,
                # minuta se genereaza fara el in loc sa esueze.
                logger.warning("context %s indisponibil: %s", context_storage_path, e)
        inregistrari = [(input_path, stem)] + alte_inregistrari if alte_inregistrari else None
        docx_path, preview_html = await run_minuta_pipeline(
            input_path, api_key, context_path=context_path,
            on_step=lambda step: jobs.set_step(job_id, step),
            autor=autor,
            inregistrari=inregistrari,
            notite=notite,
            **(optiuni or {}),
        )
        filename = _nume_fisier(stem, timestamp, optiuni)
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
        for cale, _ in alte_inregistrari:
            cale.unlink(missing_ok=True)
        if context_path is not None:
            context_path.unlink(missing_ok=True)


async def _preia_fisierul(
    storage_path: str, filename: str, file: UploadFile | None
) -> tuple[Path, str]:
    """Fișierul de procesat, ca (cale locală, nume original).

    Traseul normal: fișierul e urcat de browser direct în Supabase și aici vine
    doar `storage_path` — corpul cererii rămâne mic, sub limita de 4,5MB a
    funcțiilor Vercel prin care trece proxy-ul. Varianta cu fișier în corp e
    păstrată pentru compatibilitate.
    """
    if storage_path:
        nume = filename or Path(storage_path).name
        if Path(nume).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .vtt sau .docx")
        try:
            return download_upload(storage_path), nume
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Fișierul încărcat nu mai este disponibil. Reîncarcă-l și reia.",
            )

    if file is None or not file.filename:
        raise HTTPException(status_code=422, detail="Lipsește fișierul de procesat")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Fișierul trebuie să fie .vtt sau .docx (primit: '{file.filename}')",
        )
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(await file.read())
        return Path(tmp.name), file.filename


async def _preia_inregistrarile(brut: str) -> list[tuple[Path, str]]:
    """Înregistrările aceleiași zile de după prima, din JSON-ul
    `[{"storage_path": ..., "filename": ...}]` trimis de pagină. Fiecare e urcată de browser
    direct în storage, ca prima; aici se descarcă, cu aceleași verificări de extensie."""
    if not (brut or "").strip():
        return []
    try:
        lista = json.loads(brut)
    except ValueError:
        raise HTTPException(status_code=422, detail="Lista înregistrărilor suplimentare nu e validă")
    if not isinstance(lista, list) or not all(isinstance(x, dict) for x in lista):
        raise HTTPException(status_code=422, detail="Lista înregistrărilor suplimentare nu e validă")
    if len(lista) > MAX_INREGISTRARI_SUPLIMENTARE:
        raise HTTPException(
            status_code=422,
            detail=f"O minută reunește cel mult {MAX_INREGISTRARI_SUPLIMENTARE + 1} înregistrări",
        )
    preluate: list[tuple[Path, str]] = []
    try:
        for x in lista:
            storage_path = x.get("storage_path")
            if not isinstance(storage_path, str) or not storage_path.strip():
                raise HTTPException(status_code=422,
                                    detail="O înregistrare suplimentară nu are fișierul încărcat")
            nume = x.get("filename") if isinstance(x.get("filename"), str) else ""
            preluate.append(await _preia_fisierul(storage_path, nume, None))
    except HTTPException:
        for cale, _ in preluate:
            cale.unlink(missing_ok=True)
        raise
    return [(cale, Path(nume).stem) for cale, nume in preluate]


@router.post("/minuta")
async def generate_minuta(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    storage_path: str = Form(""),
    filename: str = Form(""),
    context_path: str = Form(""),
    marcaje: str = Form("1"),
    limba: str = Form("ro"),
    structura: str = Form("standard"),
    detaliu: str = Form("standard"),
    notite: str = Form(""),
    inregistrari: str = Form(""),
    user=Depends(cere_modul("minuta")),
):
    """Pornește procesarea minutei în fundal și returnează un job_id imediat.

    `notite` — notițele echipei din ședință, opționale; `inregistrari` — JSON cu celelalte
    înregistrări ale aceleiași zile (`storage_path`, `filename`), reunite în aceeași minută."""
    optiuni = _optiuni(marcaje, limba, structura, detaliu)
    notite = (notite or "").strip()
    if len(notite) > MAX_NOTITE:
        raise HTTPException(
            status_code=422,
            detail=f"Notițele au {len(notite)} de caractere — cel mult {MAX_NOTITE} pe minută",
        )
    input_path, nume = await _preia_fisierul(storage_path, filename, file)
    try:
        alte_inregistrari = await _preia_inregistrarile(inregistrari)
    except HTTPException:
        input_path.unlink(missing_ok=True)
        raise

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        input_path.unlink(missing_ok=True)
        for cale, _ in alte_inregistrari:
            cale.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY lipsă pe server")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(nume).stem

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email)
    background_tasks.add_task(
        _run_job, job_id, input_path, api_key, stem, timestamp, context_path, optiuni,
        nume_utilizator(user), alte_inregistrari=alte_inregistrari, notite=notite,
    )

    return {"job_id": job_id}


@router.get("/minuta/job/{job_id}")
async def get_minuta_job(job_id: str, user=Depends(cere_modul("minuta"))):
    """Returnează statusul unui job de generare minută."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
