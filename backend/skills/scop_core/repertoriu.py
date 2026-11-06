# -*- coding: utf-8 -*-
"""Repertoriul elementelor de scop: ce am mai scris, ca să nu rescriem.

Un document de scop are două jumătăți. Standardul CORE trăiește în `charisma_core.py` și e
același la toți clienții. Cealaltă jumătate — MultiCash, e-Factura, postcalcul, integrarea cu
aplicația de magazin — se scria de fiecare dată de la zero, în `continut_<client>.py`, deși la al
patrulea client textul e în mare parte același. Repertoriul adună aceste elemente într-un singur
loc căutabil, ca un scop nou să înceapă de la ce avem, nu de la pagina albă.

**Varianta, nu media.** Același element scris pentru un grup de lactate și pentru un industrial nu
e același text. Nu le topim într-unul singur: fiecare client își păstrează varianta lui, iar
elementul arată implicit varianta cea mai detaliată. Cine ia elementul într-un scop nou vede toate
formele în care l-am mai livrat și alege, sau scrie a cincea.

**Termenii** sunt singurul lucru derivat automat: codurile de flux, acronimele și cuvintele rare
din denumire și descriere. Ei sunt cârligele cu care o minută nouă regăsește elementul — vezi
`filtru_standard.py`.

Datele stau ca JSON, un fișier pe element, în `repertoriu/` la rădăcina workspace-ului; alături se
regenerează `REPERTORIU.md`, ca să se poată citi și fără unealtă.
"""
from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .confrunta import GOALE, TIPAR_COD, _tokenuri
from .minute import fara_diacritice

NUME_DOSAR = "repertoriu"


def dosar(cale: Path | str | None = None) -> Path:
    """Unde stă repertoriul. Căutat în sus de la modul, ca să meargă din orice skill; pe web nu
    există și atunci `incarca` întoarce o listă goală, fără să cadă."""
    if cale:
        return Path(cale)
    din_mediu = os.environ.get("REPERTORIU_SCOP")
    if din_mediu:
        return Path(din_mediu)
    aici = Path(__file__).resolve()
    for parinte in aici.parents:
        if (parinte / NUME_DOSAR).is_dir():
            return parinte / NUME_DOSAR
    return aici.parents[2] / NUME_DOSAR


def slug(text: str) -> str:
    t = fara_diacritice(text).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:60] or "element"


@dataclass
class Varianta:
    """Elementul așa cum a fost livrat unui client. Textul nu se amestecă între variante."""

    client: str
    descriere: str = ""
    puncte: list[str] = field(default_factory=list)
    fluxuri: list[dict] = field(default_factory=list)
    nota: str = ""
    sursa: str = ""
    denumire: str = ""        # titlul sub care a apărut la clientul acela

    @property
    def greutate(self) -> int:
        """Cât de detaliată e varianta — după asta se alege cea implicită."""
        return (len(self.descriere) + sum(len(p) for p in self.puncte)
                + 200 * len(self.fluxuri) + len(self.nota))


@dataclass
class Element:
    """Un subiect care se adaugă peste standardul CORE, cu toate formele în care l-am livrat."""

    cheie: str
    denumire: str
    capitol: str | None = None        # cheia secțiunii CORE; None = capitol propriu în cap. 4
    incadrare: str = "Inclus"
    termeni: list[str] = field(default_factory=list)
    variante: list[Varianta] = field(default_factory=list)
    implicit: int = 0
    actualizat: str = ""

    @property
    def varianta(self) -> Varianta:
        if not self.variante:
            return Varianta(client="")
        return self.variante[min(self.implicit, len(self.variante) - 1)]

    @property
    def descriere(self) -> str:
        return self.varianta.descriere

    @property
    def puncte(self) -> list[str]:
        return self.varianta.puncte

    @property
    def fluxuri(self) -> list[dict]:
        return self.varianta.fluxuri

    @property
    def nota(self) -> str:
        return self.varianta.nota

    @property
    def clienti(self) -> list[str]:
        return [v.client for v in self.variante if v.client]

    @property
    def nou(self) -> bool:
        """Un element fără nicio variantă scrisă e un subiect ridicat în ședință și nimic mai
        mult: intră în document marcat ca atare, nu cu text inventat aici."""
        return not any(v.descriere or v.puncte for v in self.variante)

    def pentru(self, client: str) -> Varianta | None:
        tinta = fara_diacritice(client).lower()
        for v in self.variante:
            if fara_diacritice(v.client).lower() == tinta:
                return v
        return None

    def ca_json(self) -> dict:
        return {
            "cheie": self.cheie,
            "denumire": self.denumire,
            "capitol": self.capitol,
            "incadrare": self.incadrare,
            "termeni": sorted(self.termeni),
            "implicit": self.implicit,
            "actualizat": self.actualizat or datetime.date.today().isoformat(),
            "variante": [
                {"client": v.client, "denumire": v.denumire, "sursa": v.sursa,
                 "descriere": v.descriere, "puncte": v.puncte, "fluxuri": v.fluxuri,
                 "nota": v.nota}
                for v in self.variante
            ],
        }

    @classmethod
    def din_json(cls, d: dict) -> Element:
        return cls(
            cheie=d["cheie"], denumire=d["denumire"], capitol=d.get("capitol"),
            incadrare=d.get("incadrare", "Inclus"), termeni=list(d.get("termeni", [])),
            implicit=int(d.get("implicit", 0)), actualizat=d.get("actualizat", ""),
            variante=[Varianta(**v) for v in d.get("variante", [])],
        )


