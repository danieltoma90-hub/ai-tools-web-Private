# -*- coding: utf-8 -*-
"""Regulile de redactare adăugate după prompturile de extragere, după opțiunile alese în pagină.

Metoda vine din minutele făcute pentru VEDAŞ (AI_Claude/skills/minuta-client-totalsoft): nimic peste surse,
tot ce e tangibil, pasajele deformate nu se reconstituie, nume cu diacritice, fără englezisme inutile;
opțional marcajele [DEDUCȚIE] / [COMPLETARE] / [CLARIFICARE NEEDED], detaliul complet și limba engleză.
"""
from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
STRUCTURI = ("standard", "fitgap")
DETALII = ("standard", "complet")


def build_rules(marcaje: bool = False, limba: str = "ro", detaliu: str = "standard",
                notite: bool = False, inregistrari: int = 1) -> str:
    """Regulile date modelului după promptul de extragere.

    notite: există notițele echipei din ședință — sursă alături de transcriere, cu marcajul lor
    când se cer marcaje. inregistrari: câte înregistrări ale aceleiași zile reunește transcrierea.
    """
    files = ["reguli_redactare.md"]
    if inregistrari > 1:
        files.append("reguli_inregistrari.md")
    if notite:
        files.append("reguli_notite.md")
    if marcaje:
        files.append("reguli_marcaje.md")
        if notite:
            files.append("reguli_notite_marcaje.md")
    if detaliu == "complet":
        files.append("detaliu_complet.md")
    if limba == "en":
        files.append("limba_en.md")
    return "\n\n".join((PROMPTS_DIR / f).read_text(encoding="utf-8").strip() for f in files)


def with_legend(context_si_scop, legend: str) -> list[dict]:
    """„Context și scop” cu legenda marcajelor la final: ca punct în lista existentă, altfel ca paragraf."""
    blocks = [b for b in (context_si_scop or []) if isinstance(b, dict)]
    if blocks and blocks[-1].get("type") == "bullets":
        blocks[-1] = {**blocks[-1], "items": list(blocks[-1].get("items", [])) + [legend]}
    else:
        blocks.append({"type": "paragraph", "text": legend})
    return blocks
