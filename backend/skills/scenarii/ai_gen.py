# -*- coding: utf-8 -*-
"""Generarea AI a scenariilor din cerintele specifice + pass-ul de dependente.

Ruleaza pe Claude, prin drumul comun `claude.py`. Varianta gratuita (Groq) a
fost scoasa: un singur motor, un singur drum.
"""
from __future__ import annotations

import json
import logging
import re

import claude

from .spec_parser import SpecificRequirement

ROMANIAN_CHARS_PER_TOKEN = 2.2

logger = logging.getLogger(__name__)

# bugetul de input per lot (chars)
CLAUDE_BATCH_CHARS = 30_000

SHEETS = [
    "⚙️ Configurare", "🏷️ Articole", "📦 Coduri Bare", "💰 Liste Preturi",
    "👥 Parteneri", "🛒 Comenzi Achiz.", "📥 Receptie NIR", "🧾 Facturi Achiz.",
    "📤 Vanzari", "📊 Stocuri", "🔄 Transfer & Inventar", "🏭 Mijloace Fixe",
    "💳 Financiar", "📚 Contabilitate", "🗂️ Import Date",
]
_MODULE_SHEET_FALLBACK = {
    "articole": "🏷️ Articole", "parteneri": "👥 Parteneri",
    "gestiuni": "🔄 Transfer & Inventar", "centre de cost": "⚙️ Configurare",
    "modul achizitii": "🧾 Facturi Achiz.", "modul depozit": "📊 Stocuri",
    "modul vanzari": "📤 Vanzari", "modul mijloace fixe": "🏭 Mijloace Fixe",
    "modul financiar": "💳 Financiar", "modul contabilitate": "📚 Contabilitate",
}

_GEN_PROMPT = """Ești inginer QA senior pentru ERP Charisma. Primești CERINȚE SPECIFICE ale unui client \
(identificate la analiză, în plus față de funcționalitatea standard). Pentru FIECARE cerință generează \
1-2 scenarii de testare concrete (cazul principal + un caz negativ dacă cerința conține validări/restricții), \
STRICT pe baza textului cerinței — nu inventa funcționalități.

Scrie în română cu diacritice. Pașii numerotați (4-6 pași), concreți, cu denumirile de ecrane/tranzacții din text.
Fiecare scenariu se alocă unui sheet din lista: {sheets}

Răspunde DOAR cu JSON valid:
{{"scenarii": [{{"cerinta_index": <nr cerinței din input>, "sheet": "<exact din listă>", \
"Scenariu": "titlu concret", "Obiectiv": "...", "Pasi de Test": "1. ...\\n2. ...", \
"Rezultat Asteptat": "...", "Tip Test": "Functional - Pozitiv" sau "Functional - Negativ", \
"Prioritate": "Critical"|"High"|"Medium"}}]}}"""

_DEPS_PROMPT = """Ești QA lead pentru ERP Charisma. Primești indexul scenariilor de testare existente \
(ID | modul | titlu) și scenariile NOI din cerințele specifice ale clientului.
Pentru fiecare scenariu NOU, stabilește ce scenarii trebuie executate CU SUCCES înainte \
(precondiții de execuție): maxim 3, doar dacă legătura e reală (date/documente necesare). \
Folosește DOAR ID-uri din index.

Răspunde DOAR cu JSON valid: {"dependente": {"<ID scenariu nou>": ["<ID>", ...], ...}}
Scenariile fără dependențe reale se omit din răspuns."""


