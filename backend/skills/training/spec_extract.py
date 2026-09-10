# -*- coding: utf-8 -*-
"""Extrage din specificatia clientului particularitatile care trebuie predate.

Un training standard preda sistemul asa cum vine din cutie. Clientul insa a
cerut lucruri proprii — ecrane noi, fluxuri adaptate, campuri obligatorii in
plus — iar operatorul lui pe acelea le va folosi zilnic. Le identificam si le
atasam modulului potrivit, marcate distinct fata de continutul standard.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from docx import Document

MODEL = os.environ.get("TRAINING_CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_SPEC_CHARS = 120_000   # specificatiile trec de 150k; taiem cu marja de siguranta


def extract_docx_text(path: Path) -> str:
    doc = Document(str(path))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for t in doc.tables:
        for row in t.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _prompt(module_nume: list[str]) -> str:
    lista = "\n".join(f"- {n}" for n in module_nume)
    return f"""Ești consultant ERP care pregătește școlarizarea utilizatorilor unui client Charisma.

Primești specificația funcțională a clientului. Identifici PARTICULARITĂȚILE lui —
lucrurile care diferă de sistemul standard și pe care operatorii TREBUIE instruiți
distinct: ecrane dezvoltate special, fluxuri adaptate, câmpuri obligatorii proprii,
rapoarte specifice, integrări, reguli de business proprii.

Modulele de training disponibile:
{lista}

Răspunde DOAR cu JSON valid:
{{"particularitati": [
  {{"modul": "<exact un nume din listă>",
    "titlu": "Denumire scurtă a particularității (max 70 caractere)",
    "detaliu": "Ce anume trebuie să știe operatorul să facă — o propoziție",
    "cod": "codul cerinței dacă apare în specificație (CR.01.02, OF08.01), altfel ''"}}
]}}

Reguli:
- Doar ce e SPECIFIC clientului. Funcționalitatea standard Charisma nu se listează —
  aceea e deja acoperită de programul standard.
