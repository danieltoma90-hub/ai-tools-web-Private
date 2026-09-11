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

`titlu` și `text` sunt segmentate din documentul clientului — modelul nu le
rescrie, nu le rezumă și nu le parafrazează (vezi promptul).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from docx import Document

from .charisma_core import SECTIUNI

CLAUDE_MODEL = os.environ.get("SCOP_CORE_CLAUDE_MODEL", "claude-sonnet-4-6")
GROQ_MODEL = os.environ.get("SCOP_CORE_GROQ_MODEL", "openai/gpt-oss-120b")

# cele zece chei de secțiune CORE, în ordinea canonică din SECTIUNI
CHEI_SECTIUNI: list[str] = [s.cheie for s in SECTIUNI]
_PLASARI_VALIDE: set[str] = set(CHEI_SECTIUNI) | {"propriu"}


def _coduri_valide() -> set[str]:
    return {f.cod for s in SECTIUNI for f in s.fluxuri}


def _extrage_text(docx_path: Path) -> str:
    """Textul documentului încărcat, cu titlurile (stiluri Heading/Title)
    marcate distinct — ajută modelul să găsească segmentele naturale ale
    documentului fără să fie nevoit să rescrie nimic ca să le delimiteze."""
    doc = Document(str(docx_path))
    linii: list[str] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        stil_p = p.style.name if p.style else ""
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


_PROMPT_TEMPLATE = """Ești analist de business pentru implementări ERP Charisma. Primești un \
DOCUMENT SUPLIMENTAR încărcat de un client — cerințe sau elemente care depășesc funcționalitatea \
standard Charisma ERP CORE.

Sarcina ta are exact două părți:

1. SEGMENTEAZĂ documentul în elemente distincte. `titlu` și `text` se PREIAU din document — nu \
rescrie, nu rezuma, nu parafraza conținutul. Dacă documentul are deja titluri sau subtitluri \
(marcate cu "## " mai jos), folosește-le ca `titlu`; altfel formulează un titlu scurt, format \
doar din cuvinte care apar deja în text.

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
"fluxuri_legate": ["<cod>", ...]}}]}}

=== DOCUMENT SUPLIMENTAR ===
"""


def _construieste_prompt() -> str:
    return _PROMPT_TEMPLATE.format(
        chei=", ".join(CHEI_SECTIUNI), context_fluxuri=_context_fluxuri()
    )


def parse_json_block(text: str) -> Any:
    """Valoarea JSON din răspunsul modelului, chiar dacă vine încadrat în
    ```json``` sau cu text în jur. Un răspuns care nu conține JSON valid
    ridică `ValueError` cu mesaj clar — routerul îl poate arăta direct
    utilizatorului.

    Întoarce exact ce a parsat `json.loads` — nu neapărat un `dict`: un
    model poate răspunde sintactic valid cu `null`, cu o listă sau cu un
    număr la nivelul de bază. Apelantul (`propune_elemente`) verifică forma
    imediat după apel."""
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    candidate = match.group(1) if match else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", candidate)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Răspunsul modelului nu este JSON valid: {text[:300]!r}")


async def _call_claude(prompt: str, continut: str, max_tokens: int = 4_000) -> str:
    from anthropic import AsyncAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY lipsește de pe server — nu se poate apela Claude.")
    client = AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": f"{prompt}\n{continut}"}],
    )
    return resp.content[0].text


async def _call_groq(prompt: str, continut: str, max_tokens: int = 4_000) -> str:
    from groq import AsyncGroq

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY lipsește de pe server — nu se poate apela Groq.")
    client = AsyncGroq(api_key=api_key)
    kwargs = {"reasoning_effort": "low"} if GROQ_MODEL.startswith("openai/") else {}
    resp = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": f"{prompt}\n{continut}"}],
        max_tokens=max_tokens,
        temperature=0.1,
        **kwargs,
    )
    return resp.choices[0].message.content


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


async def propune_elemente(docx_path: Path, engine: str = "groq") -> list[dict]:
    """Segmentează documentul suplimentar de la `docx_path` și propune, pentru
    fiecare element găsit, o plasare printre secțiunile CORE.

    `engine`: "groq" (implicit, gratuit — pasul e opțional și nu trebuie să
    schimbe costul zero al capitolului standard) sau "claude".

    Întoarce o listă de dicturi validate — gata să alimenteze `capitol.Element`
    într-un pas ulterior, după ce utilizatorul le corectează în UI. Un răspuns
    care nu e JSON valid ridică `ValueError`; orice altă formă de răspuns
    garbage (elemente malformate, chei lipsă, tipuri greșite) e filtrată aici,
    nu propagată — vezi `_valideaza_elemente`.
    """
    text = _extrage_text(docx_path)
    if not text:
        return []

    prompt = _construieste_prompt()
    if engine == "claude":
        raw = await _call_claude(prompt, text)
    else:
        raw = await _call_groq(prompt, text)

    data = parse_json_block(raw)
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
