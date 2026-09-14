# -*- coding: utf-8 -*-
"""Segmentarea documentului suplimentar și propunerea de plasare (Task 3).

Utilizatorul încarcă un document suplimentar față de standardul Charisma ERP
CORE (cerințe care depășesc capitolul standard). Acest modul face UN singur
apel de model care:
  1. segmentează documentul în elemente (titlu + text),
  2. propune, pentru fiecare, o plasare — sub-capitol al uneia din cele zece
     secțiuni CORE, sau secțiune proprie ("propriu").

Utilizatorul corectează plasările în UI înainte ca `capitol.Element` să fie
construit dintr-un dict validat aici — vezi `capitol.py`.

Apelul de model trece prin `llm_client` (rădăcina `backend/`), clientul comun
provider-agnostic al repo-ului — nu prin apeluri proprii către Anthropic sau
Groq. Varianta inițială a acestui modul avea `_call_claude`/`_call_groq`
proprii, copiate din `skills/scenarii/ai_gen.py`; s-a renunțat la ele pentru
că, la verificare, `ANTHROPIC_API_KEY` din acest proiect e invalidă și
`GROQ_API_KEY` lipsește complet din `.env` — niciuna nu poate autentifica.
`MISTRAL_API_KEY`, singura cheie validă disponibilă, e exact ceea ce
`llm_client` folosește implicit, cu throttle și retry deja incluse pentru
tier-ul ei gratuit. Nu mai există parametru de alegere a providerului
(`engine`) — un singur furnizor, un singur drum.

Regula centrală, ținută prin construcție (nu doar prin instrucțiuni în prompt):
modelul NU are voie să introducă o denumire de flux Charisma în datele
întoarse. Cele 47 de fluxuri din `charisma_core.py` au fost verificate pe
manualele oficiale, în douăsprezece runde de review — o denumire inventată
într-o ofertă comercială e o eroare de fapt pe care clientul o observă și care
subminează tot lanțul de conținut.

De-a lungul acestui modul se aplică mereu regula: fluxurile se referă prin
COD (ex: "V2", "F5"). Modelul primește codurile doar ca context de
clasificare (`_context_fluxuri`), i se cere explicit în prompt să răspundă
tot prin cod, iar după parsare `fluxuri_legate` se filtrează la codurile
existente în `SECTIUNI` (`_coduri_valide`) — orice altceva, inclusiv o
denumire completă de tranzacție scrisă acolo de model, e aruncat tăcut,
exact ca la randare în `capitol._denumiri_fluxuri_legate`. Denumirea reală
se traduce din cod abia în `capitol.py`, niciodată aici.

`text` e un extras copiat din documentul clientului — modelul nu are voie
să-l rescrie, să-l rezume, să-l completeze sau să-l parafrazeze, și mai ales
nu are voie să adauge exemple, cifre, praguri valorice sau nume de roluri pe
care documentul nu le conține (vezi promptul). Doar `titlu` poate fi compus
de model, ca etichetă scurtă, când documentul nu oferă unul propriu.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

import llm_client

from . import stil
from .charisma_core import SECTIUNI

# Bugetul de tokeni al apelului de model — cât mai mare (limita practică a
# providerului), pentru că `text` trebuie extras verbatim: lungimea lui
# scalează cu documentul, nu cu un rezumat, iar implicitul lui `llm_client`
# (4000) taie JSON-ul la jumătate pe orice document de dimensiune reală. Alte
# extractoare din acest repo cu aceeași nevoie (extras integral, nu rezumat)
# folosesc aceeași valoare — vezi `skills/training/spec_extract.py` și
# `skills/training/spec_build.py`.
MAX_TOKENS_RASPUNS = 8192

# cele zece chei de secțiune CORE, în ordinea canonică din SECTIUNI
CHEI_SECTIUNI: list[str] = [s.cheie for s in SECTIUNI]
_PLASARI_VALIDE: set[str] = set(CHEI_SECTIUNI) | {"propriu"}


def _coduri_valide() -> set[str]:
    return {f.cod for s in SECTIUNI for f in s.fluxuri}


def _iter_blocuri(doc):
    """Paragrafele și tabelele documentului, în ordinea reală din body.

    `doc.paragraphs` omite tabelele cu totul — un document al cărui conținut
    e (parțial sau integral) un tabel de cerințe, cum e caietul de sarcini
    standard TotalSoft, ar pierde tăcut acele rânduri. Tiparul de mai jos
    (`doc.element.body` + `docx.table.Table`/`docx.text.paragraph.Paragraph`)
    e cel deja folosit în acest repo pentru exact aceeași nevoie — vezi
    `skills/minuta/scripts/context_parser.py::_iter_blocks`."""
    for copil in doc.element.body:
        if copil.tag == qn("w:p"):
            yield Paragraph(copil, doc)
        elif copil.tag == qn("w:tbl"):
            yield Table(copil, doc)


def _randuri_tabel(tabel: Table) -> list[str]:
    """Fiecare rând al tabelului, ca `celulă | celulă | ...` — un rând cu
    toate celulele goale nu adaugă nimic (zgomot, nu conținut)."""
    randuri = []
    for row in tabel.rows:
        celule = [cell.text.strip() for cell in row.cells]
        if any(celule):
            randuri.append(" | ".join(celule))
    return randuri


def _extrage_text(docx_path: Path) -> str:
    """Textul documentului încărcat, cu titlurile (stiluri Heading/Title)
    marcate distinct — ajută modelul să găsească segmentele naturale ale
    documentului fără să fie nevoit să rescrie nimic ca să le delimiteze.
    Tabelele (ex. caietul de sarcini standard, o matrice de cerințe) sunt
    incluse rând cu rând, la locul lor real în document — vezi `_iter_blocuri`."""
    doc = stil.deschide_docx(docx_path)
    linii: list[str] = []
    for bloc in _iter_blocuri(doc):
        if isinstance(bloc, Table):
            linii.extend(_randuri_tabel(bloc))
            continue
        text = bloc.text.strip()
        if not text:
            continue
        stil_p = bloc.style.name if bloc.style else ""
        if re.match(r"^(Heading \d|Title)$", stil_p, re.I):
            linii.append(f"\n## {text}")
        else:
            linii.append(text)
    return "\n".join(linii).strip()


def _context_fluxuri() -> str:
    """Cele 47 de fluxuri CORE ca perechi cod -> denumire, grupate pe
    secțiune — DOAR context de clasificare pentru model. Niciodată sursă de
    text pentru `titlu`/`text` ale elementelor generate."""
    blocuri = []
    for s in SECTIUNI:
        linii = "\n".join(f"  {f.cod} -> {f.flux}" for f in s.fluxuri)
        blocuri.append(f"[{s.cheie}] {s.titlu}\n{linii}")
    return "\n".join(blocuri)


_SYSTEM_TEMPLATE = """Ești analist de business pentru implementări ERP Charisma. Primești, ca \
mesaj separat de la utilizator, un DOCUMENT SUPLIMENTAR încărcat de un client — cerințe sau \
elemente care depășesc funcționalitatea standard Charisma ERP CORE.

