# -*- coding: utf-8 -*-
"""Confruntarea punctelor dintr-o minută cu un document de scop.

Întrebarea la care răspunde: **ce s-a discutat și nu se regăsește în document, și ce e în document
deși ședința a cerut scoaterea.** Exact munca făcută de mână la Teldo v6 → v7, unde o rundă de
ștergeri a lăsat în urmă trimiteri în gol, coduri orfane și capitole care ofereau mai departe ce
tocmai se scosese.

Nu e o potrivire de text și nu folosește asemănare generală între fraze — aceea dă zgomot pe un
document de 40 de pagini. Lucrează pe **termeni de subiect**: codurile de flux (MG3, CIRA1), cuvintele
din catalogul Charisma și cuvintele rare din document. „Sistem" apare peste tot și nu spune nimic
despre ce discută un punct; „WMS" apare în trei locuri și spune totul.

Verdictul nu e o decizie, e o listă de verificat. Un punct marcat `[DEDUCȚIE]` sau
`[CLARIFICARE NEEDED]` nu devine niciodată „de adăugat": el trece la **de confirmat**, fiindcă
scopul nu promite ce nu s-a confirmat.
"""
from __future__ import annotations

import collections
import re
from dataclasses import dataclass
from pathlib import Path

from .minute import Punct, fara_diacritice, fara_marcaje

TIPAR_COD = re.compile(r"\b([A-Z]{1,4})(\d{1,2})\b")
TIPAR_CUVANT = re.compile(r"[a-z0-9]+")

# Cuvintele de legătură și cele de umplutură din limbajul de ofertă. Nu pretind o listă completă:
# filtrul care contează e raritatea în document, calculată mai jos. Asta scoate doar gunoiul
# evident, ca să nu ajungă în raport ca „termen de subiect".
GOALE = {
    "acest", "acesta", "aceasta", "acestea", "acestui", "aceste", "acelasi", "aceeasi",
    "altul", "alta", "alte", "altele", "atunci", "cand", "care", "care", "catre", "ceea",
    "cele", "celor", "cest", "chiar", "cum", "cumva", "daca", "dar", "decat", "deci",
    "despre", "din", "dintre", "doar", "dupa", "este", "face", "fara", "fel", "fie",
    "fiecare", "fiind", "intre", "inca", "insa", "mai", "mult", "multe", "nici", "numai",
    "orice", "pana", "pentru", "poate", "prin", "printr", "sau", "sunt", "toate", "tot",
    "unde", "unei", "unor", "deja", "foarte", "trebuie", "spus", "discutie", "discutat",
    "sedinta", "minuta", "client", "clientul", "clientului", "echipa", "totalsoft",
    "charisma", "document", "documentul", "documentului", "scop", "scopul", "scopului",
    "varianta", "versiune", "capitol", "capitolul", "sectiune", "sectiunea", "flux",
    "fluxuri", "fluxul", "modul", "modulul", "sistem", "sistemul", "solutie", "solutia",
    "oferta", "oferit", "ofertat", "efort", "efortul", "proiect", "proiectul", "zile",
    # vocabularul marcajelor de redactare — comentariu despre enunț, nu subiectul lui
    "deductie", "clarificare", "needed", "notite", "notes", "confirmat", "confirmare",
}


def _tokenuri(text: str) -> list[str]:
    return TIPAR_CUVANT.findall(fara_diacritice(text).lower())


# Un document de scop vorbește despre ce NU oferă la fel de mult ca despre ce oferă: capitolul
# „Arii în afara scopului" și rândurile „Neinclus" sunt exact locul unde un subiect scos trebuie
# să apară. Fără distincția asta, confruntarea raportează „încă e în document" tocmai pentru că
# documentul spune corect că nu se oferă.
TIPAR_BUCATA_EXCLUSA = re.compile(
    r"(nu face obiectul|neinclus|nu este inclus|nu sunt incluse|in afara scopului"
    r"|se coteaza distinct|se coteaza separat|se bugeteaza (?:distinct|separat)"
    r"|faza ulterioara|etapa ulterioara|nu fac obiectul)",
    re.I,
)
TIPAR_TITLU_EXCLUS = re.compile(r"(arii in afara|elemente acoperite partial|in afara scopului)",
                                re.I)


@dataclass
class Bucata:
    """O bucată de document: un paragraf sau un rând de tabel, cu titlul sub care stă."""

    titlu: str
    text: str
    tokenuri: frozenset[str]
    coduri: frozenset[str]
    exclusa: bool = False


