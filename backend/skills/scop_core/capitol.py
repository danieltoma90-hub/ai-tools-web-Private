# -*- coding: utf-8 -*-
"""Asamblarea capitolului standard CORE din secțiunile de conținut."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import stil
from .charisma_core import SECTIUNI, Sectiune

TITLU_CAPITOL = "Soluția ofertată — Charisma ERP CORE"

# Numărul de secțiuni canonice CORE — folosit ca prag fix de numerotare pentru
# elementele cu secțiune proprie ("<numar>.<10+k>"), nu lungimea efectivă a
# listei `sectiuni` primite de `construieste`. Rămâne fix indiferent câte
# secțiuni a selectat utilizatorul cu --fara/--doar, ca numerotarea unui
# element propriu să nu depindă de filtrul aplicat secțiunilor standard.
# Derivat din `len(SECTIUNI)`, nu ținut ca literal hand-sync-uit: o a 11-a
# secțiune canonică legitimă ar coliza tăcut cu primul element "propriu"
# (ambele "5.11.") dacă pragul ar rămâne fix la 10 din greșeală.
NUMAR_SECTIUNI_CANONICE = len(SECTIUNI)


@dataclass(frozen=True)
class Element:
    """Un element suplimentar față de standard, extras din documentul încărcat.

    Randarea lui e descrisă în `construieste`. Textul lui NU intervine niciodată
    în denumirea unui flux legat — vezi `_denumiri_fluxuri_legate`.
    """
    titlu: str
    text: str
    plasare: str          # cheia unei secțiuni CORE -> sub-capitol; "propriu" -> capitol nou
    fluxuri_legate: list[str] = field(default_factory=list)   # coduri: ["V2", "F5"]


@dataclass(frozen=True)
class Delimitare:
    """O intrare din „Delimitări de scop” — ce anume NU intră în scopul ofertat.

    Forma (`element` scurt + `precizare` clarificatoare) și randarea ca tabel
    „Element | Precizare” mimează exact capitolul „Delimitari de scop” pe
    care documentele gazdă reale (ex. Turkish Doner Steakhouse) îl au deja
    pentru același conținut — vezi `stil.tabel_delimitari`.
    """
    element: str
    precizare: str


def _denumiri_fluxuri_legate(fluxuri_legate: list[str]) -> list[str]:
    """Traduce codurile de fluxuri legate în denumirile lor verificate din SECTIUNI.

    Sursa denumirii e mereu `SECTIUNI` — niciodată un câmp al elementului. Un
    cod care nu se regăsește în niciun flux din `SECTIUNI` (de ex. un cod
    inventat sau greșit propus de un model) se ignoră tăcut: nu ridică eroare,
    nu produce text de rezervă și, esențial, nu deschide nicio cale prin care
    titlul sau textul elementului să ajungă în locul unei denumiri reale de
    tranzacție Charisma — acelea se verifică doar împotriva manualelor CORE,
    nu se inventează (vezi regula din `charisma_core.py`).
    """
    toate_fluxurile = {f.cod: f.flux for s in SECTIUNI for f in s.fluxuri}
    return [toate_fluxurile[cod] for cod in fluxuri_legate if cod in toate_fluxurile]


def _scrie_element(doc, el: Element, titlu_numerotat: str, nivel_titlu: int) -> None:
    """Randează un element suplimentar: titlu numerotat, text, apoi — dacă are
    fluxuri legate valide — o frază care le numește cu denumirile verificate.
    """
    stil.heading(doc, titlu_numerotat, nivel_titlu)
    stil.para(doc, el.text)

    denumiri = _denumiri_fluxuri_legate(el.fluxuri_legate)
    if denumiri:
        eticheta = "fluxul" if len(denumiri) == 1 else "fluxurile"
        stil.para(doc, f"Elementul este corelat cu {eticheta}: {', '.join(denumiri)}.")


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
                 client: str = "[NUME CLIENT]",
                 elemente: list[Element] | None = None,
                 delimitari: list[Delimitare] | None = None) -> None:
    """Scrie capitolul în `doc`, deja pregătit cu stilurile gazdei.

    `elemente` — elemente suplimentare față de standard, cu plasarea deja
    decisă (vezi `Element`): fiecare merge fie ca sub-capitol sub secțiunea
    ei (`plasare` = cheia secțiunii), fie ca secțiune proprie la finalul
    capitolului (`plasare = "propriu"`). Un element a cărui `plasare` numește
    o secțiune care nu e (sau nu mai e) printre cele din `sectiuni` — de
    exemplu utilizatorul a filtrat-o cu --fara/--doar — nu are sub ce
    sub-capitol să stea: cade la coada capitolului, alături de elementele
    "propriu" explicite, ca să nu se piardă tăcut conținutul din documentul
    încărcat de client. `elemente=None` (implicit) și `elemente=[]` produc
    exact același rezultat — ambele nu ating deloc pașii de mai jos.

    `delimitari` — ce anume NU intră în scopul ofertat (vezi `Delimitare`),
    randat ca ultimul sub-capitol, „Delimitări de scop”, DUPĂ toate secțiunile
    standard și după orice element „propriu” — vezi coada de mai jos. La fel
    ca la `elemente`, `delimitari=None` și `delimitari=[]` nu ating pasul
    respectiv: nicio secțiune „Delimitări de scop” nu apare, nici măcar goală.
    """
    elemente = elemente or []
    delimitari = delimitari or []
    chei_selectate = {s.cheie for s in sectiuni}

    stil.heading(doc, f"{numar}. {TITLU_CAPITOL}", nivel)
    stil.para(
        doc,
        f"Capitolul descrie funcționalitățile standard Charisma ERP CORE care intră în "
        f"scopul implementării la {client}, pe module, cu fluxurile operaționale acoperite.",
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

        elemente_sectiune = [el for el in elemente if el.plasare == s.cheie]
        for j, el in enumerate(elemente_sectiune, start=1):
            _scrie_element(doc, el, f"{numar}.{i}.{j}. {el.titlu}", nivel + 2)

    # Elemente cu secțiune proprie: cele marcate explicit "propriu" și cele a
    # căror secțiune țintă nu e printre `sectiuni` (vezi docstring-ul de mai
    # sus) — amestecate într-o singură coadă, numerotate contiguu în ordinea
    # din `elemente`, nu grupate separat după motivul pentru care au ajuns aici.
    elemente_proprii = [el for el in elemente if el.plasare not in chei_selectate]
    for k, el in enumerate(elemente_proprii, start=1):
        _scrie_element(doc, el, f"{numar}.{NUMAR_SECTIUNI_CANONICE + k}. {el.titlu}", nivel + 1)

    # „Delimitări de scop” — mereu ultimul sub-capitol, după cele zece secțiuni
    # standard ȘI după orice element „propriu” (continuă contiguu numerotarea
    # lor: dacă au fost N elemente proprii, secțiunea asta e "numar.N+1", la
    # fel cum ar fi fost al (N+1)-lea element propriu). Lista goală (implicit
    # sau explicit) nu scrie nimic — nici titlu, nici tabel gol.
    if delimitari:
        numar_delimitari = NUMAR_SECTIUNI_CANONICE + len(elemente_proprii) + 1
        stil.heading(doc, f"{numar}.{numar_delimitari}. Delimitări de scop", nivel + 1)
        stil.tabel_delimitari(doc, delimitari)