def termeni_din(denumire: str, descriere: str = "", puncte=None, fluxuri=None) -> list[str]:
    """Cârligele elementului: codurile de flux, acronimele și cuvintele rare.

    Denumirea cântărește cel mai mult — „Schimbul de fișiere bancare în format MultiCash" conține
    exact cuvintele cu care subiectul revine în minuta următorului client. Din descriere luăm doar
    acronimele și codurile, fiindcă o descriere de zece rânduri aduce mai mult zgomot decât semnal.
    """
    termeni: set[str] = set()
    for cod in TIPAR_COD.finditer(f"{denumire} {descriere}"):
        termeni.add(cod.group(0).lower())
    for acronim in re.findall(r"\b[A-ZĂÂÎȘȚ]{3,}\b", f"{denumire} {descriere}"):
        termeni.add(acronim.lower())
    termeni.update(t for t in _tokenuri(denumire) if len(t) > 4 and t not in GOALE)
    for f in fluxuri or []:
        nume = f.get("flux", "") if isinstance(f, dict) else getattr(f, "flux", "")
        cod = f.get("cod", "") if isinstance(f, dict) else getattr(f, "cod", "")
        if cod:
            termeni.add(cod.lower())
        termeni.update(t for t in _tokenuri(nume) if len(t) > 4 and t not in GOALE)
    return sorted(termeni)


# --------------------------------------------------------------------------- citire / scriere

def incarca(cale: Path | str | None = None) -> list[Element]:
    d = dosar(cale)
    if not d.is_dir():
        return []
    elemente = []
    for f in sorted(d.glob("*.json")):
        elemente.append(Element.din_json(json.loads(f.read_text(encoding="utf-8"))))
    return elemente