- Atribuie fiecare particularitate modulului în care operatorul o va folosi.
- Formulează din perspectiva a ce face utilizatorul, nu a ce dezvoltă IT-ul.
- Maximum 25 de particularități, cele cu impact real în operarea zilnică.
- Dacă specificația nu conține nimic specific, returnează listă goală."""


def _parse_json(text: str) -> dict:
    """JSON-ul din răspuns, chiar dacă vine cu explicații în jur sau ciobit.

    Un răspuns tăiat la mijloc n-are voie să arunce toată extragerea: ultimul
    pas repară JSON-ul malformat, ca în pipeline-ul de minută.
    """
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    candidate = m.group(1) if m else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    bloc = re.search(r"\{[\s\S]*\}", candidate)
    if bloc:
        try:
            return json.loads(bloc.group(0))
        except json.JSONDecodeError:
            pass

    try:
        from json_repair import repair_json
    except ImportError:
        raise ValueError(f"Răspuns care nu conține JSON: {text[:200]}")

    reparat = repair_json(bloc.group(0) if bloc else candidate)
    if reparat and reparat.strip() not in ("", "null", "{}"):
        return json.loads(reparat)
    raise ValueError(f"Răspuns care nu conține JSON: {text[:200]}")


_DIACRITICE = str.maketrans("ăâîșşțţ", "aaisstt")
_CUVINTE_GOALE = {"modul", "de", "si", "informatii", "generale"}


def _cuvinte(nume: str) -> frozenset[str]:
    curat = nume.lower().translate(_DIACRITICE)
    return frozenset(
        c for c in re.findall(r"[a-z]+", curat)
        if c not in _CUVINTE_GOALE and len(c) > 2
    )


def _nediscriminante(module_nume: list[str]) -> frozenset[str]:
    """Cuvintele care apar în jumătate din denumiri nu deosebesc nimic.

    „Producție" e în trei din cele cinci module de Producție: dacă l-am lua în
    calcul, „Costuri" ar semăna la fel de bine cu oricare dintre ele.
    """
    numarate: dict[str, int] = {}
    for nume in module_nume:
        for c in _cuvinte(nume):
            numarate[c] = numarate.get(c, 0) + 1
    prag = max(2, len(module_nume) // 2)
    return frozenset(c for c, n in numarate.items() if n >= prag)


def potriveste_modul(propus: str, module_nume: list[str]) -> str:
    """Numele de modul din catalog care corespunde celui propus de AI.

    „Nomenclatoare producție" și „Nomenclatoare de producție" sunt același modul.
    Fără potrivirea asta, orice abatere de o literă ar trimite particularitatea
    pe primul modul din catalog și agenda ar ieși amestecată.

    Când nimic nu seamănă, particularitatea merge pe primul modul — acolo unde
    ambele cataloage țin partea generală, de configurare — pentru că o
    particularitate pusă alături e recuperabilă, una pierdută nu.
    """
    if propus in module_nume:
        return propus

    surplus = _nediscriminante(module_nume)
    tinta = _cuvinte(propus) - surplus
    if tinta:
        scoruri = [(len(_cuvinte(n) - surplus & tinta), n) for n in module_nume]
        scor, nume = max(scoruri, key=lambda x: x[0])
        if scor > 0:
            return nume

    return module_nume[0]


async def extrage_particularitati(
    spec_path: Path, module_nume: list[str], api_key: str
) -> list[dict]:
    """Un singur apel Claude, care intoarce particularitatile gasite.

    Erorile de provider urca la apelant: el stie daca specificatia e obligatorie
    (Productie) sau doar un plus (CORE) si decide daca opreste sau avertizeaza.
    """
    from anthropic import AsyncAnthropic

    text = extract_docx_text(spec_path)
    if not text.strip():
        return []
    if len(text) > MAX_SPEC_CHARS:
        text = text[:MAX_SPEC_CHARS] + "\n[...specificație trunchiată...]"

    client = AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model=MODEL,
        # 25 de particularitati cu detaliu incap in ~2500 de tokeni; lasam
        # marja dubla, ca raspunsul sa nu se taie la mijlocul JSON-ului.
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": f"{_prompt(module_nume)}\n\n---SPECIFICAȚIE CLIENT---\n{text}",
        }],
    )
    data = _parse_json(resp.content[0].text)
    items = data.get("particularitati", [])

    out = []
    for it in items:
        if not isinstance(it, dict) or not it.get("titlu"):
            continue
        modul = potriveste_modul(it.get("modul", ""), module_nume)
        out.append({
            "modul": modul,
            "titlu": it["titlu"].strip(),
            "detaliu": (it.get("detaliu") or "").strip(),
            "cod": (it.get("cod") or "").strip(),
        })
    return out


def ataseaza_la_module(module: list[dict], particularitati: list[dict]) -> list[dict]:
    """Adauga fiecare particularitate ca grupa separata in modulul ei.

    Grupa se numeste explicit „Particularități client" ca sa se distinga de
    continutul standard si in Word, si in Excel.
    """
    if not particularitati:
        return module

    # Ultima poarta inainte de document. Foloseste aceeasi potrivire ca la
    # extragere: un nume aproximativ („Trasabilitate" pentru „Trasabilitate si
    # calitate") trebuie sa ajunga la modulul lui, nu pe primul din catalog.
    nume = [m["nume"] for m in module]
    pe_modul: dict[str, list[dict]] = {}
    for p in particularitati:
        pe_modul.setdefault(potriveste_modul(p.get("modul", ""), nume), []).append(p)

    for m in module:
        proprii = pe_modul.get(m["nume"], [])
        if not proprii:
            continue
        subiecte = []
        for p in proprii:
            linie = p["titlu"]
            if p["detaliu"]:
                linie += f" — {p['detaliu']}"
            if p["cod"]:
                linie += f" ({p['cod']})"
            subiecte.append(linie)
        m["grupe"] = list(m["grupe"]) + [("Particularități client", subiecte)]
        m["nr_particularitati"] = len(proprii)
        # continutul propriu al clientului cere timp peste standard
        m["ore"] = m["ore"] + 0.5 * len(proprii)

    return module
