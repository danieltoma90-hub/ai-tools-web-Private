# -*- coding: utf-8 -*-
"""Jurnalul generărilor eșuate, pentru administrator.

Când un coleg spune „nu merge", administratorul are aici răspunsul: cine, ce
modul, când și de ce — fără să caute în logurile Render. Ultimele `MAX_INTRARI`
eșecuri stau în Supabase Storage (bucketul privat `config`, lângă grupuri), ca
să supraviețuiască repornirilor serverului.

Totul e „best effort": un jurnal care nu se poate scrie nu are voie să strice
generarea, nici mesajul de eroare pe care îl vede utilizatorul.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone

from auth import get_supabase

logger = logging.getLogger(__name__)

BUCKET, CALE = "config", "jurnal_erori.json"
MAX_INTRARI = 200

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


def inregistreaza(modul: str, email: str, mesaj: str, tehnic: str = "") -> None:
    """Adaugă un eșec în jurnal. Nu ridică excepții."""
    intrare = {
        "cand": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modul": modul or "necunoscut",
        "email": email or "anonymous",
        "mesaj": mesaj,
        # Ce vede administratorul în plus față de utilizator: tipul și textul brut
        # al erorii, scurtat — fără căi de fișier sau chei, doar ce era în excepție.
        "tehnic": tehnic[:500],
    }
    try:
        with _lock:
            intrari = [intrare] + _incarca()
            del intrari[MAX_INTRARI:]
            global _intrari
            _intrari = intrari
            _salveaza(intrari)
    except Exception as e:
        logger.warning("jurnal: eșecul nu a putut fi salvat: %s", e)


def citeste(limita: int = 100) -> list[dict]:
    """Cele mai recente eșecuri, primul cel mai nou."""
    with _lock:
        return list(_incarca()[:limita])
