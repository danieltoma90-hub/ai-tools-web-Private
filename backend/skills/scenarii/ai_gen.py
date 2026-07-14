# -*- coding: utf-8 -*-
"""Generarea AI a scenariilor din cerintele specifice + pass-ul de dependente.

Doi provideri:
- "claude": Claude Sonnet (credite API) — loturi mari, rapid
- "groq":   gpt-oss-120b cu fallback llama (gratuit) — loturi mici, 62s intre apeluri
"""
from __future__ import annotations

import asyncio
import json
import os
import re

from .spec_parser import SpecificRequirement

ROMANIAN_CHARS_PER_TOKEN = 2.2

# bugetul de input per lot (chars) — dimensionat dupa provider
CLAUDE_BATCH_CHARS = 30_000
GROQ_BATCH_CHARS = 9_000
GROQ_DELAY_S = 62

CLAUDE_MODEL = os.environ.get("SCENARII_CLAUDE_MODEL", "claude-sonnet-4-6")
GROQ_CHAIN = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"]

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


# ── Provideri ────────────────────────────────────────────────────────────────

async def _call_claude(prompt: str, content: str, max_tokens: int) -> str:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = await client.messages.create(
        model=CLAUDE_MODEL, max_tokens=max_tokens,
        messages=[{"role": "user", "content": f"{prompt}\n\n{content}"}],
    )
    return resp.content[0].text


async def _call_groq(prompt: str, content: str, max_tokens: int, state: dict) -> str:
    from groq import AsyncGroq, RateLimitError
    client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    last_err: Exception | None = None
    for attempt in range(4):
        model = state.get("model", GROQ_CHAIN[0])
        kwargs = {"reasoning_effort": "low"} if model.startswith("openai/") else {}
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"{prompt}\n\n{content}"}],
                max_tokens=max_tokens, temperature=0.1, **kwargs,
            )
            return resp.choices[0].message.content
        except RateLimitError as e:
            last_err = e
            if "per day" in str(e) or "TPD" in str(e):
                idx = GROQ_CHAIN.index(model) if model in GROQ_CHAIN else 0
                if idx + 1 < len(GROQ_CHAIN):
                    state["model"] = GROQ_CHAIN[idx + 1]
                    continue
                raise RuntimeError(
                    "Limita zilnică gratuită Groq epuizată. Reîncercați mâine sau folosiți varianta Claude."
                ) from e
            if attempt < 3:
                await asyncio.sleep(65)
    raise last_err


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
    engine: str,
    on_step=None,
) -> list[dict]:
    """Genereaza scenariile pentru cerintele specifice. Returneaza lista de dicturi
    cu cheile: cerinta_index, sheet, Scenariu, Obiectiv, Pasi de Test, ..."""
    batch_chars = CLAUDE_BATCH_CHARS if engine == "claude" else GROQ_BATCH_CHARS
    batches = batch_requirements(reqs, batch_chars)
    prompt = _GEN_PROMPT.format(sheets=", ".join(SHEETS))
    state: dict = {}
    results: list[dict] = []

    for bi, idxs in enumerate(batches, start=1):
        if on_step:
            on_step(f"gen:{bi}/{len(batches)}")
        if engine == "groq" and bi > 1:
            await asyncio.sleep(GROQ_DELAY_S)
        content = _batch_content(reqs, idxs, batch_chars)
        max_out = 8_000 if engine == "claude" else 2_000
        try:
            if engine == "claude":
                raw = await _call_claude(prompt, content, max_out)
            else:
                raw = await _call_groq(prompt, content, max_out, state)
            data = parse_json_block(raw)
            items = data.get("scenarii", [])
        except Exception:
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
    engine: str,
    on_step=None,
) -> dict[str, list[str]]:
    """Un singur apel: dependentele scenariilor noi catre scenariile existente."""
    if not new_index:
        return {}
    if on_step:
        on_step("deps")
    if engine == "groq":
        await asyncio.sleep(GROQ_DELAY_S)

    def fmt(rows):
        return "\n".join(f"{i} | {sh} | {t[:60]}" for i, sh, t in rows)

    content = (
        "=== INDEX SCENARII EXISTENTE (standard) ===\n" + fmt(core_index)
        + "\n\n=== SCENARII NOI (cerinte specifice) ===\n" + fmt(new_index)
    )
    try:
        if engine == "claude":
            raw = await _call_claude(_DEPS_PROMPT, content, 3_000)
        else:
            raw = await _call_groq(_DEPS_PROMPT, content, 2_000, {})
        data = parse_json_block(raw)
        deps = data.get("dependente", {})
    except Exception:
        return {}

    valid = {i for i, _, _ in core_index} | {i for i, _, _ in new_index}
    out: dict[str, list[str]] = {}
    for sid, dlist in deps.items():
        if sid in valid and isinstance(dlist, list):
            clean = [d for d in dlist if isinstance(d, str) and d in valid and d != sid][:3]
            if clean:
                out[sid] = clean
    return out
