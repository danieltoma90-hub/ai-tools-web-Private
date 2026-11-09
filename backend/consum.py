# -*- coding: utf-8 -*-
"""Consumul Claude pe generare, pentru administrator.

Factura Anthropic arată un total; aici se vede din ce s-a adunat: ce modul, ce
coleg, cu ce efort, câți tokeni și cât a costat, estimat după prețurile din
`claude.PRETURI_USD`. Ultimele `MAX_INTRARI` generări stau în Supabase Storage
(bucketul privat `config`, lângă jurnalul de erori), ca să supraviețuiască
repornirilor serverului.

Totul e „best effort", ca la jurnalul de erori: un consum care nu se poate
nota nu are voie să strice generarea.
"""
from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import claude
from auth import get_supabase

logger = logging.getLogger(__name__)

BUCKET, CALE = "config", "consum.json"
MAX_INTRARI = 2000

_lock = threading.Lock()
_intrari: list[dict] | None = None  # copia din memorie, încărcată o singură dată


def _incarca() -> list[dict]:
    global _intrari
    if _intrari is None:
        try:
            date = get_supabase().storage.from_(BUCKET).download(CALE)
            _intrari = [i for i in json.loads(date) if isinstance(i, dict)]
        except Exception:
            _intrari = []  # fișier inexistent sau Storage indisponibil: pornim de la gol
    return _intrari


def _salveaza(intrari: list[dict]) -> None:
    get_supabase().storage.from_(BUCKET).upload(
        CALE, json.dumps(intrari, ensure_ascii=False).encode("utf-8"),
        {"upsert": "true", "content-type": "application/json"},
    )


def inregistreaza(modul: str, email: str, c: claude.Consum, reusit: bool = True) -> None:
    """Notează consumul unei generări. Generările fără niciun apel Claude nu se notează."""
    if not c.apeluri:
        return
    intrare = {
        "cand": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modul": modul or "necunoscut",
        "email": email or "anonymous",
        "efort": "+".join(sorted(c.eforturi)),
        "apeluri": c.apeluri,
        "intrare": c.intrare,
        "iesire": c.iesire,
        "cache_citit": c.cache_citit,
        "cache_scris": c.cache_scris,
        "cost_usd": round(c.cost_usd, 4),
        "reusit": reusit,
    }
    try:
        with _lock:
            intrari = [intrare] + _incarca()
            del intrari[MAX_INTRARI:]
            global _intrari
            _intrari = intrari
            _salveaza(intrari)
    except Exception as e:
        logger.warning("consum: generarea nu a putut fi notată: %s", e)


@contextmanager
def masoara(modul: str, email: str, efort: str | None = None):
    """Numără apelurile Claude din blocul `with` și le notează la ieșire, și când
    blocul eșuează: tokenii consumați până la eroare se plătesc oricum."""
    reusit = False
    with claude.numara(efort) as c:
        try:
            yield c
            reusit = True
        finally:
            inregistreaza(modul, email, c, reusit)


def _total(intrari: list[dict]) -> dict:
    return {
        "generari": len(intrari),
        "cost_usd": round(sum(i.get("cost_usd", 0) for i in intrari), 2),
        "intrare": sum(i.get("intrare", 0) for i in intrari),
        "iesire": sum(i.get("iesire", 0) for i in intrari),
        "cache_citit": sum(i.get("cache_citit", 0) for i in intrari),
    }


def _pe(cheie: str, intrari: list[dict]) -> list[dict]:
    grupe: dict[str, list[dict]] = {}
    for i in intrari:
        grupe.setdefault(str(i.get(cheie) or "—"), []).append(i)
    randuri = [{cheie: k, **_total(v)} for k, v in grupe.items()]
    for r in randuri:
        r["cost_mediu_usd"] = round(r["cost_usd"] / r["generari"], 3) if r["generari"] else 0
    return sorted(randuri, key=lambda r: r["cost_usd"], reverse=True)


def sumar(zile: int = 30, recente: int = 30) -> dict:
    """Consumul pe ultimele `zile`: total, pe modul, pe coleg și ultimele generări."""
    prag = datetime.now(timezone.utc) - timedelta(days=zile)
    with _lock:
        toate = list(_incarca())

    def in_perioada(i: dict) -> bool:
        try:
            return datetime.fromisoformat(i.get("cand", "")) >= prag
        except ValueError:
            return False

    perioada = [i for i in toate if in_perioada(i)]
    return {
        "zile": zile,
        "total": _total(perioada),
        "pe_modul": _pe("modul", perioada),
        "pe_utilizator": _pe("email", perioada),
        "recente": perioada[:recente],
    }
