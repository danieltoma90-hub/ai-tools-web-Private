import base64
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from auth import verify_token
from pipelines.mockup_pipeline import run_mockup_pipeline
from storage import upload_file

router = APIRouter()


@router.post("/mockup")
async def generate_mockup(
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    if Path(file.filename).suffix.lower() != ".xlsx":
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .xlsx")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(await file.read())
        input_path = Path(tmp.name)

    try:
        docx_path, html, html_compact = run_mockup_pipeline(input_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{Path(file.filename).stem}_{timestamp}.docx"
        upload_file(docx_path, tool="mockup", filename=filename)

        with open(docx_path, "rb") as f:
            docx_b64 = base64.b64encode(f.read()).decode()

        return {
            "filename": filename,
            "docx_b64": docx_b64,
            "html": html,
            "html_compact": html_compact,
        }
    finally:
        input_path.unlink(missing_ok=True)
        if "docx_path" in locals():
            docx_path.unlink(missing_ok=True)
