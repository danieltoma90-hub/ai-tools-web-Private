import os
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from auth import verify_token
from istorie import evenimentele_zilei

router = APIRouter()


@router.get("/istorie/zi")
async def istoria_zilei(luna: int = 0, zi: int = 0, user=Depends(verify_token)):
    """Evenimentele importante ale zilei, pentru ecranul de așteptare.

    Fără parametri întoarce ziua curentă a serverului. Rezultatul e calculat o
    singură dată pentru fiecare zi din calendar și ținut în Supabase — istoria
    nu se schimbă.
    """
    azi = date.today()
    luna = luna or azi.month
    zi = zi or azi.day
    if not (1 <= luna <= 12 and 1 <= zi <= 31):
        raise HTTPException(status_code=422, detail="Zi calendaristică invalidă")

    evenimente = await evenimentele_zilei(
        luna, zi, os.environ.get("ANTHROPIC_API_KEY", "")
    )
    return {"luna": luna, "zi": zi, "evenimente": evenimente}
