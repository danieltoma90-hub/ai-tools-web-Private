"""Grupurile de utilizatori: ce module poate folosi fiecare (pentru meniu) și administrarea lor.

GET /acces/eu e pentru orice utilizator autentificat; restul doar pentru administratori. Modificările
citesc configurația strict (fără rezervă), ca o eroare de Storage să nu ducă la salvarea rezervei peste
configurația reală.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import acces
from auth import verify_token

router = APIRouter()


class GrupIn(BaseModel):
    nume: str = ""
    module: list[str] = []


class MembruIn(BaseModel):
    email: str
    grup: str


class ImplicitIn(BaseModel):
    grup: str


def _public(cfg: dict) -> dict:
    return {"module": acces.MODULE, "grupuri": cfg["grupuri"], "grup_implicit": cfg["grup_implicit"]}


def _pentru_modificare() -> dict:
    try:
        return acces.incarca_config(fortat=True, strict=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Configurația grupurilor nu poate fi citită acum; încearcă din nou. ({e})")


def _salveaza(cfg: dict) -> dict:
    try:
        return acces.salveaza_config(cfg)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Configurația grupurilor nu a putut fi salvată: {e}")


def _grup(cfg: dict, gid: str) -> dict:
    g = next((g for g in cfg["grupuri"] if g["id"] == gid), None)
    if g is None:
        raise HTTPException(status_code=404, detail="Grupul nu există")
    return g


@router.get("/acces/eu")
def accesul_meu(user=Depends(verify_token)):
    """Grupul și modulele utilizatorului curent — meniul afișează doar ce poate folosi."""
    email = acces.email_din(user)
    cfg = acces.incarca_config()
    g = acces.grup_al(email, cfg)
    return {
        "email": email,
        "grup": {"id": g["id"], "nume": g["nume"]},
        "module": acces.module_permise(email, cfg),
        "admin": email in acces.admin_emails(),
    }


@router.get("/acces/config")
def configuratia(user=Depends(acces.cere_admin)):
    """Grupurile, modulele și utilizatorii (din Supabase Auth), cu grupul fiecăruia."""
    cfg = _pentru_modificare()
    try:
        users = acces.utilizatori_supabase()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Utilizatorii nu pot fi citiți din Supabase: {e}")
    admini = acces.admin_emails()
    utilizatori = []
    for u in users:
        email = acces.email_din(u)
        if not email:
            continue
        ultima = getattr(u, "last_sign_in_at", None)
        utilizatori.append({
            "email": email,
            "activ": bool(ultima),
            "ultima_conectare": str(ultima or ""),
            "grup": cfg["membri"].get(email, cfg["grup_implicit"]),
            "explicit": email in cfg["membri"],
            "admin": email in admini,
        })
    utilizatori.sort(key=lambda x: x["email"])
    return {**_public(cfg), "utilizatori": utilizatori}


@router.post("/acces/grupuri")
def creeaza_grup(body: GrupIn, user=Depends(acces.cere_admin)):
    nume = body.nume.strip()
    if not nume:
        raise HTTPException(status_code=422, detail="Grupul trebuie să aibă un nume")
    cfg = _pentru_modificare()
    ids = {g["id"] for g in cfg["grupuri"]}
    gid = baza = acces.slug(nume)
    i = 2
    while gid in ids:
        gid, i = f"{baza}-{i}", i + 1
    cfg["grupuri"].append({"id": gid, "nume": nume, "module": body.module})
    return _public(_salveaza(cfg))


@router.put("/acces/grupuri/{gid}")
def actualizeaza_grup(gid: str, body: GrupIn, user=Depends(acces.cere_admin)):
    cfg = _pentru_modificare()
    g = _grup(cfg, gid)
    if body.nume.strip():
        g["nume"] = body.nume.strip()
    g["module"] = body.module
    return _public(_salveaza(cfg))


@router.delete("/acces/grupuri/{gid}")
def sterge_grup(gid: str, user=Depends(acces.cere_admin)):
    """Membrii grupului șters trec în grupul implicit."""
    cfg = _pentru_modificare()
    _grup(cfg, gid)
    if gid == cfg["grup_implicit"]:
        raise HTTPException(status_code=422, detail="Grupul implicit nu se poate șterge; alege întâi alt grup implicit.")
    cfg["grupuri"] = [g for g in cfg["grupuri"] if g["id"] != gid]
    cfg["membri"] = {e: g for e, g in cfg["membri"].items() if g != gid}
    return _public(_salveaza(cfg))


@router.put("/acces/membri")
def seteaza_membru(body: MembruIn, user=Depends(acces.cere_admin)):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Email invalid")
    cfg = _pentru_modificare()
    _grup(cfg, body.grup)
    cfg["membri"][email] = body.grup
    _salveaza(cfg)
    return {"ok": True}


@router.put("/acces/grup-implicit")
def seteaza_implicit(body: ImplicitIn, user=Depends(acces.cere_admin)):
    """Grupul în care intră utilizatorii fără grup ales (de exemplu, cei invitați de acum încolo)."""
    cfg = _pentru_modificare()
    _grup(cfg, body.grup)
    cfg["grup_implicit"] = body.grup
    return _public(_salveaza(cfg))
