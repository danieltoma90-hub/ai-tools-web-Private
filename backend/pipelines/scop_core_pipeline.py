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

`delimitari` (intrările „Delimitări de scop”) urmează exact același drum ca
`elemente`: dicturi brute din browser, validate tolerant (`_delimitare_din_dict`)
și duse identic pe ambele căi. `curata_antet_subsol` golește antetul/subsolul
moștenite din gazdă pe ambele căi, pentru cazul unei gazde reutilizate ca
șablon de stil pentru alt client — vezi `stil.curata_antet_subsol`.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from skills.scop_core import capitol, extractie, insereaza, stil
from skills.scop_core.charisma_core import SECTIUNI
from skills.scop_core.stil import DocumentInvalid  # re-exportat pentru router,
# care nu importă `skills.scop_core` direct — vezi docstring-ul de sus.

logger = logging.getLogger(__name__)

# cele zece chei de secțiune CORE, plus "propriu" — singurele valori valide
# pentru `plasare`, aceeași listă pe care se bazează și `extractie.py`.
_PLASARI_VALIDE: set[str] = {s.cheie for s in SECTIUNI} | {"propriu"}

CLIENT_IMPLICIT = "[NUME CLIENT]"


def _mktemp_path(suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return Path(name)


def valideaza_docx(cale: Path) -> None:
    """Verifică sincron că `cale` chiar se deschide ca document Word.

    Nu păstrează rezultatul — e o gardă rapidă, apelată de router imediat
    după descărcarea gazdei în `/scop-core/genereaza`, ÎNAINTE de a porni
    jobul de fundal. Fără ea, un fișier cu extensia `.docx` dar conținut
    invalid (ex. un `.xlsx` redenumit) trecea de verificarea de extensie,
    pornea un job care eșua abia mai târziu în `stil.document_din_gazda`, iar
    utilizatorul primea un job „error" cu mesaj tehnic în loc de un răspuns
    422 imediat — vezi raportul, itemul despre erorile de upload malformat.
    Ridică `DocumentInvalid` (mesaj curat, fără cale de fișier) dacă `cale`
    nu e un `.docx` valid.
    """
    stil.deschide_docx(cale)


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


def _delimitare_din_dict(brut: object) -> capitol.Delimitare | None:
    """Convertește un singur dict brut (din browser) într-un `capitol.Delimitare`.

    Aceeași filosofie tolerantă ca `_element_din_dict`: doar `dict`-uri sunt
    acceptate, iar `element`/`precizare` lipsă, goale după strip sau de alt
    tip decât `str` fac intrarea inutilizabilă — un rând din tabelul
    „Element | Precizare” fără unul din cele două câmpuri nu are ce însemna,
    și nu se completează tăcut cu text de rezervă inventat aici.
    """
    if not isinstance(brut, dict):
        return None

    element_brut = brut.get("element")
    element = element_brut.strip() if isinstance(element_brut, str) else ""
    precizare_brut = brut.get("precizare")
    precizare = precizare_brut.strip() if isinstance(precizare_brut, str) else ""
    if not element or not precizare:
        return None

    return capitol.Delimitare(element=element, precizare=precizare)


def _delimitari_din_dicturi(brute: object) -> tuple[list[capitol.Delimitare], int]:
    """Convertește lista de dicturi brute de delimitări; întoarce (valide, respinse).

    O `delimitari` care nu e deloc listă (None, obiect greșit trimis) e
    tratată ca listă goală — fără nicio excepție ridicată către router,
    exact ca la `_elemente_din_dicturi`.
    """
    if not isinstance(brute, list):
        return [], 0

    valide: list[capitol.Delimitare] = []
    respinse = 0
    for brut in brute:
        d = _delimitare_din_dict(brut)
        if d is None:
            respinse += 1
        else:
            valide.append(d)
    return valide, respinse


async def run_scop_core_pipeline(
    gazda_path: Path,
    client: str,
    elemente: list[dict],
    insereaza_in_gazda: bool,
    delimitari: list[dict] | None = None,
    curata_antet_subsol: bool = False,
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

    `delimitari` — intrările „Delimitări de scop” (dicturi brute din browser,
    convertite tolerant prin `_delimitari_din_dicturi`, în oglindă cu
    `elemente`), duse la fel spre `capitol.construieste`/`insereaza_capitol`
    și randate ca ultimul sub-capitol pe ambele căi.

    `curata_antet_subsol` — golește antetul/subsolul moștenite din gazdă (vezi
    `stil.curata_antet_subsol`), pentru cazul unei gazde reutilizate ca șablon
    de stil pentru alt client. Implicit `False`. Când e `False` ȘI clientul a
    fost completat efectiv (nu placeholder-ul implicit), sumarul semnalează
    dacă numele lui nu apare deloc în antetul/subsolul găsit — vezi
    `antet_subsol_avertisment` mai jos.
    """
    if on_step:
        on_step("parsing")

    sectiuni = capitol.alege_sectiuni()
    client_declarat = (client or "").strip()
    client_nume = client_declarat or CLIENT_IMPLICIT
    elemente_valide, elemente_respinse = _elemente_din_dicturi(elemente)
    delimitari_valide, delimitari_respinse = _delimitari_din_dicturi(delimitari)

    chei_sectiuni = {s.cheie for s in sectiuni}
    elemente_pe_sectiune = sum(1 for el in elemente_valide if el.plasare in chei_sectiuni)
    elemente_proprii = len(elemente_valide) - elemente_pe_sectiune

    if on_step:
        on_step("building")

    capitol_path = _mktemp_path(".docx")
    try:
        doc = stil.document_din_gazda(gazda_path)
        antet_text, subsol_text = stil.texte_antet_subsol(doc)
        if curata_antet_subsol:
            stil.curata_antet_subsol(doc)
        capitol.construieste(doc, sectiuni, client=client_nume, elemente=elemente_valide,
                             delimitari=delimitari_valide)
        doc.save(str(capitol_path))
    except Exception:
        capitol_path.unlink(missing_ok=True)
        raise

    # Mismatch de client în antetul/subsolul moștenit din gazdă — doar dacă
    # utilizatorul chiar a completat un client (altfel comparăm cu placeholder-ul
    # implicit, care evident n-apare niciodată) ȘI n-a cerut deja curățarea lor
    # (caz în care mismatch-ul e deja rezolvat, nu mai e nimic de semnalat).
    antet_subsol_avertisment = ""
    if not curata_antet_subsol and client_declarat and (antet_text or subsol_text):
        text_gasit = f"{antet_text}\n{subsol_text}".lower()
        if client_declarat.lower() not in text_gasit:
            bucati = []
            if subsol_text:
                bucati.append(f"subsol: „{subsol_text}”")
            if antet_text:
                bucati.append(f"antet: „{antet_text}”")
            antet_subsol_avertisment = (
                f"Numele clientului („{client_declarat}”) nu apare în antetul/subsolul moștenit "
                "din documentul gazdă — verifică dacă documentul a fost creat pentru alt client "
                "înainte să-l trimiți. Text găsit — " + "; ".join(bucati) + "."
            )

    gazda_path_out: Path | None = None
    avertismente: list[str] = []
    if elemente_respinse:
        avertismente.append(
            f"{elemente_respinse} element(e) suplimentar(e) primite din browser nu au putut fi "
            "folosite (titlu sau text lipsă) și au fost ignorate."
        )
    if delimitari_respinse:
        avertismente.append(
            f"{delimitari_respinse} intrare(intrări) de „Delimitări de scop” primite din browser "
            "nu au putut fi folosite (element sau precizare lipsă) și au fost ignorate."
        )

    if insereaza_in_gazda:
        if on_step:
            on_step("inserare")
        candidat = _mktemp_path(".docx")
        try:
            gazda_cu_capitol = insereaza.insereaza_capitol(
                gazda_path, sectiuni, client=client_nume, elemente=elemente_valide,
                delimitari=delimitari_valide, curata_antet_subsol=curata_antet_subsol,
            )
            gazda_cu_capitol.save(str(candidat))
            gazda_path_out = candidat
        except DocumentInvalid as e:
            # Mesajul lui `DocumentInvalid` e garantat curat (fără cale de
            # fișier) — sigur de arătat direct utilizatorului, spre deosebire
            # de orice altă excepție de mai jos.
            candidat.unlink(missing_ok=True)
            avertismente.append(f"Inserarea capitolului în documentul gazdă a eșuat: {e}")
        except Exception as e:
            # Excepție neprevăzută: nu interpolăm `{e}` brut într-un mesaj
            # către utilizator (poate conține o cale de fișier de pe server
            # sau alt detaliu tehnic) — detaliul rămâne în logul serverului,
            # utilizatorul primește un mesaj generic.
            candidat.unlink(missing_ok=True)
            logger.warning("Inserarea capitolului în gazdă a eșuat: %s", e)
            avertismente.append("Inserarea capitolului în documentul gazdă a eșuat.")

    sumar = {
        "sectiuni": len(sectiuni),
        "fluxuri": sum(len(s.fluxuri) for s in sectiuni),
        "elemente_primite": len(elemente) if isinstance(elemente, list) else 0,
        "elemente_plasate": len(elemente_valide),
        "elemente_pe_sectiune": elemente_pe_sectiune,
        "elemente_proprii": elemente_proprii,
        "elemente_respinse": elemente_respinse,
        "delimitari_primite": len(delimitari) if isinstance(delimitari, list) else 0,
        "delimitari_plasate": len(delimitari_valide),
        "delimitari_respinse": delimitari_respinse,
        "gazda_inserata": gazda_path_out is not None,
        "antet_subsol_curatat": curata_antet_subsol,
        "antet_subsol_avertisment": antet_subsol_avertisment,
        "avertisment": " ".join(avertismente),
    }
    return capitol_path, gazda_path_out, sumar