Sarcina ta are exact două părți:

1. SEGMENTEAZĂ documentul în elemente distincte. `text` este un EXTRAS COPIAT cuvânt cu cuvânt din \
document — nu reformula, nu rezuma, nu completa și nu parafraza conținutul. NU adăuga exemple, \
cifre, praguri valorice, sume, procente, nume de roluri sau de funcții, sau orice alt detaliu \
concret pe care documentul nu îl conține deja — chiar dacă ți se pare plauzibil sau util pentru \
un client din acest domeniu. Dacă o cerință e formulată într-o singură propoziție, `text` este \
EXACT acea propoziție — un element scurt e corect, nu un eșec de extragere. `titlu`, singurul câmp \
unde ai voie să compui: dacă documentul are deja titluri sau subtitluri (marcate cu "## " în \
textul primit), folosește-le ca `titlu`; altfel formulează un titlu scurt, descriptiv, format doar \
din cuvinte care apar deja în text — nu inventa un titlu care sugerează conținut ce nu există în \
`text`.

2. Pentru FIECARE element, propune o PLASARE: cheia secțiunii CORE sub care se potrivește cel \
mai bine ca sub-capitol, sau exact valoarea "propriu" dacă elementul nu se potrivește la nicio \
secțiune standard. Cheile valide sunt STRICT acestea: {chei}. Nu inventa alte chei.

Mai jos ai cele 47 de fluxuri operaționale standard CORE, grupate pe secțiune, ca perechi \
cod -> denumire — folosește-le DOAR ca să identifici ce fluxuri standard atinge fiecare element \
(câmpul `fluxuri_legate`). NU relua și nu parafraza denumirile de fluxuri în `titlu` sau `text`. \
ESENȚIAL: în `fluxuri_legate` referă fluxurile STRICT prin cod (de exemplu "V2", "F5") — \
NICIODATĂ prin denumire. Denumirea finală, verificată, se traduce din cod în altă parte a \
sistemului — a ta nu contează și va fi ignorată dacă apare acolo.

=== FLUXURI STANDARD CORE (cod -> denumire) ===
{context_fluxuri}