class Document:
    """Documentul de scop, pregătit pentru întrebarea „unde apare termenul ăsta?"."""

    def __init__(self, bucati: list[Bucata]):
        self.bucati = bucati
        self.df: collections.Counter[str] = collections.Counter()
        for b in bucati:
            self.df.update(b.tokenuri)
        self.coduri = {c for b in bucati for c in b.coduri}
        self.n = max(1, len(bucati))

    @classmethod
    def citeste(cls, cale: Path | str) -> Document:
        from docx import Document as Docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        doc = Docx(str(cale))
        titlu = ""
        in_cuprins = False
        bucati: list[Bucata] = []

        def adauga(text):
            t = " ".join(text.split())
            if len(t) < 10:
                return
            fara = fara_diacritice(t)
            bucati.append(Bucata(
                titlu, t, frozenset(_tokenuri(t)),
                frozenset(m.group(0) for m in TIPAR_COD.finditer(t)),
                exclusa=bool(TIPAR_BUCATA_EXCLUSA.search(fara)
                             or TIPAR_TITLU_EXCLUS.search(fara_diacritice(titlu)))))

        for el in doc.element.body.iterchildren():
            if el.tag == W + "p":
                p = Paragraph(el, doc)
                t = p.text.strip()
                stil = p.style.name if p.style else ""
                if stil.startswith("Heading"):
                    in_cuprins = t.lower().startswith("cuprins")
                    if not in_cuprins and t:
                        titlu = t
                    continue
                if in_cuprins or stil.lower().startswith("toc"):
                    continue
                adauga(t)
            elif el.tag == W + "tbl" and not in_cuprins:
                try:
                    tb = Table(el, doc)
                except Exception:
                    continue
                for rand in tb.rows:
                    adauga(" | ".join(c.text.strip() for c in rand.cells))
        return cls(bucati)

    def rar(self, token: str, prag: float = 0.12) -> bool:
        """Un termen e discriminant dacă apare în puține bucăți. Pragul e pe document, nu pe o
        listă fixă: ce e generic într-un scop de producție („lot") e specific în altul."""
        return 0 < self.df[token] <= max(2, int(self.n * prag))

    def cauta(self, termeni: set[str]) -> tuple[set[str], list[Bucata], int]:
        """Termenii găsiți, bucățile cele mai relevante și câți termeni adună cea mai bună bucată
        **care oferă ceva**.

        Ultimul număr e cel care decide dacă subiectul chiar e în document: termenii împrăștiați
        prin 600 de bucăți nu înseamnă nimic — „comanda" într-un capitol și „factura" în altul nu
        fac un flux de comandă-factură. Contează câți se întâlnesc în aceeași bucată, iar bucățile
        de excludere nu intră la socoteală: acolo subiectul apare tocmai ca să fie scos."""
        gasiti = {t for t in termeni if self.df.get(t, 0) > 0}
        if not gasiti:
            return set(), [], 0
        scor = sorted(((len(b.tokenuri & gasiti), b) for b in self.bucati if b.tokenuri & gasiti),
                      key=lambda x: -x[0])
        oferite = [s for s in scor if not s[1].exclusa]
        return gasiti, [b for _, b in scor[:3]], (oferite[0][0] if oferite else 0)


def lexicon_charisma() -> set[str]:
    """Cuvintele din catalogul CORE: denumirile de flux și titlurile de secțiune. Un punct care
    le atinge discută sigur despre scop, nu despre buget sau despre calendar."""
    from .charisma_core import SECTIUNI
    cuvinte: set[str] = set()
    for s in SECTIUNI:
        for sursa in [s.titlu] + [f.flux for f in s.fluxuri]:
            cuvinte.update(t for t in _tokenuri(sursa) if len(t) > 4 and t not in GOALE)
    return cuvinte


@dataclass
class Rezultat:
    punct: Punct
    verdict: str          # de_scos | de_adaugat | de_rescris | de_confirmat | acoperit | rezolvat
    termeni: tuple[str, ...]
    gasiti: tuple[str, ...]
    locuri: tuple[str, ...]
    incredere: str = "tare"   # „slaba" = judecat doar pe cuvinte de catalog, fără cod sau acronim

    @property
    def acoperire(self) -> float:
        return len(self.gasiti) / len(self.termeni) if self.termeni else 0.0


