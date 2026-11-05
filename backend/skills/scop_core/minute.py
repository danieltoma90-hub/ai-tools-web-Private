# -*- coding: utf-8 -*-
"""Citirea minutelor ca puncte discutate, pentru alimentarea documentelor de scop.

O minută F.05 există deja în două forme: JSON-ul din care `build_minuta.py` o construiește și
documentul Word rezultat. JSON-ul e sursa bună — are secțiunile, bulinele și pașii următori deja
separați, deci nu e nevoie nici de model, nici de ghicit structura din text. Documentul rămâne
varianta de rezervă, pentru minutele primite de la alții.

Ce iese de aici e o listă plată de `Punct`: un enunț discutat, cu secțiunea din care provine și cu
marcajele redactorului păstrate intacte. Marcajele contează: `[DEDUCȚIE]` și `[CLARIFICARE NEEDED]`
spun că enunțul **nu** e confirmat de client, iar un enunț neconfirmat nu intră în scop ca
promisiune fermă — vezi regula din memoria „Promisiunile din ședințe intră în scop".

Nimic de aici nu rescrie textul minutei. Un punct e un extras, cuvânt cu cuvânt; singura curățare e
scoaterea marcajelor de îngroșare (`**...**`), care sunt formatare, nu conținut.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# Marcajele pe care redactorul minutei le lasă în text. Le recunoaștem ca să putem separa ce s-a
# spus de ce a dedus redactorul — distincția se pierde dacă textul e doar citit ca text.
TIPAR_MARCAJ = re.compile(
    r"\[(DEDUC[ȚT]IE|CLARIFICARE NEEDED|NOTI[ȚT]E|NOTES|TO BE CONFIRMED[^\]]*|DE CONFIRMAT[^\]]*)"
    r"[^\]]*\]",
    re.I,
)
TIPAR_INGROSARE = re.compile(r"\*\*(.+?)\*\*")

# Trei feluri de limbaj, trei steaguri. Niciunul nu decide nimic singur: ridică semnalul, iar
# confruntarea cu documentul spune dacă subiectul chiar mai e acolo.
#
# Tiparele sunt scrise pe felul în care vorbesc minutele noastre, nu pe gramatică generală: la
# TotalSoft decizia de scoatere se notează la participiu („Scos integral", „Scoase rândurile"),
# iar convenția minutei spune explicit că „unde scrie «scos» sau «notat»" e o modificare operată.
TIPAR_EXCLUDERE = re.compile(
    r"(\bscos\b|\bscoas[ăae]\b|\bscoase\b|se scoate|se poate scoate|scoatem|s-a scos"
    r"|de [șs]ters|\b[șs]ters\b|\b[șs]tearsă\b|\bies[e]? din\b|\bce iese\b"
    r"|nu e[  ]?(?:în|in) scop"
    r"|nu este (?:în|in) scop|(?:în|in) afara scopului|nu se ofer|nu mai (?:se )?ofer|renun[țt]"
    r"|se elimin|elimin[ăa]m|se taie|t[ăa]iat|nu face obiectul|se coteaz[ăa] separat"
    r"|se bugeteaz[ăa] separat|analiz[ăa] separat[ăa]|faz[ăa] ulterioar|etap[ăa] ulterioar)",
    re.I,
)
TIPAR_PROMISIUNE = re.compile(
    r"\b(oferim|se ofer[ăa]|putem (?:face|oferi|acoperi)|se poate (?:face|configura|dezvolta)"
    r"|r[ăa]m[âa]ne (?:(?:în|in) (?:scop|ofert[ăa])|integrarea)|intr[ăa] (?:în|in) scop"
    r"|se include|includem|acoperim|vom (?:face|livra|acoperi)|se preia prin)",
    re.I,
)
# Ce rămâne în scop, dar trebuie rescris. Minuta le notează, iar ele sunt exact munca de corelare
# care altfel se descoperă abia la citirea documentului.
TIPAR_MODIFICARE = re.compile(
    r"(de reformulat|trebuie reformulat|de actualizat|trebuie actualizat|de specificat"
    r"|de completat|de detaliat|\bnotat\b|de corelat|trebuie corelat|de verificat)",
    re.I,
)


@dataclass(frozen=True)
class Punct:
    """Un enunț discutat, cu locul din care vine."""

    sursa: str
    sectiune: str
    rubrica: str          # context | discutie | pain | solutie | actiune | risc | concluzie
    text: str
    marcaje: tuple[str, ...] = field(default_factory=tuple)

    @property
    def confirmat(self) -> bool:
        """Fără marcaje de deducție sau de clarificare, enunțul e ce s-a spus în ședință."""
        return not self.marcaje

    @property
    def exclude(self) -> bool:
        return bool(TIPAR_EXCLUDERE.search(self.text))

    @property
    def promite(self) -> bool:
        return bool(TIPAR_PROMISIUNE.search(self.text))

    @property
    def modifica(self) -> bool:
        return bool(TIPAR_MODIFICARE.search(self.text))

    @property
    def semnale(self) -> tuple[str, ...]:
        return tuple(nume for nume, da in (
            ("excludere", self.exclude), ("promisiune", self.promite),
            ("modificare", self.modifica)) if da)


def curata(text: str) -> str:
    """Textul fără marcajele de îngroșare, cu spațiile normalizate. Marcajele redactorului rămân:
    ele spun ceva despre enunț și se pierd dacă le ștergem aici."""
    return " ".join(TIPAR_INGROSARE.sub(r"\1", str(text)).split())


def marcaje(text: str) -> tuple[str, ...]:
    return tuple(sorted({m.group(1).upper() for m in TIPAR_MARCAJ.finditer(text)}))


def fara_marcaje(text: str) -> str:
    """Enunțul fără parantezele redactorului. Textul dinăuntru e comentariu despre enunț —
    „DEDUCȚIE: «wizz RO» = aplicația magazinelor" —, iar dacă rămâne, cuvinte ca „deducție" sau
    „clarificare" ajung să fie căutate în document ca și cum ar fi subiectul discuției."""
    return " ".join(re.sub(r"\[[^\]]*\]", " ", text).split())