Răspunde DOAR cu JSON valid, fără text în plus, fără explicații:
{{"elemente": [{{"titlu": "...", "text": "...", "plasare": "<o cheie din listă sau propriu>", \
"fluxuri_legate": ["<cod>", ...]}}]}}"""


def _construieste_system_prompt() -> str:
    """Regulile și catalogul de fluxuri — partea stabilă a interacțiunii,
    trimisă ca mesaj `system` către `llm_client.chat`. Textul documentului
    clientului NU intră aici, ci în mesajul `user` — vezi `propune_elemente`."""
    return _SYSTEM_TEMPLATE.format(
        chei=", ".join(CHEI_SECTIUNI), context_fluxuri=_context_fluxuri()
    )


def _valideaza_elemente(bruti, coduri_valide: set[str]) -> list[dict]:
    """Aplică regulile din brief peste elementele brute întoarse de model.

    Nimic de aici nu are voie să ridice o excepție pe un răspuns garbage —
    un element malformat se aruncă sau se corectează, nu blochează restul.
    """
    rezultat: list[dict] = []
    for it in bruti:
        if not isinstance(it, dict):
            continue

        titlu_raw = it.get("titlu")
        titlu = titlu_raw.strip() if isinstance(titlu_raw, str) else ""
        text_raw = it.get("text")
        text = text_raw.strip() if isinstance(text_raw, str) else ""
        if not titlu or not text:
            continue

        plasare = it.get("plasare")
        if not isinstance(plasare, str) or plasare not in _PLASARI_VALIDE:
            plasare = "propriu"

        fluxuri_raw = it.get("fluxuri_legate")
        if not isinstance(fluxuri_raw, list):
            fluxuri_raw = []
        # doar strip — fără case-folding: "MF1" și "M1" sunt coduri distincte,
        # ale unor secțiuni diferite, iar a le trata la fel ar fi un pas spre
        # ghicit, lucru pe care acest modul nu îl face niciodată. Un spațiu
        # parazit (" V2 ") e zgomot de formatare de la un model gratuit și
        # se recuperează; o literă mică ("v2") nu se potrivește cu niciun cod
        # real și se aruncă, la fel ca un cod inexistent.
        fluxuri_legate = []
        for c in fluxuri_raw:
            if not isinstance(c, str):
                continue
            cod = c.strip()
            if cod in coduri_valide:
                fluxuri_legate.append(cod)

        rezultat.append({
            "titlu": titlu,
            "text": text,
            "plasare": plasare,
            "fluxuri_legate": fluxuri_legate,
        })
    return rezultat


def _pare_trunchiat(raw: str) -> bool:
    """Euristică pentru „răspunsul modelului s-a oprit la mijlocul JSON-ului”
    (depășire de `max_tokens`), fără să inspecteze `finish_reason` —
    `llm_client.chat` întoarce doar textul, nu și motivul opririi, iar a-l
    expune ar cere modificarea lui `llm_client.py`, în afara acestui fix
    (vezi raportul). Un răspuns JSON complet, chiar împachetat în
    ```json ... ```, se termină mereu cu acolada de închidere a obiectului
    de nivel de bază; unul tăiat la mijloc aproape sigur nu. Nu e o dovadă
    matematică — un răspuns garbage complet, coincidental, s-ar putea și el
    termina fără acoladă — dar diferențiază corect cazul care contează aici:
    un document mare, valid, al cărui răspuns depășește bugetul de tokeni.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return text.startswith("{") and not text.endswith("}")


async def propune_elemente(docx_path: Path) -> list[dict]:
    """Segmentează documentul suplimentar de la `docx_path` și propune, pentru
    fiecare element găsit, o plasare printre secțiunile CORE.

    Apelul de model trece prin `llm_client` — clientul comun, provider-agnostic
    al repo-ului (implicit Mistral La Plateforme, tier gratuit), cu throttle,
    retry pe 429/5xx și buget zilnic incluse acolo. Nu mai există alegere de
    provider aici: modulul nu mai apelează Anthropic sau Groq direct (vezi
    docstring-ul de sus al fișierului pentru motiv) — un singur furnizor,
    un singur drum.

    Întoarce o listă de dicturi validate — gata să alimenteze `capitol.Element`
    într-un pas ulterior, după ce utilizatorul le corectează în UI. Un răspuns
    care nu e JSON valid ridică `ValueError`; orice altă formă de răspuns
    garbage (elemente malformate, chei lipsă, tipuri greșite) e filtrată aici,
    nu propagată — vezi `_valideaza_elemente`. O eroare de rețea/autentificare
    la nivelul lui `llm_client` (cheie lipsă, 429 după reîncercări epuizate)
    urcă neschimbată, ca `RuntimeError` — vezi `llm_client.chat`.
    """
    text = _extrage_text(docx_path)
    if not text:
        return []

    raw = await llm_client.chat(
        _construieste_system_prompt(), text, max_tokens=MAX_TOKENS_RASPUNS, json_mode=True,
    )

    try:
        data = llm_client.parse_json(raw)
    except json.JSONDecodeError as exc:
        if _pare_trunchiat(raw):
            raise ValueError(
                "Documentul suplimentar e prea mare pentru un singur răspuns al "
                "modelului — răspunsul a fost tăiat înainte să se termine JSON-ul. "
                "Încarcă un document mai scurt sau împarte-l în mai multe."
            ) from exc
        raise ValueError(f"Răspunsul modelului nu este JSON valid: {raw[:300]!r}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            "Răspunsul modelului e JSON valid, dar nu are forma așteptată "
            f"(un obiect cu cheia \"elemente\") — a întors în schimb un "
            f"{type(data).__name__}: {raw[:300]!r}"
        )
    bruti = data.get("elemente")
    if not isinstance(bruti, list):
        bruti = []

    return _valideaza_elemente(bruti, _coduri_valide())
