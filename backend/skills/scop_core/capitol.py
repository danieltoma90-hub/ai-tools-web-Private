# -*- coding: utf-8 -*-
"""Asamblarea capitolului standard CORE din secțiunile de conținut."""
from __future__ import annotations

from . import stil
from .charisma_core import SECTIUNI, Sectiune

TITLU_CAPITOL = "Soluția ofertată — Charisma ERP CORE"


def alege_sectiuni(fara=None, doar=None) -> list[Sectiune]:
    """Filtrează secțiunile, păstrând întotdeauna ordinea canonică din SECTIUNI."""
    if fara and doar:
        raise ValueError("--fara și --doar nu pot fi folosite împreună.")

    valide = [s.cheie for s in SECTIUNI]
    for cheie in list(fara or []) + list(doar or []):
        if cheie not in valide:
            raise ValueError(
                f"Cheie de secțiune necunoscută: {cheie!r}. Chei valide: {', '.join(valide)}"
            )

    if doar:
        return [s for s in SECTIUNI if s.cheie in set(doar)]
    if fara:
        return [s for s in SECTIUNI if s.cheie not in set(fara)]
    return list(SECTIUNI)


def construieste(doc, sectiuni, numar: int = 5, nivel: int = 1,
                 client: str = "[NUME CLIENT]") -> None:
    """Scrie capitolul în `doc`, deja pregătit cu stilurile gazdei."""
    stil.heading(doc, f"{numar}. {TITLU_CAPITOL}", nivel)
    stil.para(
        doc,
        f"Capitolul descrie funcționalitățile standard Charisma ERP CORE care intră în "
        f"perimetrul implementării la {client}, pe module, cu fluxurile operaționale acoperite.",
    )

    for i, s in enumerate(sectiuni, start=1):
        stil.heading(doc, f"{numar}.{i}. {s.titlu}", nivel + 1)

        stil.para(doc, "Scop", bold=True)
        stil.para(doc, s.scop)

        stil.para(doc, "Funcționalitate", bold=True)
        stil.para(doc, s.functionalitate)

        # Beneficiile lipsesc la configurare / nomenclatoare / migrare — șablonul
        # nu are pentru ele. Blocul se sare complet, nu se scrie un titlu gol.
        if s.beneficii:
            stil.para(doc, "Beneficii", bold=True)
            for b in s.beneficii:
                stil.para(doc, b.titlu, bold=True)
                stil.para(doc, b.text)

        # `detaliere` lipsește la nomenclatoare — conținutul ei stă în `grupe`.
        # Fără gardă, eticheta bold ar rămâne singură, fără nicio bulină sub ea.
        if s.detaliere:
            stil.para(doc, "Detaliere funcționalități", bold=True)
            stil.bullets(doc, s.detaliere)
        # Nomenclatoare are patru grupe cu sub-titlu propriu (Catalog articole,
        # Parteneri, Liste de prețuri, Coduri de bare). Restul secțiunilor au
        # `grupe` goală și bucla nu produce nimic.
        for g in s.grupe:
            stil.para(doc, g.titlu, bold=True)
            stil.bullets(doc, g.puncte)

        stil.para(doc, "Fluxurile de operațiuni care se vor implementa:", bold=True)
        stil.tabel_fluxuri(doc, s.fluxuri)
