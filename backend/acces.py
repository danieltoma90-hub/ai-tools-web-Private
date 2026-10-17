# -*- coding: utf-8 -*-
"""Grupuri de utilizatori și accesul la module (skill-uri).

Fiecare utilizator face parte dintr-un singur grup; grupul spune la ce module are acces („*” = toate,
inclusiv cele adăugate ulterior). Configurația stă în Supabase Storage (bucket privat „config”,
fișierul „grupuri.json”) — fără tabele noi în baza de date — și se modifică din pagina Grupuri,
doar de administratori.

La prima pornire (fișierul lipsește) se creează două grupuri: „Echipa ERP” (toate modulele), cu toți
utilizatorii activi la acel moment, și „TotalSoft” (doar Minută), grupul implicit pentru utilizatorii
noi. Configurația se reconstruiește DOAR când fișierul lipsește cu adevărat (404) — o eroare
temporară de Storage nu are voie să suprascrie ce a setat administratorul.

Administratorii (variabila ADMIN_EMAILS, implicit daniel.toma@totalsoft.ro) au acces la tot și
administrează grupurile.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
from typing import Any

from fastapi import Depends, HTTPException

from auth import get_supabase, verify_token

# Modulele site-ului: cheia = folderul din Storage și ruta API; valoarea = eticheta din pagină.
MODULE: dict[str, str] = {
    "minuta": "Minută",
    "mockup": "Mockup",
    "scenarii": "Scenarii",
    "scop-core": "Scop CORE",
    "training": "Training",
}
# folderul din Storage → modulul de care ține (contextele de proiect țin de Minută)
TOOL_MODUL: dict[str, str] = {**{m: m for m in MODULE}, "context": "minuta"}

ERP, TOTALSOFT = "echipa-erp", "totalsoft"
CONFIG_BUCKET, CONFIG_PATH = "config", "grupuri.json"
CACHE_TTL_S = 30


def config_implicita(membri: dict[str, str] | None = None) -> dict:
    return {
        "versiune": 1,
        "grupuri": [
            {"id": ERP, "nume": "Echipa ERP", "module": ["*"]},
            {"id": TOTALSOFT, "nume": "TotalSoft", "module": ["minuta"]},
        ],
        "grup_implicit": TOTALSOFT,
        "membri": dict(membri or {}),
    }


def admin_emails() -> set[str]:
    raw = os.environ.get("ADMIN_EMAILS", "daniel.toma@totalsoft.ro")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def email_din(user: Any) -> str:
    """Email-ul utilizatorului autentificat (obiect Supabase User sau dict în teste)."""
    email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
    return (email or "").strip().lower()


def nume_utilizator(user: Any) -> str:
    """Numele afișat al utilizatorului autentificat (de exemplu autorul documentelor generate):
    numele din profil, dacă există, altfel din email („daniel.toma@totalsoft.ro” → „Daniel Toma”),
    iar fără niciunul „TotalSoft”."""
    profil = user.get("user_metadata") if isinstance(user, dict) else getattr(user, "user_metadata", None)
    if isinstance(profil, dict):
        for cheie in ("full_name", "name", "nume"):
            nume = " ".join(str(profil.get(cheie) or "").split())
            if nume:
                return nume
    parti = [p for p in re.split(r"[._+-]+", email_din(user).split("@")[0]) if p]
    return " ".join(p[:1].upper() + p[1:] for p in parti) or "TotalSoft"


# ── citire / scriere ─────────────────────────────────────────────────────────

_lock = threading.Lock()
_cache: dict[str, Any] = {"config": None, "pana": 0.0}
_bucket_gata = False


def _e_lipsa(e: Exception) -> bool:
    """True doar pentru „obiectul nu există” — nu pentru erori de rețea sau de autorizare."""
    status = str(getattr(e, "status", "") or "")
    text = f"{getattr(e, 'code', '')} {e}".lower()
    return status == "404" or "not_found" in text or "object not found" in text or "not found" in text


def _asigura_bucket() -> None:
    global _bucket_gata
    if _bucket_gata:
        return
    sb = get_supabase()
    existente = {getattr(b, "name", None) or getattr(b, "id", "") for b in sb.storage.list_buckets()}
    if CONFIG_BUCKET not in existente:
        sb.storage.create_bucket(CONFIG_BUCKET, options={"public": False})
    _bucket_gata = True


def _citeste() -> dict | None:
    """Configurația salvată; None dacă fișierul nu există. Alte erori se propagă."""
    _asigura_bucket()
    try:
        data = get_supabase().storage.from_(CONFIG_BUCKET).download(CONFIG_PATH)
    except Exception as e:
        if _e_lipsa(e):
            return None
        raise
    return valideaza(json.loads(data))


def _scrie(cfg: dict) -> None:
    _asigura_bucket()
    get_supabase().storage.from_(CONFIG_BUCKET).upload(
        CONFIG_PATH, json.dumps(cfg, ensure_ascii=False, indent=1).encode("utf-8"),
        {"upsert": "true", "content-type": "application/json"},
    )


def utilizatori_supabase() -> list[Any]:
    """Toți utilizatorii din Supabase Auth (paginat)."""
    sb, pagina, toti = get_supabase(), 1, []
    while True:
        lot = sb.auth.admin.list_users(page=pagina, per_page=1000)
        toti += lot
        if len(lot) < 1000:
            return toti
        pagina += 1


def _initializeaza() -> dict:
    """Prima configurație: utilizatorii activi (conectați cel puțin o dată) în Echipa ERP."""
    activi = {
        email_din(u): ERP for u in utilizatori_supabase()
        if email_din(u) and getattr(u, "last_sign_in_at", None)
    }
    cfg = config_implicita(activi)
    _scrie(cfg)
    return cfg


def incarca_config(fortat: bool = False, strict: bool = False) -> dict:
    """Configurația curentă, din cache (30 s). Dacă Storage nu răspunde, rămâne ultima variantă
    cunoscută; dacă nu există niciuna, varianta implicită (fiecare în grupul implicit, admini la tot).

    `strict=True` (înainte de o modificare): fără variantă de rezervă — o eroare de Storage se propagă,
    altfel rezerva ar fi salvată peste configurația reală."""
    acum = time.monotonic()
    with _lock:
        if not fortat and _cache["config"] is not None and _cache["pana"] > acum:
            return _cache["config"]
        try:
            cfg = _citeste()
            if cfg is None:
                cfg = _initializeaza()
        except Exception:
            if strict:
                raise
            cfg = _cache["config"] or config_implicita()
            _cache.update(config=cfg, pana=acum + 5)  # reîncercăm curând
            return cfg
        _cache.update(config=cfg, pana=acum + CACHE_TTL_S)
        return cfg


def salveaza_config(cfg: dict) -> dict:
    cfg = valideaza(cfg)
    with _lock:
        _scrie(cfg)
        _cache.update(config=cfg, pana=time.monotonic() + CACHE_TTL_S)
    return cfg


# ── reguli ───────────────────────────────────────────────────────────────────

def valideaza(cfg: dict) -> dict:
    if not isinstance(cfg, dict) or not isinstance(cfg.get("grupuri"), list) or not cfg["grupuri"]:
        raise ValueError("Configurația grupurilor nu are niciun grup")
    ids = [g.get("id") for g in cfg["grupuri"]]
    if len(set(ids)) != len(ids) or not all(ids):
        raise ValueError("Grupurile trebuie să aibă identificatori unici")
    for g in cfg["grupuri"]:
        g["module"] = sorted({m for m in g.get("module", []) if m == "*" or m in MODULE})
        g["nume"] = str(g.get("nume") or g["id"]).strip()
    if cfg.get("grup_implicit") not in ids:
        cfg["grup_implicit"] = ids[0]
    cfg["membri"] = {
        str(e).strip().lower(): gid for e, gid in (cfg.get("membri") or {}).items() if gid in ids
    }
    cfg.setdefault("versiune", 1)
    return cfg


def grup_al(email: str, cfg: dict | None = None) -> dict:
    cfg = cfg or incarca_config()
    gid = cfg["membri"].get(email.lower(), cfg["grup_implicit"])
    return next(g for g in cfg["grupuri"] if g["id"] == gid)


def module_permise(email: str, cfg: dict | None = None) -> list[str]:
    if email.lower() in admin_emails():
        return list(MODULE)
    module = grup_al(email, cfg)["module"]
    return list(MODULE) if "*" in module else [m for m in MODULE if m in module]


def are_acces(email: str, modul: str, cfg: dict | None = None) -> bool:
    return bool(email) and modul in module_permise(email, cfg)


def acces_la_tool(email: str, tool: str, cfg: dict | None = None) -> bool:
    """Accesul la documentele unui folder din Storage (ex. „context” ține de Minută)."""
    modul = TOOL_MODUL.get(tool)
    return modul is not None and are_acces(email, modul, cfg)


def slug(nume: str) -> str:
    s = unicodedata.normalize("NFKD", nume).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "grup"


# ── dependențe FastAPI ───────────────────────────────────────────────────────

def cere_modul(modul: str):
    """Dependență: utilizatorul autentificat trebuie să aibă acces la modul (altfel 403)."""
    if modul not in MODULE:
        raise ValueError(f"Modul necunoscut: {modul}")

    async def _dep(user=Depends(verify_token)):
        if not are_acces(email_din(user), modul):
            raise HTTPException(
                status_code=403,
                detail=f"Nu ai acces la modulul „{MODULE[modul]}”. Cere acces administratorului.",
            )
        return user

    return _dep


async def cere_admin(user=Depends(verify_token)):
    if email_din(user) not in admin_emails():
        raise HTTPException(status_code=403, detail="Doar administratorii pot gestiona grupurile.")
    return user