def termeni_subiect(punct: Punct, lexicon: set[str]) -> tuple[set[str], set[str]]:
    """Ancorele punctului, în două categorii: tari și slabe.

    **Tari** sunt codurile de flux (MG3, CIRA1) și acronimele scrise cu majuscule (SFA, WMS) —
    un singur astfel de cuvânt identifică subiectul fără dubiu. **Slabe** sunt cuvintele din
    catalogul Charisma („comanda", „factura", „productie"): apar în zeci de locuri, deci spun ceva
    doar când se adună mai multe în aceeași frază.

    Restul cuvintelor nu sunt ancore deloc. Un punct fără ancore nu e despre scop — e despre
    buget, calendar sau despre cum a decurs ședința — și iese din confruntare."""
    text = fara_marcaje(punct.text)
    # tot pe litere mici: documentul e indexat prin `_tokenuri`, care lasă „MG3" ca „mg3".
    # Scrise cu majuscule, codurile nu s-ar potrivi cu nimic și fiecare ar părea absent.
    tari = {m.group(0).lower() for m in TIPAR_COD.finditer(text)}
    tari |= {w.lower() for w in re.findall(r"\b[A-ZĂÂÎȘȚ]{3,}\b", text)}
    slabe = {t for t in _tokenuri(text) if len(t) > 4 and t not in GOALE and t in lexicon}
    return tari, slabe - tari


def confrunta(puncte: list[Punct], doc: Document, prag_slabe: int = 3,
              prag_decisiv: int = 8) -> list[Rezultat]:
    """Verdictul fiecărui punct față de document.

    `prag_decisiv` e cheia împotriva fals-pozitivelor: un cuvânt care apare în zeci de bucăți
    („CORE", „ERP", „CIRA" într-un document despre integrarea CIRA) nu poate decide nimic — e
    vocabularul documentului, nu subiectul punctului. Dacă un punct nu are nicio ancoră
    discriminantă, nu primește verdict; a inventa unul din vocabular general e cum a ieșit
    „capitolul 10 e încă în document" pentru singurul motiv că scria „CORE" pe copertă."""
    lexicon = lexicon_charisma()
    out: list[Rezultat] = []
    for p in puncte:
        tari, slabe = termeni_subiect(p, lexicon)
        decisive = {t for t in tari if 0 < doc.df.get(t, 0) <= prag_decisiv} | \
                   {t for t in tari if doc.df.get(t, 0) == 0}
        if decisive:
            termeni, incredere = decisive, "tare"
        elif len(slabe) >= prag_slabe:
            termeni, incredere = slabe, "slaba"
        else:
            continue
        gasiti, locuri, concentrare = doc.cauta(termeni)
        prezent = concentrare >= 1 if incredere == "tare" else concentrare >= prag_slabe

        # Ordinea contează. „De reformulat" bate „scos": ședința care cere rescrierea unui capitol
        # nu cere ștergerea lui, iar dacă scoaterea ar fi judecată prima, exact capitolele
        # reformulate ar apărea ca nescoase.
        if p.modifica and prezent:
            verdict = "de_rescris"
        elif p.exclude:
            verdict = "de_scos" if prezent else "rezolvat"
        elif prezent:
            verdict = "acoperit"
        elif p.confirmat:
            verdict = "de_adaugat"
        else:
            verdict = "de_confirmat"

        out.append(Rezultat(
            punct=p, verdict=verdict, incredere=incredere,
            termeni=tuple(sorted(termeni)), gasiti=tuple(sorted(gasiti)),
            locuri=tuple(dict.fromkeys(
                f"{b.titlu or '(început de document)'} → {b.text[:70]}" for b in locuri)),
        ))
    return out


ORDINE = ["de_scos", "de_adaugat", "de_rescris", "de_confirmat", "acoperit", "rezolvat"]
ETICHETE = {
    "de_scos": "DE SCOS — ședința a cerut scoaterea, documentul încă le conține",
    "de_adaugat": "DE ADĂUGAT — discutat și confirmat, nu apare în document",
    "de_rescris": "DE RESCRIS — rămâne în scop, dar ședința a cerut reformularea",
    "de_confirmat": "DE CONFIRMAT — deducție sau clarificare, nu se promite până la confirmare",
    "acoperit": "ACOPERIT — discutat și prezent în document",
    "rezolvat": "REZOLVAT — ședința a cerut scoaterea, documentul nu le mai conține",
}
