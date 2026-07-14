# -*- coding: utf-8 -*-
"""Pipeline Scenarii de Testare — catalog standard + cerinte specifice client.

Fluxul:
1. Parseaza specificatia clientului (headinguri + sectiunile
   "Cerinte specifice identificate in urma Analizei")
2. Porneste de la catalogul CORE standard (170 scenarii validate);
   scenariile ale caror capitole standard lipsesc din spec sunt EXCLUSE
   si listate in sheet-ul "Excluse vs Standard"
3. AI (Claude Sonnet sau Groq gratuit) genereaza scenarii pentru fiecare
   cerinta specifica — marcate galben, cu codul de trasabilitate
4. Pass de dependente: scenariile noi primesc preconditiile de executie
   (ID-uri din catalog), apoi totul intra in Plan Executie (ordine topologica)
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path

from skills.scenarii import ai_gen
from skills.scenarii.excel_writer import write_scenarii_excel
from skills.scenarii.spec_parser import parse_client_spec, norm_txt

SKILL_DIR = Path(__file__).parent.parent / "skills" / "scenarii"
CATALOG_PATH = SKILL_DIR / "catalog_core.json"

SHEET_PREFIX = {
    "⚙️ Configurare": "CFG", "🏷️ Articole": "ART", "📦 Coduri Bare": "CB",
    "💰 Liste Preturi": "LP", "👥 Parteneri": "PRT", "🛒 Comenzi Achiz.": "CA",
    "📥 Receptie NIR": "NIR", "🧾 Facturi Achiz.": "FA", "📤 Vanzari": "VAN",
    "📊 Stocuri": "ST", "🔄 Transfer & Inventar": "TRI", "🏭 Mijloace Fixe": "MF",
    "💳 Financiar": "FIN", "📚 Contabilitate": "CTB", "🗂️ Import Date": "IMP",
}


def _load_catalog() -> dict:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    # copie de lucru; statusul porneste mereu de la Netestat
    for items in catalog.values():
        for s in items:
            s["Status"] = "Netestat"
            s.setdefault("deps", [])
            s["_specific"] = False
    return catalog


def _is_included(std_ref: str, titles: set[str]) -> bool:
    if not std_ref:
        return True
    last = norm_txt(std_ref.split(" > ")[-1])
    return last in titles


def _apply_exclusions(catalog: dict, titles: set[str]) -> list[tuple[str, dict]]:
    """Scoate din catalog scenariile fara capitol in spec; le returneaza pt. raport.
    Dependentele catre scenariile excluse se elimina din cele ramase."""
    excluded: list[tuple[str, dict]] = []
    for sheet, items in catalog.items():
        keep = []
        for s in items:
            if _is_included(s.get("std_ref", ""), titles):
                keep.append(s)
            else:
                excluded.append((sheet, s))
        catalog[sheet] = keep
    excluded_ids = {s["ID"] for _, s in excluded}
    for items in catalog.values():
        for s in items:
            s["deps"] = [d for d in s.get("deps", []) if d not in excluded_ids]
    return excluded


def estimate_scenarii_job(docx_path: Path) -> dict:
    """Pre-check: cerinte specifice gasite, apeluri si durate pe ambele variante."""
    spec = parse_client_spec(docx_path)
    total_chars = sum(len(r.text) + len(r.title) for r in spec.requirements)

    claude_batches = max(1, len(ai_gen.batch_requirements(spec.requirements, ai_gen.CLAUDE_BATCH_CHARS))) if spec.requirements else 0
    groq_batches = max(1, len(ai_gen.batch_requirements(spec.requirements, ai_gen.GROQ_BATCH_CHARS))) if spec.requirements else 0

    est_tokens = round(total_chars / ai_gen.ROMANIAN_CHARS_PER_TOKEN) + (groq_batches + 1) * 3_000
    return {
        "requirements": len(spec.requirements),
        "est_tokens": est_tokens,
        "calls": claude_batches + 1,
        "modules": len({r.module_h2 for r in spec.requirements}) or 1,
        "est_minutes": max(1, math.ceil((claude_batches + 1) * 25 / 60)),
        "est_minutes_free": max(1, groq_batches + 2),
        "fits_budget": True,
    }


def _next_cs_id(items: list[dict], prefix: str) -> str:
    mx = 0
    for s in items:
        m = re.match(rf"{prefix}-CS-(\d+)$", s.get("ID", ""))
        if m:
            mx = max(mx, int(m.group(1)))
    return f"{prefix}-CS-{mx + 1:02d}"


async def run_scenarii_pipeline(
    docx_path: Path,
    engine: str = "claude",   # "claude" | "groq"
    on_step=None,
) -> tuple[Path, dict]:
    """Returneaza (xlsx_path, sumar)."""
    if on_step:
        on_step("parsing")
    spec = parse_client_spec(docx_path)
    catalog = _load_catalog()

    excluded = _apply_exclusions(catalog, spec.titles)

    # generare scenarii pentru cerintele specifice
    generated = []
    if spec.requirements:
        generated = await ai_gen.generate_specific_scenarios(
            spec.requirements, engine=engine, on_step=on_step)

    new_index: list[tuple[str, str, str]] = []
    for it in generated:
        req = spec.requirements[it["cerinta_index"]]
        sheet = ai_gen.resolve_sheet(it.get("sheet", ""), req)
        catalog.setdefault(sheet, [])
        sid = _next_cs_id(catalog[sheet], SHEET_PREFIX.get(sheet, "GEN"))
        obs = f"Cerinta specifica {req.code or req.item_no}"
        if it.get("_fallback"):
            obs += " (generat fara AI — apelul a esuat)"
        scen = {
            "ID": sid,
            "Modul": req.module_h2,
            "Capitol": f"{req.module_no} {req.module_h2}".strip(),
            "Subcapitol": f"{req.item_no} {req.title}".strip(),
            "Scenariu": it.get("Scenariu", ""),
            "Obiectiv": it.get("Obiectiv", ""),
            "Pasi de Test": it.get("Pasi de Test", ""),
            "Rezultat Asteptat": it.get("Rezultat Asteptat", ""),
            "Tip Test": it.get("Tip Test", "Functional - Pozitiv"),
            "Prioritate": it.get("Prioritate", "High"),
            "Status": "Netestat",
            "Observatii": obs,
            "deps": [], "std_ref": "", "_specific": True,
        }
        catalog[sheet].append(scen)
        new_index.append((sid, sheet, scen["Scenariu"]))

    # dependentele scenariilor noi (un singur apel)
    if new_index:
        core_index = [
            (s["ID"], sheet, s.get("Scenariu", ""))
            for sheet, items in catalog.items() for s in items if not s["_specific"]
        ]
        deps_map = await ai_gen.generate_dependencies(
            core_index, new_index, engine=engine, on_step=on_step)
        by_id = {s["ID"]: s for items in catalog.values() for s in items}
        for sid, dlist in deps_map.items():
            if sid in by_id:
                by_id[sid]["deps"] = dlist

    if on_step:
        on_step("building")

    fd, tmp_name = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    fd_path = Path(tmp_name)
    write_scenarii_excel(catalog, fd_path, excluded=excluded)

    summary = {
        "core_count": sum(1 for items in catalog.values() for s in items if not s["_specific"]),
        "specific_count": len(new_index),
        "excluded_count": len(excluded),
        "requirements": len(spec.requirements),
    }
    return fd_path, summary
