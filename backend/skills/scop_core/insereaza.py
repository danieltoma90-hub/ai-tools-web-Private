# -*- coding: utf-8 -*-
"""Inserarea capitolului CORE în documentul gazdă, cu renumerotarea capitolelor următoare.

Nu se atinge niciodată fișierul original: se lucrează pe un Document încărcat în
memorie, iar apelantul îl salvează sub alt nume.
"""
from __future__ import annotations

import copy
import pathlib
import re

from . import capitol
from . import stil

TIPAR_NUMAR = re.compile(r"^(\d+)(\.\d+)*\.?(\s|$)")

# Paragrafe non-heading cunoscute ca defecte de stil ale unei gazde: text care
# începe cu un număr de capitol, dar e formatat "Normal" în loc de "Heading 1"/
# "Heading 2" (ex. „7. Puncte de confirmat...” în gazda Producție). Fiecare
# intrare e o substring care identifică fără echivoc paragraful respectiv.
# Un viitor host cu un defect asemănător își adaugă propria intrare aici —
# fără să schimbe logica de potrivire din _e_paragraf_de_capitol.
DEFECTE_STIL_CUNOSCUTE = ("Puncte de confirmat",)


def _numar_capitol(text: str) -> int | None:
    m = TIPAR_NUMAR.match(text.strip())
    return int(m.group(1)) if m else None


def _e_paragraf_de_capitol(p) -> bool:
    """Adevărat doar dacă paragraful chiar poate reprezenta un titlu de capitol:
    stilizat Heading 1/2, sau explicit cunoscut ca defect de stil al gazdei
    (vezi DEFECTE_STIL_CUNOSCUTE) — ȘI, în acest al doilea caz, doar dacă
    paragraful chiar ÎNCEPE cu un număr de capitol. Fără condiția asta, orice
    paragraf de text obișnuit care conține din întâmplare fraza marcaj
    (ex. „Puncte de confirmat cu clientul înainte de semnare: lista de mai
    jos.”, fără niciun număr în față) ar fi confundat cu un titlu de capitol
    și ar deveni un capitol-fantomă în cuprinsul clientului — vezi
    `_repara_puncte_de_confirmat`, care aplică aceeași regulă la restilizare.
    Exclude, la fel, orice paragraf Normal obișnuit care începe întâmplător
    cu o cifră (ex. „300 de zile”), ca să nu fie confundat cu un capitol și
    renumerotat greșit — imunitatea gazdei actuale la acest caz vine din
    formatarea ei curată, nu din potrivirea de text, deci nu trebuie să
    depindem tacit de asta.
    """
    stil_nume = p.style.name if p.style is not None else None
    if stil_nume in ("Heading 1", "Heading 2"):
        return True
    if _numar_capitol(p.text) is None:
        return False
    return any(marcaj in p.text for marcaj in DEFECTE_STIL_CUNOSCUTE)


def _inlocuieste_numar_in_paragraf(p, vechi: str, nou: str) -> None:
    """Înlocuiește numărul de capitol de la începutul paragrafului cu ``nou``,
    păstrând formatarea fiecărui run neatinsă.

    Numărul poate fi împărțit între mai multe run-uri — Word rupe des run-urile
    la editare manuală. Se calculează segmentul exact de caractere (poziții în
    textul concatenat al paragrafului) ocupat de cifrele vechi, apoi se
    rescrie doar acel segment: primul run care se suprapune cu el primește
    tot textul ``nou``, iar run-urile următoare care se suprapun pierd doar
    porțiunea suprapusă. Niciun run neimplicat nu e atins și nicio proprietate
    (bold/italic/etc.) a run-urilor implicate nu e schimbată — doar `.text`.
    """
    text = p.text
    inceput = len(text) - len(text.lstrip())
    sfarsit = inceput + len(vechi)

    offset = 0
    scris_deja = False
    for run in p.runs:
        start_run = offset
        stop_run = offset + len(run.text)
        offset = stop_run

        s = max(start_run, inceput)
        e = min(stop_run, sfarsit)
        if s >= e:
            continue  # acest run nu atinge deloc numărul vechi

        s -= start_run
        e -= start_run
        if not scris_deja:
            run.text = run.text[:s] + nou + run.text[e:]
            scris_deja = True
        else:
            run.text = run.text[:s] + run.text[e:]


