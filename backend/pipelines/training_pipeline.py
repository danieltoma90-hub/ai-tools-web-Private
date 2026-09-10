# -*- coding: utf-8 -*-
"""Pipeline pentru agenda de training.

Cele doua tipuri pleaca din locuri diferite, fiindca asa arata realitatea:

CORE — exista un program standard Charisma, acelasi la orice client. Fara
specificatie se genereaza standardul comprimat pe zilele cerute, fara niciun
apel AI. Cu specificatie, peste standard se adauga particularitatile clientului.

PRODUCTIE — nu exista un standard. Fiecare implementare are alte entitati
tehnologice, alte retete, alt mod de raportare, asa ca intreaga agenda se
ridica din documentul clientului. Ce nu scrie acolo nu intra in training.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ai_errors import mesaj_eroare_ai
from skills.training import builders
from skills.training.catalog import LABELS, get_catalog, ore_referinta
from skills.training.scheduler import ORE_PE_ZI, construieste_plan
from skills.training.spec_build import construieste_module_din_spec
from skills.training.spec_extract import ataseaza_la_module, extrage_particularitati

INTERVAL_IMPLICIT = "09:00 – 16:00"


def estimate_training_job(tip: str, zile: int, are_spec: bool) -> dict:
    """Ce se stie inainte de generare.

    La Productie nu exista continut de referinta: cat training iese se afla abia
    dupa citirea specificatiei, deci `ore_referinta` ramane necunoscut.
    """
    referinta = ore_referinta(tip) if tip == "core" else None
    buget = zile * ORE_PE_ZI
    return {
        "tip": tip,
        "zile": zile,
        "buget_ore": buget,
        "ore_referinta": referinta,
        "comprimat": referinta is not None and buget < referinta,
        "specificatie_obligatorie": tip == "productie",
        "cu_specificatie": are_spec,
        "est_minutes": 1 if are_spec or tip == "productie" else 0,
    }


async def _module_core(
    spec_path: Path | None, api_key: str, on_step
) -> tuple[list[dict], list[dict], str]:
    """Standardul CORE, imbogatit cu particularitatile clientului daca exista."""
    module = get_catalog("core")
    if spec_path is None or not api_key:
        return module, [], ""

    if on_step:
        on_step("specificatie")
    try:
        particularitati = await extrage_particularitati(
            spec_path, [m["nume"] for m in module], api_key
        )
        return ataseaza_la_module(module, particularitati), particularitati, ""
    except Exception as e:
        # Standardul ramane valid si fara particularitati, dar utilizatorul
        # trebuie sa afle ca lipsesc si de ce.
        return module, [], (
            f"Particularitățile clientului nu au putut fi extrase — {mesaj_eroare_ai(e)}"
        )


async def _module_productie(spec_path: Path | None, api_key: str, on_step) -> list[dict]:
    """Programul ridicat integral din specificatia clientului."""
    if spec_path is None:
        raise RuntimeError(
            "Trainingul de Producție se construiește din specificația clientului. "
            "Fără document nu există conținut de predat."
        )
    if not api_key:
        raise RuntimeError(
            "Citirea specificației cere cheia API Claude, care lipsește pe server."
        )

    if on_step:
        on_step("specificatie")
    try:
        return await construieste_module_din_spec(spec_path, api_key)
    except ValueError:
        raise  # mesajul e deja scris pentru utilizator
    except Exception as e:
        raise RuntimeError(f"Nu am putut citi specificația: {mesaj_eroare_ai(e)}") from e


async def run_training_pipeline(
    tip: str,
    zile: int,
    client: str,
    spec_path: Path | None = None,
    api_key: str = "",
    interval: str = INTERVAL_IMPLICIT,
    on_step=None,
) -> tuple[Path, Path, dict]:
    """Returneaza (docx_path, xlsx_path, sumar)."""
    if on_step:
        on_step("catalog")

    particularitati: list[dict] = []
    avertisment = ""
    if tip == "productie":
        module = await _module_productie(spec_path, api_key, on_step)
    else:
        module, particularitati, avertisment = await _module_core(
            spec_path, api_key, on_step
        )

    referinta = round(sum(m["ore"] for m in module), 2)

    if on_step:
        on_step("planificare")
    plan = construieste_plan(module, zile)

    if on_step:
        on_step("documente")
    meta = {
        "client": client or "<NUME CLIENT>",
        "titlu_program": LABELS[tip],
        "interval": interval,
        "sursa": (
            "Program construit integral din specificația clientului"
            if tip == "productie"
            else ""
        ),
    }
    fd, docx_name = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    fd, xlsx_name = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)

    docx_path = builders.build_word(plan, meta, Path(docx_name))
    xlsx_path = builders.build_excel(plan, meta, Path(xlsx_name))

    sumar = {
        "tip": tip,
        "zile": len(plan["zile"]),
        "total_ore": plan["total_ore"],
        # Un modul spart pe doua zile ramane un singur modul in sumar.
        "module": len({m["nr"] for z in plan["zile"] for m in z["module"]}),
        "particularitati": len(particularitati),
        "ore_referinta": referinta,
        "excluse": [m["nume"] for m in plan["excluse"]],
        "supraincarcat": plan["supraincarcat"],
        "avertisment": avertisment,
    }
    return docx_path, xlsx_path, sumar
