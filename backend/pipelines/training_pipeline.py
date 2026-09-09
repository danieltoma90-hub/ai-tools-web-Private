# -*- coding: utf-8 -*-
"""Pipeline pentru agenda de training.

Fara specificatie: catalog standard + distributie pe zile. Zero apeluri AI,
deci instant si gratuit.
Cu specificatie: un singur apel Claude care extrage particularitatile
clientului si le ataseaza modulelor, inainte de distributie.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from skills.training import builders
from skills.training.catalog import LABELS, get_catalog, ore_referinta
from skills.training.scheduler import ORE_PE_ZI, construieste_plan
from skills.training.spec_extract import ataseaza_la_module, extrage_particularitati

INTERVAL_IMPLICIT = "09:00 – 16:00"


def estimate_training_job(tip: str, zile: int, are_spec: bool) -> dict:
    """Ce iese inainte de a genera: cat continut standard exista si cum se
    raporteaza la zilele cerute."""
    referinta = ore_referinta(tip)
    buget = zile * ORE_PE_ZI
    return {
        "tip": tip,
        "zile": zile,
        "buget_ore": buget,
        "ore_referinta": referinta,
        "comprimat": buget < referinta,
        "cu_specificatie": are_spec,
        "est_minutes": 1 if are_spec else 0,
    }


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
    module = get_catalog(tip)

    particularitati: list[dict] = []
    if spec_path is not None and api_key:
        if on_step:
            on_step("specificatie")
        try:
            particularitati = await extrage_particularitati(
                spec_path, [m["nume"] for m in module], api_key
            )
            module = ataseaza_la_module(module, particularitati)
        except Exception:
            # Specificatia e un plus: daca extragerea esueaza, programul
            # standard ramane valid si se genereaza fara particularitati.
            particularitati = []

    if on_step:
        on_step("planificare")
    plan = construieste_plan(module, zile)

    if on_step:
        on_step("documente")
    meta = {
        "client": client or "<NUME CLIENT>",
        "titlu_program": LABELS[tip],
        "interval": interval,
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
        "excluse": [m["nume"] for m in plan["excluse"]],
        "supraincarcat": plan["supraincarcat"],
    }
    return docx_path, xlsx_path, sumar