def scrie(el: Element, cale: Path | str | None = None) -> Path:
    """Scrie elementul, cu varianta cea mai detaliată pusă prima.

    Denumirea elementului o dă tot ea: „Business Intelligence" scris la un client și „Business
    Intelligence și raportare managerială" la altul sunt același subiect, iar titlul care spune
    mai mult e cel sub care merită căutat."""
    d = dosar(cale)
    d.mkdir(parents=True, exist_ok=True)
    el.variante.sort(key=lambda v: -v.greutate)
    el.implicit = 0
    if el.variante and el.variante[0].denumire:
        el.denumire = el.variante[0].denumire
    el.actualizat = datetime.date.today().isoformat()
    f = d / f"{el.cheie}.json"
    f.write_text(json.dumps(el.ca_json(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return f


def adauga(el: Element, cale: Path | str | None = None) -> Path:
    """Scrie elementul, îmbinându-l cu ce există deja sub aceeași cheie.

    Îmbinarea e pe client: aceeași denumire livrată altui client adaugă o variantă; aceluiași
    client, o înlocuiește. Nimic nu se suprascrie în tăcere între clienți — asta ar amesteca texte
    scrise pentru contexte diferite."""
    d = dosar(cale)
    f = d / f"{el.cheie}.json"
    if f.exists():
        vechi = Element.din_json(json.loads(f.read_text(encoding="utf-8")))
        for v in el.variante:
            existenta = vechi.pentru(v.client)
            if existenta:
                vechi.variante[vechi.variante.index(existenta)] = v
            else:
                vechi.variante.append(v)
        vechi.termeni = sorted(set(vechi.termeni) | set(el.termeni))
        vechi.capitol = el.capitol if el.capitol is not None else vechi.capitol
        el = vechi
    return scrie(el, cale)


# --------------------------------------------------------------------------- căutare

def cauta(termeni, elemente: list[Element] | None = None, prag: int = 2) -> list[tuple[int, Element]]:
    """Elementele care împart cârlige cu termenii dați, de la cel mai bine potrivit.

    Un cod de flux comun valorează cât trei cuvinte: „MG1" nu apare din întâmplare."""
    elemente = incarca() if elemente is None else elemente
    cautati = {t.lower() for t in termeni}
    out = []
    for el in elemente:
        ai_lui = set(el.termeni)
        comune = ai_lui & cautati
        if not comune:
            continue
        coduri = {t for t in comune if TIPAR_COD.fullmatch(t.upper())}
        scor = len(comune) + 2 * len(coduri)
        if scor >= prag:
            out.append((scor, el))
    return sorted(out, key=lambda x: (-x[0], x[1].cheie))


def ca_suplimentar(el: Element, client: str | None = None) -> dict:
    """Elementul în forma pe care o mănâncă generatorul (`scope.Suplimentar`).

    Elementul fără text scris intră cu încadrarea de dezvoltare și cu descrierea goală: scopul
    spune atunci că subiectul e în listă și urmează a fi detaliat, nu inventează funcționalitate.
    """
    from .charisma_core import Flux

    v = (el.pentru(client) if client else None) or el.varianta
    return {
        "titlu": el.denumire,
        "intro": v.descriere,
        "puncte": list(v.puncte),
        "fluxuri": [Flux(**f) for f in v.fluxuri],
        "nota": v.nota,
        "in_modul": el.capitol,
        "incadrare": el.incadrare,
    }


# --------------------------------------------------------------------------- citit de om

def index_md(elemente: list[Element]) -> str:
    linii = [
        "# Repertoriul elementelor de scop", "",
        f"{len(elemente)} subiecte scrise peste standardul Charisma CORE, din "
        f"{len({c for e in elemente for c in e.clienti})} proiecte. Fiecare client își păstrează "
        "varianta lui de text; elementul arată implicit varianta cea mai detaliată.", "",
        "**Cum se folosește.** Dintr-un scop nou: "
        "`python skills/generare-scope-core/repertoriu_scop.py cauta \"<subiect>\"`, iar "
        "`minute_in_scop.py filtru` îl consultă singur și propune elementul cu textul de aici.",
        "",
        "**Cum se ține la zi.** Nu se scrie direct în fișierele astea: conținutul se scrie în "
        "`skills/generare-scope-core/continut_<client>.py`, ca pentru orice ofertă, apoi "
        "`repertoriu_scop.py seminteaza` reconstruiește repertoriul din toate modulele de "
        "conținut. Un singur loc de ținut la zi — cel în care oricum se lucrează.", "",
        "| Element | Unde intră | Livrat la | Fluxuri |", "|---|---|---|---|"]
    for el in sorted(elemente, key=lambda e: (e.capitol or "~propriu", e.denumire)):
        unde = el.capitol or "capitol propriu"
        linii.append(f"| [{el.denumire}]({el.cheie}.json) | {unde} | "
                     f"{', '.join(el.clienti) or '—'} | {len(el.fluxuri)} |")
    return "\n".join(linii) + "\n"


def repertoriu_md(elemente: list[Element]) -> str:
    """Tot repertoriul ca text, ca să poată fi citit fără unealtă și căutat cu Ctrl+F."""
    bucati = ["# Repertoriul elementelor de scop — text integral", ""]
    for el in sorted(elemente, key=lambda e: (e.capitol or "~propriu", e.denumire)):
        bucati.append(f"## {el.denumire}")
        bucati.append("")
        bucati.append(f"- **Unde intră:** {el.capitol or 'capitol propriu în cap. 4'}")
        bucati.append(f"- **Încadrare:** {el.incadrare}")
        bucati.append(f"- **Livrat la:** {', '.join(el.clienti) or '—'}")
        bucati.append(f"- **Termeni:** {', '.join(el.termeni)}")
        bucati.append("")
        for v in el.variante:
            bucati.append(f"### Varianta {v.client or '(fără client)'}")
            bucati.append("")
            if v.descriere:
                bucati.append(v.descriere)
                bucati.append("")
            for p in v.puncte:
                bucati.append(f"- {p}")
            if v.puncte:
                bucati.append("")
            for f in v.fluxuri:
                bucati.append(f"- `{f.get('cod', '')}` **{f.get('flux', '')}** — "
                              f"{f.get('presupune', '')}")
            if v.fluxuri:
                bucati.append("")
            if v.nota:
                bucati.append(f"> {v.nota}")
                bucati.append("")
    return "\n".join(bucati) + "\n"


def regenereaza_md(cale: Path | str | None = None) -> list[Path]:
    d = dosar(cale)
    elemente = incarca(d)
    scrise = []
    for nume, continut in (("INDEX.md", index_md(elemente)),
                           ("REPERTORIU.md", repertoriu_md(elemente))):
        f = d / nume
        f.write_text(continut, encoding="utf-8")
        scrise.append(f)
    return scrise
