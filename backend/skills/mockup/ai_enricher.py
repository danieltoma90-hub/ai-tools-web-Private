"""Imbogatire AI a documentatiei de ecran: overview + descrieri mai bune.

Un singur apel LLM per mockup. Orice esec => se pastreaza descrierile
deterministe (apelantul decide fallback-ul).
"""
import llm_client
from .parser import ScreenSpec

OUT_TOKENS = 3000
CALL_OVERHEAD_TOKENS = 900

_SYSTEM = """Ești analist de business senior pentru Charisma ERP. Primești structura unui ecran \
(filtre, butoane, coloane, observații) și descrierile existente ale câmpurilor.
1. Scrie secțiunea "Prezentare generală": scopul ecranului (2-3 fraze), fluxul de utilizare \
(3-6 pași scurți) și legăturile dintre câmpuri (dacă există).
2. Îmbunătățește descrierile câmpurilor: mai clare, cu context business și tehnic, în română cu diacritice. \
Păstrează faptele din descrierile existente — NU inventa reguli noi.
Răspunde DOAR cu JSON valid:
{"prezentare_generala": {"scop": "...", "flux": ["...", "..."], "legaturi": "..."}, \
"descrieri_filtre": {"<câmp>": "..."}, "descrieri_butoane": {"<buton>": "..."}, \
"descrieri_coloane": {"<coloană>": "..."}}"""


def _spec_digest(spec: ScreenSpec, descriptions: dict) -> str:
    lines = [f"ECRAN: {spec.screen_title}", ""]
    for sec in spec.sections:
        lines.append(f"SECȚIUNE: {sec.title}")
        if sec.filter_fields:
            lines.append("FILTRE:")
            for f in sec.filter_fields:
                desc = descriptions.get("descrieri_filtre", {}).get(f.label, "")
                oblig = " (obligatoriu)" if f.mandatory else ""
                lines.append(f"- {f.label}{oblig}: {desc}")
        if sec.buttons:
            lines.append("BUTOANE:")
            for b in sec.buttons:
                desc = descriptions.get("descrieri_butoane", {}).get(b.label, "")
                lines.append(f"- {b.label} [{b.group}]: {desc}")
        if sec.columns:
            lines.append("COLOANE GRID:")
            for c in sec.columns:
                desc = descriptions.get("descrieri_coloane", {}).get(c.name, "")
                lines.append(f"- {c.name}: {desc}")
        lines.append("")
    if spec.observatii:
        lines.append("OBSERVAȚII DIN SPEC:")
        lines.extend(f"- {o}" for o in spec.observatii[:30])
    if descriptions.get("descriere_generala"):
        lines.append(f"DESCRIERE EXISTENTĂ: {descriptions['descriere_generala']}")
    return "\n".join(lines)


def estimate_enrich_tokens(spec: ScreenSpec, descriptions: dict) -> int:
    return (
        llm_client.estimate_tokens(_spec_digest(spec, descriptions))
        + CALL_OVERHEAD_TOKENS
        + OUT_TOKENS
    )


async def enrich(spec: ScreenSpec, descriptions: dict) -> dict:
    """Returneaza un dict descriptions nou, cu prezentare_generala + descrieri imbunatatite."""
    content = await llm_client.chat(_SYSTEM, _spec_digest(spec, descriptions), max_tokens=OUT_TOKENS)
    data = llm_client.parse_json(content)

    merged = dict(descriptions)
    pg = data.get("prezentare_generala")
    if isinstance(pg, dict):
        merged["prezentare_generala"] = {
            "scop": str(pg.get("scop", "")),
            "flux": [str(x) for x in pg.get("flux", []) if str(x).strip()],
            "legaturi": str(pg.get("legaturi", "")),
        }
    for key in ("descrieri_filtre", "descrieri_butoane", "descrieri_coloane"):
        overrides = data.get(key)
        if isinstance(overrides, dict):
            base = dict(merged.get(key, {}))
            for label, text in overrides.items():
                # doar campuri care exista deja (AI nu poate adauga campuri noi)
                if label in base and isinstance(text, str) and text.strip():
                    base[label] = text.strip()
            merged[key] = base
    return merged