def fara_diacritice(s: str) -> str:
    """Documentele de scop se scriu fără diacritice, minutele cu. Comparația se face pe forma
    fără, altfel „trasabilitate" și „trasabilitate" par cuvinte diferite."""
    desc = unicodedata.normalize("NFKD", s)
    return "".join(c for c in desc if not unicodedata.combining(c))


def _punct(sursa, sectiune, rubrica, text) -> Punct | None:
    t = curata(text)
    if len(t) < 15:        # „Da.", „Vezi mai sus" — zgomot de transcriere
        return None
    return Punct(sursa=sursa, sectiune=sectiune, rubrica=rubrica, text=t, marcaje=marcaje(t))


def _din_blocuri_minuta(sursa, titlu, blocuri, rubrica):
    """Blocurile unei minute F.05: `bullets`, `paragraph`, `subheading`, `table`, `table_2col`."""
    sub = titlu
    for b in blocuri or []:
        tip = b.get("type")
        if tip == "subheading":
            sub = curata(b.get("text", "")) or titlu
        elif tip == "bullets":
            for it in b.get("items", []):
                p = _punct(sursa, sub, rubrica, it)
                if p:
                    yield p
        elif tip in ("paragraph", "text"):
            p = _punct(sursa, sub, rubrica, b.get("text", ""))
            if p:
                yield p
        elif tip in ("table", "table_2col"):
            for rand in b.get("rows", []):
                p = _punct(sursa, sub, rubrica, " — ".join(str(c) for c in rand))
                if p:
                    yield p


def din_minuta_json(cale: Path) -> list[Punct]:
    d = json.loads(Path(cale).read_text(encoding="utf-8"))
    sursa = Path(cale).stem
    puncte: list[Punct] = []
    for bloc in d.get("context_si_scop", []):
        puncte.extend(_din_blocuri_minuta(sursa, "Context și scop", [bloc], "context"))
    for s in d.get("sectiuni", []):
        puncte.extend(
            _din_blocuri_minuta(sursa, curata(s.get("titlu", "")), s.get("blocuri"), "discutie"))
    for pas in d.get("pasi_urmatori", []):
        p = _punct(sursa, "Pași următori", "actiune",
                   f"{pas.get('responsabil', '')}: {pas.get('actiune', '')}")
        if p:
            puncte.append(p)
    return puncte


