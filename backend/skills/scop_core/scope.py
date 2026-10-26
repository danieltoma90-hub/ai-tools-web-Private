# -*- coding: utf-8 -*-
"""Asamblarea unui document de scop Charisma ERP CORE, pe structura de 11 capitole.

Conținutul standard CORE NU se scrie aici: vine din `tools.shared.charisma_core.SECTIUNI`,
sursa unică de adevăr. Skill-ul adaugă peste el contextul clientului și elementele
suplimentare declarate în `input/2-suplimentar/`.

Regulă: denumirile de module și tranzacții se iau din manualele CORE
(docs/erp_training/surse/) — nu se inventează.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

from . import stil
from .capitol import alege_sectiuni, scrie_sectiune
from .charisma_core import Flux

PLACEHOLDER = "[ de completat ]"


@dataclass(frozen=True)
class Suplimentar:
    """Un element cerut peste standardul CORE.

    `in_modul` = cheia unei secțiuni CORE (ex. "financiar") dacă elementul se adaugă în
    interiorul acelui modul; None dacă primește capitol propriu în cap. 4.
    """
    titlu: str
    intro: str = ""
    puncte: list[str] = field(default_factory=list)
    fluxuri: list[Flux] = field(default_factory=list)
    nota: str = ""
    in_modul: str | None = None
    incadrare: str = "Inclus"
    capturi: list[tuple[str, str]] = field(default_factory=list)   # (cale, legenda)
    tabel_extra: tuple | None = None   # (titlu, antet, randuri): tabel dupa cel de fluxuri


@dataclass(frozen=True)
class Cerinta:
    """O cerinta a clientului, confruntata cu raspunsul TotalSoft.

    `incadrare`: "A" acoperit integral, "P" partial, "D" de definit, "N" in afara scopului.
    """
    zona: str
    cerinta: str
    raspuns: str
    incadrare: str = "A"


@dataclass
class Client:
    nume: str = PLACEHOLDER
    nume_complet: str = ""
    domeniu: str = ""
    entitati: list[str] = field(default_factory=list)
    # „societati" cand entitatile sunt persoane juridice distincte, „locatii" cand sunt puncte de
    # lucru ale aceleiasi societati. Scrie diferit capitolul 2.2: o singura firma nu are „evidenta
    # contabila pe entitate".
    tip_entitati: str = "societati"
    situatie_actuala: list[tuple[str, str]] = field(default_factory=list)
    obiective: list[str] = field(default_factory=list)
    observatii: str = ""

    @property
    def e_grup(self) -> bool:
        return len(self.entitati) > 1

    @classmethod
    def din_config(cls, cfg: dict) -> "Client":
        c = cfg.get("client", {})
        return cls(
            nume=c.get("nume") or PLACEHOLDER,
            nume_complet=c.get("nume_complet", ""),
            domeniu=c.get("domeniu", ""),
            entitati=list(c.get("entitati", [])),
            observatii=c.get("observatii", ""),
        )


@dataclass
class ScopCorelat:
    """Documentul de scop cu care prezentul document se delimiteaza.

    `denumire` e numele sub care apare in text (implicit „scopul de Producție"), ca documentul sa
    numeasca aria concreta, nu o relatie abstracta.
    """
    exista: bool = False
    titlu: str = ""
    arie_acoperita: str = ""
    coduri: list[str] = field(default_factory=list)
    denumire: str = "scopul de Producție"

    @property
    def denumire_capitalizata(self) -> str:
        return self.denumire[0].upper() + self.denumire[1:] if self.denumire else ""

    @classmethod
    def din_config(cls, cfg: dict) -> "ScopCorelat":
        # se accepta si cheia veche, ca configurarile existente sa nu se rupa
        d = cfg.get("scop_corelat") or cfg.get("document_frate") or {}
        implicit = cls()
        return cls(
            exista=bool(d.get("exista")),
            titlu=d.get("titlu", ""),
            arie_acoperita=d.get("arie_acoperita", ""),
            coduri=list(d.get("coduri", [])),
            denumire=d.get("denumire") or implicit.denumire,
        )


# --------------------------------------------------------------------------- capitole

def _cap1_scop(doc, client: Client, corelat: ScopCorelat, nr: int) -> None:
    stil.heading(doc, f"{nr}. Scopul documentului", 1)
    stil.para(doc,
        f"Prezentul document descrie soluția pe care TotalSoft o propune pentru acoperirea ariilor "
        f"integrate Charisma ERP CORE la {client.nume}. El delimitează scopul funcțional ofertat, "
        f"ce anume se configurează, se dezvoltă și se pune în funcțiune, și constituie baza tehnică "
        f"a ofertei comerciale.")
    if corelat.exista:
        stil.para(doc,
            f"Relația cu {corelat.denumire}. {corelat.arie_acoperita or PLACEHOLDER} face obiectul "
            f"documentului {corelat.titlu or PLACEHOLDER}. Cele două documente sunt complementare și "
            f"nu se suprapun; capitolul de delimitare detaliază explicit granița dintre ele.")
    stil.para(doc,
        "Structura documentului, pe scurt. Capitolele următoare descriu contextul, abordarea și "
        "soluția pe module, apoi analiza de acoperire a cerințelor, delimitările, premisele și "
        "punctele care necesită confirmare înainte de validarea scopului.")


def curata_pentru_client(doc, scoate: list[str] | None, reformulari: list[tuple[str, str]] | None):
    """Scoate sau rescrie, în documentul gata construit, pasaje din conținutul CORE partajat.

    Unele capabilități standard nu se ofertează unui client anume — la o fermă care vinde la
    traderi pe bază de contract și listă de preț, nici campaniile de discount, nici plafonul de
    credit nu au obiect. Ele vin însă din `charisma_core.py`, care alimentează toate documentele,
    deci nu se pot șterge de la sursă fără a-i afecta pe ceilalți clienți.

    Se lucrează pe textul asamblat al paragrafului sau al celulei, nu pe elementele `w:t`:
    corectorul Word sparge frazele în runuri, iar o înlocuire pe element ratează orice potrivire
    care traversează două runuri — și, mai rău, raportează succes.

    Fiecare intrare trebuie să potrivească ceva. Dacă textul din sursa partajată se schimbă,
    filtrul ar înceta să mai taie, în silență; de aceea lipsa unei potriviri este eroare.
    """
    scoate = scoate or []
    reformulari = reformulari or []
    gasite = {t: 0 for t in scoate}
    gasite.update({v: 0 for v, _ in reformulari})

    for p in list(doc.paragraphs):
        text = p.text
        taiat = next((t for t in scoate if t in text), None)
        if taiat:
            gasite[taiat] += 1
            p._p.getparent().remove(p._p)
            continue
        for vechi, nou in reformulari:
            if vechi in text:
                gasite[vechi] += 1
                text = text.replace(vechi, nou)
        if text != p.text:
            stil.scrie_text(p, text)

    for t in doc.tables:
        for r in t.rows:
            vazut = set()
            for c in r.cells:
                if id(c._tc) in vazut:
                    continue
                vazut.add(id(c._tc))
                text = c.text
                for vechi, nou in reformulari:
                    if vechi in text:
                        gasite[vechi] += 1
                        text = text.replace(vechi, nou)
                if text != c.text:
                    for extra in list(c.paragraphs)[1:]:
                        extra._element.getparent().remove(extra._element)
                    stil.scrie_text(c.paragraphs[0], text)

    lipsa = [t for t, n in gasite.items() if n == 0]
    if lipsa:
        raise AssertionError("intrări de curățare care nu au potrivit nimic — probabil s-a "
                             f"schimbat textul din sursa partajată: {lipsa[:3]}")


def _cap_lant_valoric(doc, client: Client, lv: dict, nr: int) -> None:
    """Lanțul valoric al beneficiarului și unde intervine soluția în el.

    Capitolul răspunde la întrebarea „ce câștigă firma", pe verigile activității, nu pe module:
    arată unde se formează sau se pierde valoarea în fluxul propriu și ce aduce soluția în fiecare
    punct. Spre deosebire de capitolul de beneficii, care enumeră efecte, acesta le așază pe
    drumul real al mărfii, de la intrarea în fermă până la valorificare.

    Conținutul vine din modulul de client, prin `LANT_VALORIC`: `intro`, `verigi` (rândurile
    tabelului) și `blocuri` — subcapitolele de după tabel, fiecare cu titlu, introducere, buline
    și paragraf de închidere.
    """
    stil.heading(doc, f"{nr}. Lanțul valoric {client.nume} și contribuția soluției", 1)
    stil.para(doc, lv["intro"])

    stil.heading(doc, f"{nr}.1. Verigile lanțului și unde se formează valoarea", 2)
    stil.tabel(doc, ["Veriga", "Unde se câștigă sau se pierde valoare", "Ce aduce soluția",
                     "Indicator urmărit"],
               lv["verigi"], latimi=[3.1, 4.6, 5.4, 3.4])

    for i, bloc in enumerate(lv["blocuri"], start=2):
        stil.heading(doc, f"{nr}.{i}. {bloc['titlu']}", 2)
        stil.para(doc, bloc["intro"])
        stil.bullets(doc, bloc["puncte"])
        stil.para(doc, bloc["incheiere"])


def _cap_context(doc, client: Client, nr: int) -> None:
    stil.heading(doc, f"{nr}. Contextul proiectului", 1)

    stil.heading(doc, f"{nr}.1. Profilul activității", 2)
    for bucata in (client.domeniu or PLACEHOLDER).split("\n"):
        if bucata.strip():
            stil.para(doc, bucata.strip())

    if client.e_grup:
        if client.tip_entitati == "locatii":
            stil.heading(doc, f"{nr}.2. Structura pe locații", 2)
            stil.para(doc,
                "Activitatea se desfășoară într-o singură societate, pe mai multe locații, cu "
                "roluri distincte:")
            stil.bullets(doc, client.entitati)
            stil.para(doc,
                "Soluția folosește o bază de date comună, cu locații distincte și drepturi de "
                "utilizator alocate pe locație. Documentele operaționale se înregistrează la "
                "locația care le generează, evidența contabilă rămâne unică la nivelul societății, "
                "iar situațiile se pot obține pe o singură locație sau centralizat.")
        else:
            stil.heading(doc, f"{nr}.2. Structura pe entități", 2)
            stil.para(doc,
                "Activitatea se desfășoară pe mai multe societăți, cu roluri distincte:")
            stil.bullets(doc, client.entitati)
            stil.para(doc,
                "Soluția folosește o bază de date comună, cu locații distincte și drepturi de "
                "utilizator alocate pe locație. Fiecare entitate își păstrează propriile documente, "
                "propria contabilitate și propriile declarații.")
        urm = 3
    else:
        urm = 2

    stil.heading(doc, f"{nr}.{urm}. Situația actuală și punctele de îmbunătățire", 2)
    if client.situatie_actuala:
        stil.tabel_doua_coloane(doc, ["Situația actuală", "Cum se adresează în Charisma"],
                                client.situatie_actuala)
    else:
        stil.para(doc, PLACEHOLDER + " — se completează din minuta de analiză.")

    stil.heading(doc, f"{nr}.{urm + 1}. Obiectivele urmărite prin implementare", 2)
    stil.bullets(doc, client.obiective or [PLACEHOLDER])


def _cap_abordare(doc, nr: int) -> None:
    """Abordarea și metodologia, pe două subcapitole, ca în documentele de scop TotalSoft."""
    stil.heading(doc, f"{nr}. Abordarea și metodologia de implementare", 1)

    stil.heading(doc, f"{nr}.1. Abordarea propusă", 2)
    stil.para(doc,
        "Implementarea se realizează etapizat, pe module, nu simultan pe toate ariile; planul se "
        "stabilește de comun acord la începutul proiectului.")
    stil.bullets(doc, [
        "Analiza pe fluxuri de business, împreună cu responsabilii fiecărei zone.",
        "Elaborarea și validarea în comun a specificației contractuale, printr-un proces iterativ; "
        "ceea ce se consemnează în specificație constituie scopul livrat.",
        "Configurarea sistemului și testarea pe fluxuri complete de business.",
        "Instruirea utilizatorilor, testarea de acceptanță și punerea în funcțiune, cu asistență în "
        "perioada de stabilizare.",
    ])
    stil.para(doc,
        "Se urmărește autonomia beneficiarului asupra aplicației: configurările, drepturile de "
        "utilizator și rapoartele pot fi întreținute de utilizatorii proprii. Estimarea finală de "
        "efort se realizează după validarea fluxurilor de către echipele tehnică și de business.")

    stil.heading(doc, f"{nr}.2. Metodologia TotalSoft", 2)
    stil.para(doc,
        "Metodologia de desfășurare a proiectelor are ca fundament standardele din domeniul "
        "managementului de proiect stabilite de Project Management Institute. Documentele care "
        "guvernează desfășurarea proiectului sunt Contractul, Project Charter-ul și Specificația de "
        "Implementare, împreună cu anexele acestora; orice înțelegere neformalizată în unul dintre "
        "aceste documente nu se ia în considerare.")
    stil.para(doc,
        "Proiectul este guvernat de echilibrul triplei constrângeri — Obiect, Buget și Timp: orice "
        "modificare a obiectului influențează bugetul sau durata de implementare.")
    stil.para(doc, "Fiecare subproiect parcurge următoarele faze:")
    stil.bullets(doc, [
        "Iniţiere proiect", "Analiză și design", "Dezvoltări suplimentare",
        "Configurare și instalare", "Migrare date", "Școlarizare",
        "Testare de acceptanță", "Lansarea în producție și acceptanța soluției",
    ])
    stil.para(doc,
        "Fiecare fază produce unul sau mai multe livrabile, recepționate prin documente de "
        "acceptanță de fază. Echipa TotalSoft cuprinde rolurile de Susținător Proiect, Manager "
        "Client, Project Manager, Consultant și Suport tehnic; o persoană poate îndeplini mai multe "
        "roluri.")


def _scrie_suplimentar_propriu(doc, e: Suplimentar, eticheta: str) -> None:
    stil.heading(doc, f"{eticheta}. {e.titlu}", 2)
    if e.intro:
        stil.para(doc, e.intro)
    if e.puncte:
        stil.para(doc, "Funcționalități", bold=True)
        stil.bullets(doc, e.puncte)
    if e.fluxuri:
        stil.tabel_fluxuri(doc, e.fluxuri)
    if e.tabel_extra:
        titlu_tabel, antet, randuri = e.tabel_extra
        if titlu_tabel:
            stil.para(doc, titlu_tabel, bold=True)
        stil.tabel(doc, antet, randuri)
    for cale, legenda in e.capturi:
        stil.captura(doc, cale, legenda)
    if e.nota:
        # o nota poate purta mai multe precizari; fiecare linie devine paragraf propriu
        for bucata in e.nota.split("\n"):
            if bucata.strip():
                stil.para(doc, bucata.strip())


def _cap_solutie(doc, client: Client, sectiuni, suplimentare: list[Suplimentar], nr: int,
                 flux=None, ordine=None, denumire_corelat: str | None = None) -> None:
    """Capitolul 4: standardul CORE, elementele suplimentare și, opțional, fluxul operațional.

    `ordine` — lista care dictează ordinea subcapitolelor: chei de secțiune CORE amestecate cu
    titluri de elemente suplimentare cu capitol propriu. Fără ea, se scriu secțiunile CORE în
    ordinea canonică, apoi elementele cu capitol propriu.
    `flux` — rânduri (etapă, ce se întâmplă în Charisma, rezultat) pentru primul subcapitol.
    """
    pe_modul: dict[str, list[Suplimentar]] = {}
    proprii: dict[str, Suplimentar] = {}
    for e in suplimentare:
        if e.in_modul:
            pe_modul.setdefault(e.in_modul, []).append(e)
        else:
            proprii[e.titlu] = e

    def _dupa(doc_, sectiune):
        """Elementele atașate se scriu în interiorul modulului, după tabelul lui de fluxuri."""
        for e in pe_modul.get(sectiune.cheie, []):
            stil.para(doc_, e.titlu, bold=True)
            if e.intro:
                stil.para(doc_, e.intro)
            if e.puncte:
                stil.bullets(doc_, e.puncte)
            if e.fluxuri:
                stil.tabel_fluxuri(doc_, e.fluxuri)
            if e.tabel_extra:
                titlu_tabel, antet, randuri = e.tabel_extra
                if titlu_tabel:
                    stil.para(doc_, titlu_tabel, bold=True)
                stil.tabel(doc_, antet, randuri)
            for cale, legenda in e.capturi:
                stil.captura(doc_, cale, legenda)
            if e.nota:
                for bucata in e.nota.split("\n"):
                    if bucata.strip():
                        stil.para(doc_, bucata.strip())

    necunoscute = set(pe_modul) - {s.cheie for s in sectiuni}
    if necunoscute:
        raise ValueError("Elemente atașate unor module care nu intră în document: "
                         + ", ".join(sorted(necunoscute)))

    stil.heading(doc, f"{nr}. Soluția ofertată — Charisma ERP CORE", 1)
    stil.para(doc,
        f"Capitolul descrie funcționalitățile Charisma ERP CORE care intră în scopul implementării "
        f"la {client.nume}, pe module, cu fluxurile operaționale acoperite.")

    index = 1
    if flux:
        stil.heading(doc, f"{nr}.{index}. Fluxul operațional acoperit", 2)
        # „în {denumire}” cere acuzativ, deci merge cu forma nominativa a denumirii; „aparține”
        # ar cere dativ si ar produce un acord greșit.
        trimitere = (f" Ce este tratat în {denumire_corelat} este marcat ca atare."
                     if denumire_corelat else "")
        stil.para(doc,
            "Tabelul urmărește lanțul acoperit de prezentul document, etapă cu etapă." + trimitere)
        stil.tabel(doc, ["Etapa", "Ce se întâmplă în Charisma", "Rezultat"], flux,
                   latimi=[3.4, 9.0, 4.2])
        index += 1

    pe_cheie = {s.cheie: s for s in sectiuni}
    if ordine:
        necunoscute_ordine = [x for x in ordine if x not in pe_cheie and x not in proprii]
        if necunoscute_ordine:
            raise ValueError("Ordine de capitol necunoscută: " + ", ".join(necunoscute_ordine))
        lipsa = [c for c in pe_cheie if c not in ordine] + [t for t in proprii if t not in ordine]
        if lipsa:
            raise ValueError("Elemente absente din ordinea declarată: " + ", ".join(lipsa))
        secventa = ordine
    else:
        secventa = [s.cheie for s in sectiuni] + list(proprii)

    for cheie in secventa:
        if cheie in pe_cheie:
            scrie_sectiune(doc, pe_cheie[cheie], f"{nr}.{index}", nivel=1, dupa_sectiune=_dupa)
        else:
            _scrie_suplimentar_propriu(doc, proprii[cheie], f"{nr}.{index}")
        index += 1


def _cap_beneficii(doc, beneficii: list[str], nr: int) -> None:
    stil.heading(doc, f"{nr}. Beneficiile soluției", 1)
    stil.bullets(doc, beneficii or [PLACEHOLDER])


_FORME_ACOPERIRE = ("apdn", "trei-grupe")

_GRUPE_APDN = {
    "A": ("Cerințe acoperite integral (A)",
          "Cerințele de mai jos se realizează cu funcționalitățile descrise mai sus și sunt "
          "cuprinse în efortul ofertat."),
    "P": ("Cerințe acoperite parțial (P)",
          "Pentru cerințele de mai jos platforma dispune de mecanismul necesar, însă forma finală "
          "depinde de decizii care se iau în analiză."),
    "D": ("Cerințe care necesită definire prin analiză dedicată (D)",
          "Elementele de mai jos nu pot fi dimensionate pe baza informațiilor disponibile în "
          "această etapă și nu sunt cuprinse în efortul ofertat."),
    "N": ("Cerințe în afara scopului acestui document (N)",
          "Zonele de mai jos aparțin altor module sau produse și se ofertează distinct."),
}

# Forma cu trei grupe, folosită de documentele de scop TotalSoft: parțial și de-definit se
# prezintă împreună, întrucât ambele lasă o parte a efortului în afara bugetului ofertat.
_GRUPE_TREI = (
    ("Elemente incluse explicit în efortul ofertat", ("A",),
     "Elementele de mai jos sunt acoperite de funcționalitățile descrise mai sus și intră în "
     "efortul ofertat prin prezentul document."),
    ("Elemente acoperite parțial sau care necesită analiză dedicată", ("P", "D"),
     "Pentru elementele de mai jos mecanismul de bază este disponibil, însă forma finală sau "
     "dimensionarea depind de decizii care se iau în analiză."),
    ("Arii în afara scopului acestui document", ("N",),
     "Ariile de mai jos aparțin altor module, altor produse sau altor secțiuni ale ofertei și se "
     "ofertează distinct."),
)


def _cap_acoperire(doc, cerinte: list[Cerinta], nr: int, forma: str = "apdn") -> None:
    if forma not in _FORME_ACOPERIRE:
        raise ValueError(f"Formă de acoperire necunoscută: {forma!r}. "
                         f"Valori acceptate: {', '.join(_FORME_ACOPERIRE)}")

    titlu_cap = ("Analiza de acoperire a cerințelor" if forma == "apdn"
                 else "Scopul ofertat și delimitări")
    stil.heading(doc, f"{nr}. {titlu_cap}", 1)
    stil.para(doc,
        "Capitolul precizează, pentru claritate contractuală, ce intră în efortul ofertat, ce este "
        "acoperit parțial și ce rămâne în afara scopului. O arie neacoperită nu înseamnă o cerință "
        "refuzată: înseamnă că soluția și efortul aferent nu pot fi definite pe baza informațiilor "
        "disponibile în această etapă.")

    index = 1
    if forma == "apdn":
        stil.heading(doc, f"{nr}.{index}. Modul de încadrare a cerințelor", 2); index += 1
        stil.tabel(doc, ["Încadrare", "Ce înseamnă", "Efect asupra efortului ofertat"], [
            ["A. Acoperit",
             "Cerința se realizează integral prin configurare sau prin dezvoltările deja "
             "dimensionate.", "Inclus în efortul ofertat"],
            ["P. Acoperit parțial",
             "Mecanismul de bază este inclus, însă forma finală depinde de decizii care se "
             "stabilesc în analiză.",
             "Partea de bază inclusă; extinderea se estimează după analiză"],
            ["D. De definit",
             "Realizabilă pe platformă, dar fără o analiză dedicată soluția nu poate fi definită.",
             "Neinclus în efortul ofertat"],
            ["N. În afara scopului",
             "Aparține altui modul, altui produs sau altei secțiuni a ofertei.",
             "Se ofertează distinct"],
        ], latimi=[2.6, 8.0, 5.4])

    if not cerinte:
        stil.para(doc, PLACEHOLDER + " — încadrarea element cu element se completează din "
                                     "informațiile transmise de beneficiar.")
        return

    numar = {k: sum(1 for c in cerinte if c.incadrare == k) for k in ("A", "P", "D", "N")}
    stil.para(doc,
        f"Au fost analizate {len(cerinte)} elemente: {numar['A']} sunt acoperite integral, "
        f"{numar['P']} sunt acoperite parțial, {numar['D']} necesită definire prin analiză "
        f"dedicată, iar {numar['N']} se ofertează distinct.")

    grupe = ([(t, (k,), i) for k, (t, i) in _GRUPE_APDN.items()] if forma == "apdn"
             else list(_GRUPE_TREI))
    for titlu, chei, intro in grupe:
        grup = [c for c in cerinte if c.incadrare in chei]
        if not grup:
            continue
        stil.heading(doc, f"{nr}.{index}. {titlu}", 2); index += 1
        stil.para(doc, intro)
        stil.tabel(doc, ["Zona", "Elementul", "Răspunsul soluției"],
                   [[c.zona, c.cerinta, c.raspuns] for c in grup], latimi=[2.6, 5.4, 8.6])


def _cap_delimitare(doc, corelat: ScopCorelat, zone, nr: int, intro: str | None = None) -> None:
    """Delimitarea față de scopul corelat.

    `zone` — rânduri (zona, tratată în, punctul de interfațare). Când lipsesc, se construiește
    un tabel-schelet din codurile declarate în configurare.
    """
    stil.heading(doc, f"{nr}. Delimitarea față de {corelat.denumire}", 1)
    stil.para(doc, intro or (
        "Cele două documente acoperă arii complementare și au fost construite astfel încât să nu se "
        "suprapună. Tabelul precizează granița și punctele în care cele două scopuri se ating. "
        "Prefixele de cod se repetă între documente, motiv pentru care fiecare trimitere precizează "
        "documentul din care provine codul."))
    randuri = list(zone) if zone else (
        [[c, corelat.titlu or PLACEHOLDER, PLACEHOLDER] for c in corelat.coduri]
        or [[PLACEHOLDER, corelat.titlu or PLACEHOLDER, PLACEHOLDER]])
    stil.tabel(doc, ["Zona", "Tratată în", "Punctul de interfațare"], randuri,
               latimi=[4.6, 3.6, 8.8])


def _cap_premise(doc, nr: int, extra: dict[str, list[str]] | None = None) -> None:
    """Premisele standard, plus punctele suplimentare pe client.

    `extra` are cheile „infrastructura”, „date” si „organizare”; punctele se adauga la finalul
    subcapitolului corespunzator. Fara ele, capitolul iese identic pentru toate documentele.
    """
    extra = extra or {}
    stil.heading(doc, f"{nr}. Premise și responsabilități", 1)
    stil.para(doc,
        "Buna funcționare a soluției presupune îndeplinirea următoarelor condiții, care revin în "
        "sarcina beneficiarului și se stabilesc împreună în etapa de analiză:")
    stil.heading(doc, f"{nr}.1. Infrastructură", 2)
    stil.bullets(doc, [
        "Stații Windows pentru operarea în back-office. Charisma ERP este o aplicație client-server "
        "pe Windows, care poate fi instalată on-premise sau în cloud.",
        "Imprimante pentru documentele emise, cu consumabilele și formularele aferente.",
        "Conexiune la internet pentru integrările cu ANAF și pentru relația cu băncile.",
    ] + list(extra.get("infrastructura", [])))
    stil.heading(doc, f"{nr}.2. Date și pregătire operațională", 2)
    stil.bullets(doc, [
        "Nomenclatoarele de articole și de parteneri, cu proprietățile și clasificările aferente.",
        "Modelele de contare agreate cu departamentul de contabilitate, pe fiecare tranzacție.",
        "Soldurile, balanța de inițializare, stocurile și registrul de mijloace fixe la data punerii "
        "în funcțiune.",
    ] + list(extra.get("date", [])))
    stil.heading(doc, f"{nr}.3. Organizare", 2)
    stil.bullets(doc, [
        "Utilizator și parolă individuale pentru fiecare operator, cu drepturi pe grupuri.",
        "Key-users desemnați pe fiecare arie, cu disponibilitate pentru analiză, testare și instruire.",
        "Un administrator de aplicație din partea beneficiarului.",
        "Testarea pe fluxuri complete de business; nu se recomandă lucrul în paralel în două sisteme.",
        "Asumarea la nivel de management a noului mod de lucru.",
    ] + list(extra.get("organizare", [])))


def _cap_confirmari(doc, puncte: list[tuple[str, str]], nr: int) -> None:
    stil.heading(doc, f"{nr}. Puncte de confirmat înainte de validarea scopului", 1)
    stil.para(doc,
        "Următoarele aspecte necesită confirmarea beneficiarului. Ele influențează atât soluția, cât "
        "și efortul de implementare, și se clarifică în prima etapă a analizei.")
    randuri = [[str(i), a, b] for i, (a, b) in enumerate(puncte, start=1)] or \
              [["1", PLACEHOLDER, PLACEHOLDER]]
    stil.tabel(doc, ["Nr.", "Aspect de confirmat", "De ce contează"], randuri,
               latimi=[1.2, 8.0, 7.0])


def _cap_sinteza(doc, sectiuni, suplimentare: list[Suplimentar], nr: int) -> None:
    stil.heading(doc, f"{nr}. Sinteza scopului funcțional", 1)
    stil.para(doc,
        "Tabelul consolidează, pe coduri, scopul propus. Este destinat utilizării ca anexă la ofertă "
        "și la specificația contractuală.")
    randuri = []
    for s in sectiuni:
        coduri = [f.cod for f in s.fluxuri]
        interval = f"{coduri[0]} - {coduri[-1]}" if len(coduri) > 1 else (coduri[0] if coduri else s.prefix)
        randuri.append([interval, s.titlu, "Inclus"])
    for e in suplimentare:
        coduri = [f.cod for f in e.fluxuri]
        interval = f"{coduri[0]} - {coduri[-1]}" if len(coduri) > 1 else (coduri[0] if coduri else "—")
        randuri.append([interval, e.titlu, e.incadrare])
    stil.tabel(doc, ["Cod", "Funcționalitate", "Încadrare bugetară"], randuri,
               latimi=[2.2, 9.3, 5.0])


def _cap_validare(doc, client: Client, nr: int) -> None:
    stil.heading(doc, f"{nr}. Validarea scopului", 1)
    stil.para(doc,
        "Prezentul document reprezintă scopul funcțional descris, care reflectă cerințele "
        "identificate și constituie baza ofertei comerciale, urmând ca detalierea la nivel de "
        "soluție să fie realizată în specificația de implementare elaborată în etapa de analiză.")
    semnatura = "Nume și prenume:\n\nFuncție:\n\nData:\n\nSemnătura:"
    stil.tabel(doc, [f"Din partea {client.nume}", "Din partea TotalSoft S.A."],
               [[semnatura, semnatura]], latimi=[8.3, 8.3], bold_prima_coloana=False)


def _rescrie_antet_subsol(doc, cfg_stil: dict, client: Client, versiune: str) -> None:
    """Rescrie antetul și linia de subsol moștenite din gazdă.

    Gazda e un document de client: antetul îi numește aria, iar subsolul îi poartă numele. Lăsate
    așa, documentul nou le tipărește pe fiecare pagină.
    """
    subsol = cfg_stil.get("subsol")
    if subsol is None:
        subsol = f"{client.nume}  |  Charisma ERP  |  v{versiune}"
    stil.rescrie_antet_subsol(doc, text_antet=cfg_stil.get("antet"), text_subsol=subsol)


# --------------------------------------------------------------------------- asamblare

def genereaza(cfg: dict, cale_iesire, client: Client | None = None,
              suplimentare: list[Suplimentar] | None = None,
              beneficii: list[str] | None = None,
              confirmari: list[tuple[str, str]] | None = None,
              acoperire: list[Cerinta] | None = None,
              delimitare: list | None = None,
              flux_operational: list | None = None,
              ordine_cap4: list | None = None,
              delimitare_intro: str | None = None,
              premise_extra: dict[str, list[str]] | None = None,
              lant_valoric: dict | None = None,
              scoate_buline: list[str] | None = None,
              reformulari: list[tuple[str, str]] | None = None):
    """Construiește documentul complet și îl salvează. Întoarce calea scrisă."""
    client = client or Client.din_config(cfg)
    corelat = ScopCorelat.din_config(cfg)
    suplimentare = suplimentare or []
    cap = cfg.get("capitole", {})
    sc = cfg.get("sectiuni_core", {})
    sectiuni = alege_sectiuni(
        fara=None if sc.get("toate", True) else (sc.get("fara") or None),
        doar=None if sc.get("toate", True) else (sc.get("doar") or None),
    )

    gazda = (cfg.get("stil", {}) or {}).get("document_gazda") or None
    stil.reseteaza_contorul_figurilor()
    doc = stil.document_din_gazda(gazda)
    _rescrie_antet_subsol(doc, cfg.get("stil", {}) or {}, client,
                          d.get("versiune", "1.0") if (d := cfg.get("document", {})) else "1.0")

    # Numerotarea se rescrie, nu se mosteneste: gazda isi aduce cu ea valorile puse in cache
    # („Pag. 19 / 1"), care raman vizibile pana cand cineva deschide documentul si da F9.
    stil.rescrie_numerotarea(doc, (cfg.get("stil", {}) or {}).get(
        "numerotare", "Pag. {PAGE} / {NUMPAGES}"))

    d = cfg.get("document", {})
    stil.rescrie_proprietati(
        doc,
        titlu=f"{d.get('titlu', '')} | {client.nume}".strip(" |"),
        subiect=d.get("subtitlu", ""),
        autor=d.get("furnizor", "TotalSoft S.A."),
    )
    stil.para(doc, d.get("titlu", "Descrierea soluției ofertate"), bold=True)
    stil.para(doc, d.get("subtitlu", "Implementare Charisma ERP CORE"), bold=True)
    stil.para(doc, f"Beneficiar: {client.nume_complet or client.nume}")
    stil.tabel(doc, ["Element", "Detaliu"], [
        ["Beneficiar", client.nume_complet or client.nume],
        ["Furnizor", d.get("furnizor", "TotalSoft S.A.")],
        ["Aria acoperită", "Charisma ERP CORE: " + ", ".join(s.titlu for s in sectiuni)],
        ["Documente corelate", corelat.titlu or "—"],
        ["Versiune document", d.get("versiune", "1.0")],
        ["Elaborat de", d.get("elaborat_de", "Echipa de consultanță TotalSoft, Delivery ERP")],
    ], latimi=[4.5, 12.0])

    nr = 1
    _cap1_scop(doc, client, corelat, nr); nr += 1
    if cap.get("context", True):
        _cap_context(doc, client, nr); nr += 1
    # Abordarea si metodologia descriu munca noastra, nu solutia oferita, deci nu intra
    # implicit: scopul explica beneficiarului ce acoperim, nu cum lucreaza consultantul.
    # Lantul valoric sta intre context si solutie: cititorul vede ce castiga, pe verigile
    # activitatii lui, inainte sa intre in descrierea pe module.
    if lant_valoric and cap.get("lant_valoric", True):
        _cap_lant_valoric(doc, client, lant_valoric, nr); nr += 1
    if cap.get("abordare", False):
        _cap_abordare(doc, nr); nr += 1
    _cap_solutie(doc, client, sectiuni, suplimentare, nr,
                 flux=flux_operational, ordine=ordine_cap4,
                 denumire_corelat=corelat.denumire if corelat.exista else None); nr += 1
    if cap.get("beneficii", True):
        _cap_beneficii(doc, beneficii or [], nr); nr += 1
    if cap.get("acoperire", True):
        _cap_acoperire(doc, acoperire or [], nr,
                       forma=(cfg.get('stil', {}) or {}).get('forma_acoperire', 'apdn'))
        nr += 1
    if cap.get("delimitare", True) and corelat.exista:
        _cap_delimitare(doc, corelat, delimitare or [], nr, intro=delimitare_intro)
        nr += 1
    if cap.get("premise", True):
        _cap_premise(doc, nr, premise_extra); nr += 1
    if cap.get("confirmari", True):
        _cap_confirmari(doc, confirmari or [], nr); nr += 1
    if cap.get("sinteza", True):
        _cap_sinteza(doc, sectiuni, suplimentare, nr); nr += 1
    if cap.get("validare", True):
        _cap_validare(doc, client, nr)

    props = doc.core_properties
    props.title = f"{d.get('titlu')} - Charisma ERP CORE | {client.nume}"
    props.subject = f"Scop Charisma ERP CORE - {client.nume}"

    # Curățarea per client se face aici, pe documentul construit, înaintea transliterării:
    # pasajele vin din conținutul CORE partajat, care nu se poate modifica pentru un singur
    # client, iar textele căutate sunt scrise cu diacritice.
    if scoate_buline or reformulari:
        curata_pentru_client(doc, scoate_buline, reformulari)

    if (cfg.get("stil", {}) or {}).get("fara_diacritice"):
        stil.transliterare_document(doc)

    cale = pathlib.Path(cale_iesire)
    cale.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(cale))
    return cale
