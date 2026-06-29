import base64
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from auth import verify_token
from pipelines.scenarii_pipeline import run_scenarii_pipeline
from storage import upload_file

router = APIRouter()


@router.post("/scenarii")
async def generate_scenarii(
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    if Path(file.filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .docx")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(await file.read())
        input_path = Path(tmp.name)

    try:
        xlsx_path = run_scenarii_pipeline(input_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Scenarii_{Path(file.filename).stem}_{timestamp}.xlsx"
        user_email = user.get("email", "anonymous")
        upload_file(xlsx_path, tool="scenarii", filename=filename, user_email=user_email)

        with open(xlsx_path, "rb") as f:
            xlsx_b64 = base64.b64encode(f.read()).decode()

        return {"filename": filename, "xlsx_b64": xlsx_b64}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        input_path.unlink(missing_ok=True)
        if "xlsx_path" in locals():
            xlsx_path.unlink(missing_ok=True)