def _din_blocuri_fitgap(sursa, titlu, blocuri, rubrica):
    """Blocurile unui FitGap: `ul` (listă), `p` (paragraf), `h` (subtitlu)."""
    sub = titlu
    for b in blocuri or []:
        if "h" in b:
            sub = curata(b["h"]) or titlu
        for it in b.get("ul", []):
            p = _punct(sursa, sub, rubrica, it)
            if p:
                yield p
        if "p" in b:
            p = _punct(sursa, sub, rubrica, b["p"])
            if p:
                yield p


def din_fitgap_json(cale: Path) -> list[Punct]:
    d = json.loads(Path(cale).read_text(encoding="utf-8"))
    sursa = Path(cale).stem
    puncte: list[Punct] = []
    for rez in d.get("executive_summary", []):
        p = _punct(sursa, "Rezumat", "context", rez)
        if p:
            puncte.append(p)
    for t in d.get("topics", []):
        puncte.extend(
            _din_blocuri_fitgap(sursa, curata(t.get("title", "")), t.get("blocks"), "discutie"))
    for t in d.get("pain_points", []):
        puncte.extend(
            _din_blocuri_fitgap(sursa, curata(t.get("title", "")), t.get("blocks"), "pain"))
    sol = d.get("solution", {})
    for g in sol.get("groups", []):
        for it in g.get("items", []):
            p = _punct(sursa, curata(g.get("title", "Soluție")), "solutie", it)
            if p:
                puncte.append(p)
    for cine in ("customer", "team"):
        for it in (d.get("actions", {}) or {}).get(cine, []) or []:
            text = it if isinstance(it, str) else " — ".join(str(x) for x in it)
            p = _punct(sursa, "Acțiuni", "actiune", text)
            if p:
                puncte.append(p)
    for r in d.get("risks", [])[1:]:          # primul rând e antetul tabelului
        p = _punct(sursa, "Riscuri", "risc", " — ".join(str(x) for x in r))
        if p:
            puncte.append(p)
    for c in d.get("conclusion", []):
        p = _punct(sursa, "Concluzii", "concluzie", c)
        if p:
            puncte.append(p)
    return puncte


def din_docx(cale: Path) -> list[Punct]:
    """Varianta de rezervă, pentru minutele primite ca document. Titlurile dau secțiunea;
    restul paragrafelor și rândurile de tabel devin puncte."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    doc = Document(str(cale))
    sursa = Path(cale).stem
    sectiune = "(fără titlu)"
    puncte: list[Punct] = []
    for el in doc.element.body.iterchildren():
        if el.tag == W + "p":
            p = Paragraph(el, doc)
            t = p.text.strip()
            if not t:
                continue
            stil = p.style.name if p.style else ""
            if re.match(r"^(Heading \d|Title)$", stil, re.I):
                sectiune = curata(t)
                continue
            pct = _punct(sursa, sectiune, "discutie", t)
            if pct:
                puncte.append(pct)
        elif el.tag == W + "tbl":
            try:
                tb = Table(el, doc)
            except Exception:
                continue
            for rand in tb.rows[1:]:
                pct = _punct(sursa, sectiune, "discutie",
                             " — ".join(c.text.strip() for c in rand.cells))
                if pct:
                    puncte.append(pct)
    return puncte


def citeste(cale: Path | str) -> list[Punct]:
    """Orice formă de minută → puncte. Alegerea se face pe conținut, nu pe nume de fișier:
    aceeași ședință are și un JSON de minută, și unul de FitGap, cu chei diferite."""
    cale = Path(cale)
    if cale.suffix.lower() == ".docx":
        return din_docx(cale)
    if cale.suffix.lower() != ".json":
        raise ValueError(f"nu știu să citesc {cale.suffix!r}; accept .json sau .docx")
    d = json.loads(cale.read_text(encoding="utf-8"))
    if "topics" in d or "pain_points" in d:
        return din_fitgap_json(cale)
    if "sectiuni" in d:
        return din_minuta_json(cale)
    raise ValueError(f"{cale.name}: nici minută (`sectiuni`), nici FitGap (`topics`)")


def citeste_multe(cai) -> list[Punct]:
    puncte: list[Punct] = []
    for c in cai:
        puncte.extend(citeste(c))
    return puncte
