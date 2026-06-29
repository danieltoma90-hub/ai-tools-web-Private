import base64
import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from auth import verify_token
from pipelines.minuta_pipeline import run_minuta_pipeline
from storage import upload_file

router = APIRouter()
ALLOWED_EXTENSIONS = {".vtt", ".docx"}


@router.post("/minuta")
async def generate_minuta(
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .vtt sau .docx")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY lipsă pe server")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(await file.read())
        input_path = Path(tmp.name)

    try:
        docx_path, preview_html = await run_minuta_pipeline(input_path, api_key)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(file.filename).stem
        filename = f"Minuta_{stem}_{timestamp}.docx"

        storage_path = upload_file(docx_path, tool="minuta", filename=filename)

        with open(docx_path, "rb") as f:
            docx_b64 = base64.b64encode(f.read()).decode()

        return {
            "filename": filename,
            "docx_b64": docx_b64,
            "preview_html": preview_html,
            "storage_path": storage_path,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e) or type(e).__name__)
    finally:
        input_path.unlink(missing_ok=True)
        if "docx_path" in locals():
            docx_path.unlink(missing_ok=True)
