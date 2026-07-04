import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import verify_token
from storage import create_upload_url

logger = logging.getLogger(__name__)
router = APIRouter()


class SignRequest(BaseModel):
    filename: str
    tool: str


@router.post("/uploads/sign")
async def sign_upload(req: SignRequest, user=Depends(verify_token)):
    """Emite un URL semnat pentru upload direct browser → Supabase Storage.

    Ocolește limita de 4,5MB a proxy-ului Vercel: fișierul nu mai trece prin el.
    """
    try:
        return create_upload_url(req.tool, req.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("uploads/sign FAILED: %s", e)
        raise HTTPException(status_code=502, detail=f"Nu s-a putut pregăti încărcarea: {e}")