def renumeroteaza(doc, de_la: int) -> int:
    """Deplasează cu +1 capitolele >= de_la. Procesează descrescător ca să nu suprascrie."""
    tinte = []
    for p in doc.paragraphs:
        if not _e_paragraf_de_capitol(p):
            continue
        n = _numar_capitol(p.text)
        if n is not None and n >= de_la:
            tinte.append((n, p))

    tinte.sort(key=lambda pereche: pereche[0], reverse=True)

    for n, p in tinte:
        _inlocuieste_numar_in_paragraf(p, str(n), str(n + 1))

    return len(tinte)


def _repara_puncte_de_confirmat(doc) -> None:
    """Restilizează la Heading 1 doar un paragraf care e CHIAR titlul de
    capitol defect — adică începe cu un număr de capitol ȘI conține fraza
    marcaj (vezi DEFECTE_STIL_CUNOSCUTE). Fără condiția numărului, o
    propoziție obișnuită de text care doar menționează fraza (ex. „Puncte de
    confirmat cu clientul înainte de semnare: lista de mai jos.”) ar fi
    promovată la Heading 1 și ar apărea ca un capitol-fantomă în cuprinsul
    clientului — vezi și `_e_paragraf_de_capitol`, care aplică aceeași regulă.
    """
    for p in doc.paragraphs:
        e_defect_cunoscut = (
            _numar_capitol(p.text) is not None
            and any(marcaj in p.text for marcaj in DEFECTE_STIL_CUNOSCUTE)
        )
        if e_defect_cunoscut and p.style.name != "Heading 1":
            p.style = doc.styles["Heading 1"]


def insereaza_capitol(cale_gazda, sectiuni, numar: int = 5, nivel: int = 1,
                      client: str = "[NUME CLIENT]",
                      elemente: list[capitol.Element] | None = None):
    """Întoarce un Document nou = gazda cu capitolul inserat și capitolele renumerotate.

    Capitolul inserat include și elementele suplimentare (`elemente`), plasate
    exact ca în `capitol.construieste`: fiecare fie ca sub-capitol sub secțiunea
    lui, fie ca secțiune proprie la finalul capitolului — vezi docstring-ul
    acelei funcții pentru regulile complete de plasare și numerotare.
    `elemente=None` (implicit) și `elemente=[]` produc exact același rezultat.

    ATENȚIE — cuprinsul cache-uit rămâne neactualizat: Word păstrează un
    Cuprins real (câmp TOC) ca un bloc `w:sdt` cu paragrafe cache-uite pentru
    fiecare titlu + numărul de pagină. Acele paragrafe sunt imbricate în
    `w:sdt` și nu apar niciodată în `doc.paragraphs` — `renumeroteaza` nu are
    de unde să le vadă, deci nu le poate atinge. Documentul întors de această
    funcție are deci un Cuprins vizibil care încă arată numerotarea VECHE (de
    dinainte de inserare) și care NU conține capitolul CORE nou, până când
    cineva îl reîmprospătează manual în Word (clic-dreapta pe cuprins →
    "Update Field"/"Actualizare câmp", sau Ctrl+A → F9).

    Acesta e comportamentul normal al câmpurilor Word și nu trebuie „reparat”
    rescriind cache-ul — ar fi fragil și ar putea fi suprascris oricum la
    următoarea deschidere a documentului în Word. Contractul acestei funcții
    este: corpul documentului (capitolele, subcapitolele, conținutul) e
    complet și corect renumerotat; Cuprinsul afișat NU e, până la refresh
    manual. Apelantul (CLI-ul din Task 10) trebuie să semnaleze asta
    utilizatorului.
    """
    cale = pathlib.Path(cale_gazda)
    if not cale.is_file():
        raise FileNotFoundError(f"Documentul gazdă nu există: {cale}")

    gazda = stil.deschide_docx(cale)
    _repara_puncte_de_confirmat(gazda)
    renumeroteaza(gazda, de_la=numar)

    # capitolul, construit separat pe stilurile aceleiași gazde
    temp = stil.document_din_gazda(cale)
    capitol.construieste(temp, sectiuni, numar=numar, nivel=nivel, client=client,
                         elemente=elemente)

    ancora = _gaseste_ancora(gazda, numar + 1)
    for element in list(temp.element.body):
        if element.tag.endswith("}sectPr"):
            continue
        ancora.addprevious(copy.deepcopy(element))

    return gazda


def _gaseste_ancora(doc, numar_urmator: int):
    """Primul paragraf al capitolului care urmează după cel inserat."""
    for p in doc.paragraphs:
        if _e_paragraf_de_capitol(p) and _numar_capitol(p.text) == numar_urmator:
            return p._p
    # niciun capitol după: inserează înainte de sectPr, la finalul corpului
    return doc.element.body[-1]
