# -*- coding: utf-8 -*-
"""Pipeline scop_core — orchestrarea skill-ului `skills/scop_core` pentru web.

Fluxul din UI are doi pași separați:
  1. Utilizatorul încarcă un document suplimentar (opțional) -> `propune_job`
     îl trimite la model (prin `extractie.propune_elemente`) și întoarce
     elementele propuse, ca să le corecteze în browser.
  2. Utilizatorul confirmă (eventual editate) elementele și cere generarea ->
     `run_scop_core_pipeline` construiește capitolul standard CORE, cu
     elementele suplimentare deja plasate, și — dacă i se cere — și o copie
     a documentului gazdă cu capitolul inserat la locul lui.

Elementele care ajung la `run_scop_core_pipeline` sunt dicturi simple
(`{"titlu", "text", "plasare", "fluxuri_legate"}`) care au trecut printr-un
formular din browser și prin editările utilizatorului — nu se poate avea
încredere oarbă în formă. Conversia lor în `capitol.Element` se face AICI,
nu în router (routerul nu importă skill-ul direct), cu aceeași filosofie de
validare „nu ridica, corectează sau aruncă” pe care `extractie._valideaza_elemente`
o aplică deja părții AI a fluxului — vezi `_element_din_dict`.

`insereaza.insereaza_capitol` primește acum aceleași `elemente` cu care se
construiește și capitolul separat — cele două fișiere întoarse de acest
pipeline (capitolul standalone și, dacă e cerută, gazda cu capitolul inserat)
conțin identic aceleași elemente suplimentare, plasate la fel.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from skills.scop_core import capitol, extractie, insereaza, stil
from skills.scop_core.charisma_core import SECTIUNI

# cele zece chei de secțiune CORE, plus "propriu" — singurele valori valide
# pentru `plasare`, aceeași listă pe care se bazează și `extractie.py`.
_PLASARI_VALIDE: set[str] = {s.cheie for s in SECTIUNI} | {"propriu"}

CLIENT_IMPLICIT = "[NUME CLIENT]"


def _mktemp_path(suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return Path(name)


async def propune_job(supliment_path: Path) -> list[dict]:
    """Subțire wrapper peste `extractie.propune_elemente`.

    Există doar ca routerul să nu importe `skills.scop_core` direct — la fel
    cum fac celelalte perechi router/pipeline din acest repo (vezi
    `mockup_pipeline`/`scenarii_pipeline`). Nu adaugă nicio logică proprie:
    validarea elementelor propuse de model trăiește deja în `extractie.py`,
    iar erorile ei (JSON invalid, cheie API lipsă) urcă neschimbate.
    """
    return await extractie.propune_elemente(supliment_path)


def _element_din_dict(brut: object) -> capitol.Element | None:
    """Convertește un singur dict brut (din browser) într-un `capitol.Element`.

    Regulile — în oglindă cu `extractie._valideaza_elemente`, ca un element
    editat de utilizator și unul propus direct de model să fie tratate la
    fel de tolerant:
      - orice altceva decât un `dict` (None, șir, listă imbricată etc.) e
        respins — nu are cum să fie un element valid;
      - `titlu`/`text` lipsă, goale după strip sau de alt tip decât `str`
        fac elementul inutilizabil (nu poți randa un titlu de capitol gol,
        nici un sub-capitol fără conținut) — respins, nu „reparat” cu text
        de rezervă inventat aici;
      - `plasare` care nu e exact una din cele zece chei de secțiune CORE
        sau `"propriu"` devine tăcut `"propriu"` — elementul nu se pierde,
        doar capătă secțiune proprie la coada capitolului, exact cum
        `capitol.construieste` tratează deja o secțiune filtrată afară
        (vezi docstring-ul funcției respective);
      - `fluxuri_legate` care nu e o listă (sau lipsește) devine `[]`; intrările
        care nu sunt șiruri se aruncă, iar spațiile parazite se curăță cu
        `.strip()` — codurile invalide propriu-zise (inexistente în
        `SECTIUNI`) NU se filtrează aici, ci mai departe, în
        `capitol._denumiri_fluxuri_legate`, care e sursa unică a acestei
        reguli — nu se duplică logica ei aici.
    """
    if not isinstance(brut, dict):
        return None

    titlu_brut = brut.get("titlu")
    titlu = titlu_brut.strip() if isinstance(titlu_brut, str) else ""
    text_brut = brut.get("text")
    text = text_brut.strip() if isinstance(text_brut, str) else ""
    if not titlu or not text:
        return None

    plasare = brut.get("plasare")
    if not isinstance(plasare, str) or plasare not in _PLASARI_VALIDE:
        plasare = "propriu"

    fluxuri_brut = brut.get("fluxuri_legate")
    fluxuri_legate = [
        cod.strip() for cod in fluxuri_brut if isinstance(cod, str) and cod.strip()
    ] if isinstance(fluxuri_brut, list) else []

    return capitol.Element(titlu=titlu, text=text, plasare=plasare, fluxuri_legate=fluxuri_legate)


def _elemente_din_dicturi(brute: object) -> tuple[list[capitol.Element], int]:
    """Convertește lista de dicturi brute; întoarce (elemente valide, nr. respinse).

    O `elemente` care nu e deloc listă (None, obiect greșit trimis) e tratată
    ca listă goală — fără nicio excepție ridicată către router.
    """
    if not isinstance(brute, list):
        return [], 0

    valide: list[capitol.Element] = []
    respinse = 0
    for brut in brute:
        element = _element_din_dict(brut)
        if element is None:
            respinse += 1
        else:
            valide.append(element)
    return valide, respinse


async def run_scop_core_pipeline(
    gazda_path: Path,
    client: str,
    elemente: list[dict],
    insereaza_in_gazda: bool,
    on_step=None,
) -> tuple[Path, Path | None, dict]:
    """Construiește capitolul CORE și, opțional, copia gazdă+capitol.

    Întoarce `(capitol_path, gazda_cu_capitol_path, sumar)`. A doua cale e
    `None` dacă `insereaza_in_gazda` e `False`, SAU dacă a fost cerută dar
    pasul de inserare a eșuat — vezi mai jos: acel eșec nu duce la pierderea
    capitolului deja construit cu succes, ci doar la un `avertisment` în sumar
    (aceeași filosofie ca în `training_pipeline._module_core`: un pas
    secundar care pică nu trebuie să tragă după el livrabilul principal).

    Documentul gazdă NU e niciodată scris pe disc: atât `capitol.construieste`
    cât și `insereaza.insereaza_capitol` lucrează pe un `Document` încărcat în
    memorie (`stil.document_din_gazda`/`Document(gazda_path)` intern) — abia
    rezultatul se salvează, sub o cale nouă, temporară.
    """
    if on_step:
        on_step("parsing")

    sectiuni = capitol.alege_sectiuni()
    client_nume = client or CLIENT_IMPLICIT
    elemente_valide, elemente_respinse = _elemente_din_dicturi(elemente)

    chei_sectiuni = {s.cheie for s in sectiuni}
    elemente_pe_sectiune = sum(1 for el in elemente_valide if el.plasare in chei_sectiuni)
    elemente_proprii = len(elemente_valide) - elemente_pe_sectiune

    if on_step:
        on_step("building")

    capitol_path = _mktemp_path(".docx")
    try:
        doc = stil.document_din_gazda(gazda_path)
        capitol.construieste(doc, sectiuni, client=client_nume, elemente=elemente_valide)
        doc.save(str(capitol_path))
    except Exception:
        capitol_path.unlink(missing_ok=True)
        raise

    gazda_path_out: Path | None = None
    avertismente: list[str] = []
    if elemente_respinse:
        avertismente.append(
            f"{elemente_respinse} element(e) suplimentar(e) primite din browser nu au putut fi "
            "folosite (titlu sau text lipsă) și au fost ignorate."
        )

    if insereaza_in_gazda:
        if on_step:
            on_step("inserare")
        candidat = _mktemp_path(".docx")
        try:
            gazda_cu_capitol = insereaza.insereaza_capitol(
                gazda_path, sectiuni, client=client_nume, elemente=elemente_valide,
            )
            gazda_cu_capitol.save(str(candidat))
            gazda_path_out = candidat
        except Exception as e:
            candidat.unlink(missing_ok=True)
            avertismente.append(f"Inserarea capitolului în documentul gazdă a eșuat: {e}")

    sumar = {
        "sectiuni": len(sectiuni),
        "fluxuri": sum(len(s.fluxuri) for s in sectiuni),
        "elemente_primite": len(elemente) if isinstance(elemente, list) else 0,
        "elemente_plasate": len(elemente_valide),
        "elemente_pe_sectiune": elemente_pe_sectiune,
        "elemente_proprii": elemente_proprii,
        "elemente_respinse": elemente_respinse,
        "gazda_inserata": gazda_path_out is not None,
        "avertisment": " ".join(avertismente),
    }
    return capitol_path, gazda_path_out, sumar
