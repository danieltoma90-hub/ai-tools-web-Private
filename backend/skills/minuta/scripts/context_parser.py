# -*- coding: utf-8 -*-
"""Citeste fisierul de Context Proiect (.docx) completat de utilizator.

Rezultatul e un text compact, gata de pus in prompt. Randurile necompletate si
instructiunile din template (paragrafele italice) sunt ignorate — altfel am
trimite modelului un formular gol si l-am invata sa inventeze.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip().lower()


# titlul capitolului (normalizat, fara numar) -> cheia interna
_SECTIONS = {
    "proiect si client": "proiect",
    "participanti recurenti": "participanti",
    "glosar si terminologie": "glosar",
    "scopul proiectului si module in lucru": "scop",
    "decizii luate anterior": "decizii",
    "actiuni deschise din sedintele anterioare": "actiuni_deschise",
    "preferinte de redactare": "preferinte",
}


@dataclass
class ProjectContext:
    proiect: dict[str, str] = field(default_factory=dict)
    participanti: list[dict[str, str]] = field(default_factory=list)
    glosar: list[dict[str, str]] = field(default_factory=list)
    scop: list[str] = field(default_factory=list)
    decizii: list[dict[str, str]] = field(default_factory=list)
    actiuni_deschise: list[dict[str, str]] = field(default_factory=list)
    preferinte: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any([
            self.proiect, self.participanti, self.glosar,
            self.scop, self.decizii, self.actiuni_deschise, self.preferinte,
        ])

    def as_prompt_block(self) -> str:
        """Contextul, in forma in care intra in prompt. Gol daca nu s-a completat nimic."""
        if self.is_empty():
            return ""
        out: list[str] = ["=== CONTEXT PROIECT (informatii furnizate de utilizator) ==="]

        if self.proiect:
            out.append("\n[Proiect]")
            out += [f"- {k}: {v}" for k, v in self.proiect.items()]
        if self.participanti:
            out.append("\n[Participanti recurenti — foloseste aceste nume si roluri]")
            for p in self.participanti:
                line = p.get("nume", "")
                if p.get("rol"):
                    line += f" — {p['rol']}"
                if p.get("organizatie"):
                    line += f" ({p['organizatie']})"
                out.append(f"- {line}")
        if self.glosar:
            out.append("\n[Glosar — transcrierea poate scrie gresit acesti termeni; foloseste forma corecta]")
            out += [f"- {g['termen']} = {g['sens']}" for g in self.glosar]
        if self.scop:
            out.append("\n[Scop proiect]")
            out += [f"- {s}" for s in self.scop]
        if self.decizii:
            out.append("\n[Decizii deja luate — NU le raporta ca noi]")
            for d in self.decizii:
                prefix = f"{d['data']}: " if d.get("data") else ""
                out.append(f"- {prefix}{d['decizie']}")
        if self.actiuni_deschise:
            out.append("\n[Actiuni deschise anterior — urmareste in transcript daca s-au inchis]")
            for a in self.actiuni_deschise:
                line = f"{a.get('responsabil', 'TBD')}: {a.get('actiune', '')}"
                if a.get("termen"):
                    line += f" (termen {a['termen']})"
                out.append(f"- {line}")
        if self.preferinte:
            out.append("\n[Preferinte de redactare — respecta-le]")
            out += [f"- {p}" for p in self.preferinte]

        out.append("=== SFARSIT CONTEXT ===")
        return "\n".join(out)


def _iter_blocks(doc: Document):
    """Paragrafele si tabelele in ordinea reala din document."""
    from docx.oxml.ns import qn
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _is_hint(p: Paragraph) -> bool:
    """Instructiunile din template sunt italice — nu sunt continut."""
    runs = [r for r in p.runs if r.text.strip()]
    return bool(runs) and all(r.italic for r in runs)


def _is_label(text: str) -> bool:
    """Etichetele structurale din template („Module / arii în scop:") nu sunt
    raspunsuri ale utilizatorului — altfel un formular necompletat ar ajunge in
    prompt ca si cum ar contine informatie."""
    return text.endswith(":") and len(text) < 60


def _rows(table: Table) -> list[list[str]]:
    """Randurile completate, fara antet."""
    out = []
    for row in list(table.rows)[1:]:
        cells = [c.text.strip() for c in row.cells]
        if any(cells):
            out.append(cells)
    return out


def parse_context(docx_path: Path) -> ProjectContext:
    doc = Document(str(docx_path))
    ctx = ProjectContext()
    current: str | None = None

    for block in _iter_blocks(doc):
        if isinstance(block, Paragraph):
            style = block.style.name if block.style else ""
            text = block.text.strip()
            if not text:
                continue
            if style.startswith("Heading") or style == "Title":
                key = _norm(re.sub(r"^\s*\d+[.)]?\s*", "", text))
                current = _SECTIONS.get(key)
                continue
            if _is_hint(block) or _is_label(text):
                continue
            # text liber in sectiunile care il accepta
            if current == "scop":
                ctx.scop.append(text)
            elif current == "preferinte":
                ctx.preferinte.append(text)

        elif isinstance(block, Table):
            rows = _rows(block)
            if not rows:
                continue
            if current == "proiect":
                for r in rows:
                    if len(r) >= 2 and r[0] and r[1]:
                        ctx.proiect[r[0]] = r[1]
            elif current == "participanti":
                for r in rows:
                    if r[0]:
                        ctx.participanti.append({
                            "nume": r[0],
                            "rol": r[1] if len(r) > 1 else "",
                            "organizatie": r[2] if len(r) > 2 else "",
                        })
            elif current == "glosar":
                for r in rows:
                    if len(r) >= 2 and r[0] and r[1]:
                        ctx.glosar.append({"termen": r[0], "sens": r[1]})
            elif current == "decizii":
                for r in rows:
                    decizie = r[1] if len(r) > 1 else ""
                    if decizie:
                        ctx.decizii.append({"data": r[0], "decizie": decizie})
            elif current == "actiuni_deschise":
                for r in rows:
                    actiune = r[1] if len(r) > 1 else ""
                    if actiune:
                        ctx.actiuni_deschise.append({
                            "responsabil": r[0],
                            "actiune": actiune,
                            "termen": r[2] if len(r) > 2 else "",
                        })

    return ctx