def parse_json_block(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    candidate = match.group(1) if match else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", candidate)
        if m:
            return json.loads(m.group(0))
        raise


# ── Provider ─────────────────────────────────────────────────────────────────

async def _call_claude(prompt: str, content: str, max_tokens: int) -> str:
    raspuns = await claude.raspunde(f"{prompt}\n\n{content}", max_tokens=max_tokens, efort="medium")
    return raspuns.text


# ── Loturi de cerinte ────────────────────────────────────────────────────────

def batch_requirements(reqs: list[SpecificRequirement], batch_chars: int) -> list[list[int]]:
    """Grupeaza indecsii cerintelor in loturi sub bugetul de caractere."""
    batches: list[list[int]] = []
    current: list[int] = []
    size = 0
    for i, r in enumerate(reqs):
        r_size = len(r.title) + min(len(r.text), batch_chars)  # cerintele uriase se trunchiaza
        if current and size + r_size > batch_chars:
            batches.append(current)
            current, size = [], 0
        current.append(i)
        size += r_size
    if current:
        batches.append(current)
    return batches


def _batch_content(reqs: list[SpecificRequirement], idxs: list[int], batch_chars: int) -> str:
    lines = []
    for i in idxs:
        r = reqs[i]
        text = r.text if len(r.text) <= batch_chars else r.text[:batch_chars] + " [...]"
        header = f"=== CERINTA {i} | {r.item_no} {r.title}"
        if r.code:
            header += f" | Cod: {r.code}"
        header += f" | Modul: {r.module_h2} ==="
        lines.append(header)
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


async def generate_specific_scenarios(
    reqs: list[SpecificRequirement],
    on_step=None,
) -> list[dict]:
    """Genereaza scenariile pentru cerintele specifice. Returneaza lista de dicturi
    cu cheile: cerinta_index, sheet, Scenariu, Obiectiv, Pasi de Test, ..."""
    batch_chars = CLAUDE_BATCH_CHARS
    batches = batch_requirements(reqs, batch_chars)
    prompt = _GEN_PROMPT.format(sheets=", ".join(SHEETS))
    results: list[dict] = []

    for bi, idxs in enumerate(batches, start=1):
        if on_step:
            on_step(f"gen:{bi}/{len(batches)}")
        content = _batch_content(reqs, idxs, batch_chars)
        # Raspunsul unui lot are ~8.000 de tokeni; restul limitei e pentru gandire.
        raw = await _call_claude(prompt, content, 32_000)
        # Doar un raspuns ilizibil se iarta (lotul primeste scenariul minimal).
        # O eroare de API — cheie, credit, refuz — urca: altfel generarea s-ar
        # termina „cu succes", cu zero scenarii specifice si fara nicio explicatie.
        try:
            items = parse_json_block(raw).get("scenarii", [])
        except (ValueError, AttributeError):
            logger.warning("scenarii: lotul %s/%s nu a intors JSON valid", bi, len(batches))
            items = []
        valid_idx = set(idxs)
        for it in items:
            ci = it.get("cerinta_index")
            if not isinstance(ci, int) or ci not in valid_idx:
                continue
            results.append(it)
        # cerintele fara niciun scenariu generat primesc un scenariu minimal
        covered = {it.get("cerinta_index") for it in items}
        for i in idxs:
            if i not in covered:
                r = reqs[i]
                results.append({
                    "cerinta_index": i, "sheet": _fallback_sheet(r),
                    "Scenariu": f"Verificare cerinta specifica: {r.title}",
                    "Obiectiv": f"Verifica implementarea cerintei '{r.title}' conform specificatiei.",
                    "Pasi de Test": "1. Configurare conform cerintei\n2. Executie flux descris in specificatie\n3. Validare rezultat",
                    "Rezultat Asteptat": "Comportament conform cerintei din specificatie.",
                    "Tip Test": "Functional - Pozitiv", "Prioritate": "High",
                    "_fallback": True,
                })
    return results


def _fallback_sheet(r: SpecificRequirement) -> str:
    key = r.module_h2.strip().lower()
    for frag, sheet in _MODULE_SHEET_FALLBACK.items():
        if frag in key:
            return sheet
    return "⚙️ Configurare"


def resolve_sheet(name: str, req: SpecificRequirement) -> str:
    return name if name in SHEETS else _fallback_sheet(req)


async def generate_dependencies(
    core_index: list[tuple[str, str, str]],   # (ID, sheet, titlu)
    new_index: list[tuple[str, str, str]],
    on_step=None,
) -> dict[str, list[str]]:
    """Un singur apel: dependentele scenariilor noi catre scenariile existente."""
    if not new_index:
        return {}
    if on_step:
        on_step("deps")

    def fmt(rows):
        return "\n".join(f"{i} | {sh} | {t[:60]}" for i, sh, t in rows)

    content = (
        "=== INDEX SCENARII EXISTENTE (standard) ===\n" + fmt(core_index)
        + "\n\n=== SCENARII NOI (cerinte specifice) ===\n" + fmt(new_index)
    )
    # Dependentele sunt o imbogatire: scenariile generate deja nu se pierd daca
    # pasul asta pica — documentul iese fara ele, iar motivul ramane in jurnal.
    try:
        raw = await _call_claude(_DEPS_PROMPT, content, 16_000)
        deps = parse_json_block(raw).get("dependente", {})
    except Exception as e:
        logger.warning("scenarii: dependentele nu au putut fi stabilite: %s", e)
        return {}

    valid = {i for i, _, _ in core_index} | {i for i, _, _ in new_index}
    out: dict[str, list[str]] = {}
    for sid, dlist in deps.items():
        if sid in valid and isinstance(dlist, list):
            clean = [d for d in dlist if isinstance(d, str) and d in valid and d != sid][:3]
            if clean:
                out[sid] = clean
    return out
