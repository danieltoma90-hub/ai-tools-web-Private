# -*- coding: utf-8 -*-
"""Conținutul pe capitolele Fit-Gap → secțiunile minutei F.05 (citite de build_minuta).

Capitolele vin din exemplul VEDAS_Charisma_Meeting_Summary_FitGap: rezumat executiv, subiecte cheie,
probleme identificate, direcții de soluție, acțiuni de urmărire, riscuri, concluzie. Formatul rămâne
F.05 TotalSoft — se schimbă doar capitolele. Portat din
AI_Claude/skills/minuta-client-totalsoft/scripts/fitgap_to_minuta.py.
"""
from __future__ import annotations

import re

LABELS = {
    "ro": {
        "objective": "Obiectiv", "executive": "Rezumat executiv", "topics": "Subiecte cheie discutate",
        "pain_item": "Problema critică", "pain": "Probleme identificate", "solution": "Direcții de soluție propuse",
        "customer": "Acțiunile clientului", "team": "Acțiunile echipei de implementare",
        "responsible": "Responsabil", "actions": "Acțiuni de urmărire",
        "risks": "Evaluarea riscurilor de implementare", "conclusion": "Concluzie finală",
        "recommendation": "Recomandare pentru ofertă",
    },
    "en": {
        "objective": "Objective", "executive": "Executive Summary", "topics": "Key Topics Discussed",
        "pain_item": "Critical Pain Point", "pain": "Pain Points Identified",
        "solution": "Proposed Solution Directions", "customer": "Customer Actions",
        "team": "Implementation Team Actions", "responsible": "Responsible", "actions": "Follow-Up Actions",
        "risks": "Implementation Risk Assessment", "conclusion": "Final Conclusion",
        "recommendation": "Recommendation for the proposal",
    },
}


def _title(t) -> str:
    """Titlul fără numărul pus de model — numerotarea o face build_minuta."""
    return re.sub(r"^\s*\d+[.)]\s*", "", str(t or "")).strip()


def _blocks(blocks) -> list[dict]:
    out = []
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        if b.get("p"):
            out.append({"type": "paragraph", "text": str(b["p"])})
        elif b.get("ul"):
            out.append({"type": "bullets", "items": [str(x) for x in b["ul"] if str(x).strip()]})
        elif b.get("h"):
            out.append({"type": "subheading", "text": str(b["h"])})
        elif b.get("quote"):
            out.append({"type": "paragraph", "text": str(b["quote"])})
    return out


def fitgap_sections(fg: dict, lang: str = "ro", legend: str | None = None) -> list[dict]:
    """Secțiunile F.05 pentru conținutul Fit-Gap. `legend` = legenda marcajelor, pusă la finalul rezumatului."""
    if not isinstance(fg, dict) or not (fg.get("executive_summary") or fg.get("topics")):
        raise ValueError("Răspunsul Fit-Gap nu conține rezumatul și nici subiectele ședinței")
    L = LABELS[lang]
    sections: list[dict] = []

    exe = [{"type": "paragraph", "text": str(p)} for p in fg.get("executive_summary") or [] if str(p).strip()]
    objective = fg.get("objective") or dict(fg.get("meeting_info") or []).get("Objective")
    if objective:
        exe.insert(0, {"type": "paragraph", "text": f"**{L['objective']}:** {objective}"})
    if legend:
        exe.append({"type": "paragraph", "text": legend})
    sections.append({"titlu": L["executive"], "blocuri": exe})

    topics = []
    for t in fg.get("topics") or []:
        topics.append({"type": "subheading", "text": _title(t.get("title"))})
        topics += _blocks(t.get("blocks"))
    if topics:
        sections.append({"titlu": L["topics"], "blocuri": topics})

    pain = []
    for i, pp in enumerate(fg.get("pain_points") or [], 1):
        pain.append({"type": "subheading", "text": f"{L['pain_item']} {i} – {_title(pp.get('title'))}"})
        pain += _blocks(pp.get("blocks"))
    if pain:
        sections.append({"titlu": L["pain"], "blocuri": pain})

    sol = fg.get("solution") or {}
    sol_blocks = [{"type": "paragraph", "text": str(sol["intro"])}] if sol.get("intro") else []
    for g in sol.get("groups") or []:
        sol_blocks.append({"type": "subheading", "text": _title(g.get("title"))})
        sol_blocks.append({"type": "bullets", "items": [str(x) for x in g.get("items") or []]})
    if sol_blocks:
        sections.append({"titlu": L["solution"], "blocuri": sol_blocks})

    actions = []
    for key in ("customer", "team"):
        items = (fg.get("actions") or {}).get(key) or []
        if not items:
            continue
        actions.append({"type": "subheading", "text": L[key]})
        for i, a in enumerate(items, 1):
            actions.append({"type": "paragraph", "text": f"**{i}. {_title(a.get('title'))}**"})
            if a.get("items"):
                actions.append({"type": "bullets", "items": [str(x) for x in a["items"]]})
            if a.get("responsible"):
                actions.append({"type": "paragraph", "text": f"{L['responsible']}: {a['responsible']}"})
    if actions:
        sections.append({"titlu": L["actions"], "blocuri": actions})

    risks = [r for r in fg.get("risks") or [] if isinstance(r, list) and len(r) >= 2]
    if len(risks) >= 2:
        sections.append({"titlu": L["risks"], "blocuri": [
            {"type": "table_2col", "header": [str(x) for x in risks[0][:2]],
             "rows": [[str(x) for x in r[:2]] for r in risks[1:]]}]})

    concl = [{"type": "paragraph", "text": str(p)} for p in fg.get("conclusion") or [] if str(p).strip()]
    if fg.get("recommendation"):
        concl.append({"type": "paragraph", "text": f"**{L['recommendation']}:** {fg['recommendation']}"})
    if concl:
        sections.append({"titlu": L["conclusion"], "blocuri": concl})
    return sections
