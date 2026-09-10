# -*- coding: utf-8 -*-
"""Construieste programul de training DIN specificatia clientului.

Deosebirea fata de CORE: la Productie nu exista un program standard de la care
sa pleci. Fiecare implementare de productie e alta — alte entitati tehnologice,
alte retete, alt mod de raportare — asa ca agenda se ridica integral din
documentul clientului. Ce nu scrie in document nu intra in training.
"""
from __future__ import annotations

import os

from pathlib import Path

from .spec_extract import MAX_SPEC_CHARS, _parse_json, extract_docx_text

MODEL = os.environ.get("TRAINING_CLAUDE_MODEL", "claude-sonnet-4-6")

MAX_MODULE = 12
MIN_ORE_MODUL = 0.5
MAX_ORE_MODUL = 8.0


def _prompt() -> str:
    return """Ești consultant ERP care pregătește școlarizarea operatorilor unui client Charisma.

Primești specificația/documentul de scop al clientului pentru zona de producție.
Construiești programul de training EXCLUSIV din ce scrie în acest document.

REGULA CARE CONTEAZĂ CEL MAI MULT:
Nu există un program standard de producție. Nu adăuga funcționalitate Charisma
care nu apare explicit în document, oricât de firească ți s-ar părea. Dacă
documentul nu vorbește despre planificare pe capacități, despre control de
calitate sau despre orice altceva, acele lucruri NU intră în agendă. Un modul
inventat îl pune pe consultant în situația să predea ceva ce clientul nu are.

Cum construiești:
- Urmează structura și ordinea documentului. Capitolele lui sunt, de regulă,
  chiar modulele de training (configurări, programare tehnică, necesare,
  transferuri, execuție, raportare, costuri — dacă și cum apar acolo).
- Fiecare subiect trebuie să fie ceva ce operatorul va face în sistem, formulat
  din perspectiva lui.
- Când documentul dă calea de acces din meniu, pune-o în subiect, în paranteză:
  „Definirea punctelor de lucru (Producție → Configurare → Puncte de lucru)".
- Când documentul dă detalii concrete ale clientului (entități tehnologice,
  denumiri de gestiuni, procente de pierderi, echipe), păstrează-le în text.
  Ele fac diferența dintre un training real și unul generic.
- Estimează pentru fiecare modul orele necesare acoperirii lui la ritm normal,
  în trepte de 0,5h. Nu încerca să nimerești un total anume — durata finală o
  distribuie altcineva.

Răspunde DOAR cu JSON valid:
{"module": [
  {"nume": "Denumirea modulului, așa cum reiese din document",
   "ore": 2.5,
   "audienta": "Cine trebuie să participe (ex: Operatori ambalare, șef secție)",
   "grupe": [
     {"titlu": "Subcapitol de conținut",
      "subiecte": ["Ce face operatorul, concret", "..."]}
   ]}
]}

Limite: maximum 12 module, 1-4 grupe per modul, 2-8 subiecte per grupă.
Dacă documentul nu conține suficient material pentru un training, returnează
{"module": []} — mai bine spui asta decât să umpli cu presupuneri."""


def _curata_modul(brut: dict, nr: int) -> dict | None:
    nume = (brut.get("nume") or "").strip()
    if not nume:
        return None

    grupe: list[tuple[str, list[str]]] = []
    for g in brut.get("grupe") or []:
        if not isinstance(g, dict):
            continue
        titlu = (g.get("titlu") or "").strip()
        subiecte = [
            s.strip() for s in (g.get("subiecte") or [])
            if isinstance(s, str) and s.strip()
        ]
        if titlu and subiecte:
            grupe.append((titlu, subiecte))
    if not grupe:
        return None

    try:
        ore = float(brut.get("ore") or 0)
    except (TypeError, ValueError):
        ore = 0.0
    ore = round(min(max(ore, MIN_ORE_MODUL), MAX_ORE_MODUL) * 2) / 2

    return {
        "nr": nr,
        "nume": nume,
        "ore": ore,
        "audienta": (brut.get("audienta") or "Operatori producție").strip(),
        # Nimic din specificatie nu e „standard", deci nimic nu e protejat de
        # comprimare: la o durata prea scurta, planificatorul taie de la coada
        # si raporteaza explicit ce a ramas neacoperit.
        "esential": False,
        "grupe": grupe,
    }


async def construieste_module_din_spec(spec_path: Path, api_key: str) -> list[dict]:
    """Modulele de training deduse din specificatie. Ridica eroare daca nu iese nimic."""
    from anthropic import AsyncAnthropic

    text = extract_docx_text(spec_path)
    if not text.strip():
        raise ValueError(
            "Specificația nu conține text care să poată fi citit "
            "(document gol sau doar imagini)."
        )
    if len(text) > MAX_SPEC_CHARS:
        text = text[:MAX_SPEC_CHARS] + "\n[...specificație trunchiată...]"

    client = AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": f"{_prompt()}\n\n---SPECIFICAȚIE CLIENT---\n{text}",
        }],
    )

    brute = _parse_json(resp.content[0].text).get("module", [])
    module = []
    for b in brute[:MAX_MODULE]:
        if not isinstance(b, dict):
            continue
        curat = _curata_modul(b, len(module) + 1)
        if curat:
            module.append(curat)

    if not module:
        raise ValueError(
            "Din specificație nu a rezultat niciun modul de training. "
            "Verifică dacă documentul descrie fluxul operațional (ecrane, "
            "documente, pași de lucru), nu doar obiective comerciale."
        )
    return module
