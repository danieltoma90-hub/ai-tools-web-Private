# -*- coding: utf-8 -*-
"""Teste pentru elementele suplimentare din capitolul CORE (Task 2).

`GAZDA` e derivat dintr-o gazdă reală (Turkish Doner Steakhouse), cu corpul
redus la strict paragrafele „List Paragraph” cu `w:numPr` (anonimizate, fără
niciun text de-al clientului), antet/subsol golite și proprietățile de
document șterse — vezi `test_fixture_gazda_produce_buline_reale_cu_numpr`
pentru dovada că nu e doar un `Document()` gol. Păstrează `styles.xml`,
`numbering.xml`, tema și `sectPr` reale, deci `Heading 1`/`Heading 2` rezolvă
și `stil._numid_pentru_buline` are o definiție de numerotare reală de la care
să învețe — nu doar stilurile implicite din python-docx. Nu e documentul real
de la client: acela trăiește în alt repo (`d:\\AI_Claude`) și nu trebuie să fie
o dependență a suitei de teste a acestui repo.
"""
from __future__ import annotations

import pathlib

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from skills.scop_core import capitol, stil
from skills.scop_core.charisma_core import SECTIUNI

GAZDA = pathlib.Path(__file__).resolve().parent / "fixtures" / "gazda_reala_anonimizata.docx"


def _corp_in_ordine(doc):
    """Corpul documentului în ordinea reală de apariție, paragrafe și tabele
    amestecate — spre deosebire de `doc.paragraphs`, care omite tabelele cu
    totul și nu poate proba nicio regulă relativă la poziția unui tabel."""
    rezultat = []
    for copil in doc.element.body:
        if copil.tag == qn("w:p"):
            rezultat.append(("p", Paragraph(copil, doc).text))
        elif copil.tag == qn("w:tbl"):
            rezultat.append(("tbl", None))
    return rezultat


def test_element_ca_subcapitol_apare_sub_sectiunea_ceruta():
    doc = stil.document_din_gazda(GAZDA)
    el = capitol.Element(titlu="Aprobare comenzi pe niveluri", text="Text.", plasare="achizitii")
    capitol.construieste(doc, capitol.alege_sectiuni(None, ["contabilitate", "achizitii"]),
                         numar=5, elemente=[el])
    texte = [p.text for p in doc.paragraphs]
    assert texte.index("5.2.1. Aprobare comenzi pe niveluri") > texte.index("5.2. Modulul Achiziții")


def test_element_propriu_apare_dupa_sectiunile_standard():
    doc = stil.document_din_gazda(GAZDA)
    el = capitol.Element(titlu="Integrare cu cântarele", text="Text.", plasare="propriu")
    capitol.construieste(doc, capitol.alege_sectiuni(None, None), numar=5, elemente=[el])
    h2 = [p.text for p in doc.paragraphs if p.style.name == "Heading 2"]
    assert h2[-1] == "5.11. Integrare cu cântarele"


def test_fluxurile_legate_se_randeaza_cu_denumirile_verificate():
    doc = stil.document_din_gazda(GAZDA)
    el = capitol.Element(titlu="X", text="Text.", plasare="vanzari", fluxuri_legate=["V2"])
    capitol.construieste(doc, capitol.alege_sectiuni(None, ["vanzari"]), numar=5, elemente=[el])
    v2 = next(f for s in SECTIUNI if s.cheie == "vanzari" for f in s.fluxuri if f.cod == "V2")
    assert v2.flux in "\n".join(p.text for p in doc.paragraphs)


def test_cod_de_flux_inexistent_nu_rupe_generarea():
    doc = stil.document_din_gazda(GAZDA)
    el = capitol.Element(titlu="X", text="Text.", plasare="vanzari", fluxuri_legate=["ZZ9"])
    capitol.construieste(doc, capitol.alege_sectiuni(None, ["vanzari"]), numar=5, elemente=[el])
    assert "ZZ9" not in "\n".join(p.text for p in doc.paragraphs)


def test_fara_elemente_iese_exact_ca_inainte():
    a = stil.document_din_gazda(GAZDA)
    capitol.construieste(a, capitol.alege_sectiuni(None, None), numar=5)
    b = stil.document_din_gazda(GAZDA)
    capitol.construieste(b, capitol.alege_sectiuni(None, None), numar=5, elemente=[])
    assert [p.text for p in a.paragraphs] == [p.text for p in b.paragraphs]


def test_lista_elemente_none_da_acelasi_rezultat_ca_lista_goala():
    """`elemente=None` (implicit) și `elemente=[]` explicit trebuie să fie
    echivalente — vezi și testul de mai sus, care le compară pe amândouă
    față de apelul fără parametrul deloc."""
    a = stil.document_din_gazda(GAZDA)
    capitol.construieste(a, capitol.alege_sectiuni(None, None), numar=5, elemente=None)
    b = stil.document_din_gazda(GAZDA)
    capitol.construieste(b, capitol.alege_sectiuni(None, None), numar=5, elemente=[])
    assert [p.text for p in a.paragraphs] == [p.text for p in b.paragraphs]


def test_mai_multe_elemente_pe_aceeasi_sectiune_se_numeroteaza_contiguu():
    """Doi „j” consecutivi sub aceeași secțiune, în ordinea din listă — nu
    trebuie să sară numere și nu trebuie să se amestece cu alte secțiuni."""
    doc = stil.document_din_gazda(GAZDA)
    e1 = capitol.Element(titlu="Primul", text="T1.", plasare="vanzari")
    e2 = capitol.Element(titlu="Al doilea", text="T2.", plasare="vanzari")
    capitol.construieste(doc, capitol.alege_sectiuni(None, ["contabilitate", "vanzari"]),
                         numar=5, elemente=[e1, e2])
    texte = [p.text for p in doc.paragraphs]
    assert "5.2.1. Primul" in texte
    assert "5.2.2. Al doilea" in texte
    assert texte.index("5.2.1. Primul") < texte.index("5.2.2. Al doilea")


def test_element_cu_sectiune_nefiltrata_apare_ca_sectiune_proprie_la_final():
    """`plasare` numește o secțiune validă din SECTIUNI, dar utilizatorul a
    filtrat-o afară din `sectiuni` — elementul n-are unde să stea ca
    sub-capitol, deci nu se pierde: cade la coada capitolului, ca secțiune
    proprie, alături de elementele explicit „propriu” (vezi comentariul din
    `capitol.construieste`)."""
    doc = stil.document_din_gazda(GAZDA)
    el = capitol.Element(titlu="Rapoarte suplimentare", text="Text.", plasare="mijloace-fixe")
    capitol.construieste(doc, capitol.alege_sectiuni(None, ["contabilitate", "vanzari"]),
                         numar=5, elemente=[el])
    h2 = [p.text for p in doc.paragraphs if p.style.name == "Heading 2"]
    assert h2[-1] == "5.11. Rapoarte suplimentare"


def test_elementele_cazute_la_finalul_capitolului_se_numeroteaza_in_ordinea_din_lista():
    """Un element „propriu” explicit și unul cu secțiune nefiltrată se
    amestecă în aceeași coadă, numerotate contiguu în ordinea din listă —
    nu grupate separat pe tipul motivului pentru care au ajuns acolo."""
    doc = stil.document_din_gazda(GAZDA)
    e1 = capitol.Element(titlu="Fără secțiune selectată", text="T1.", plasare="mijloace-fixe")
    e2 = capitol.Element(titlu="Propriu explicit", text="T2.", plasare="propriu")
    capitol.construieste(doc, capitol.alege_sectiuni(None, ["contabilitate"]),
                         numar=5, elemente=[e1, e2])
    h2 = [p.text for p in doc.paragraphs if p.style.name == "Heading 2"]
    assert h2[-2:] == ["5.11. Fără secțiune selectată", "5.12. Propriu explicit"]


def test_textul_elementului_nu_poate_inlocui_o_denumire_de_flux():
    """Chiar dacă titlul/textul elementului „seamănă” cu o denumire de flux,
    fraza de corelare nu se construiește niciodată din câmpurile elementului —
    doar din `SECTIUNI`. Cu un cod inexistent, fraza nu apare deloc, iar
    titlul/textul elementului (care ar putea fi confundate cu o denumire de
    tranzacție) nu ajunge nicăieri lângă cuvântul „flux”."""
    doc = stil.document_din_gazda(GAZDA)
    el = capitol.Element(
        titlu="Validare comandă client cu discount",
        text="Validare comandă client cu discount în trei pași.",
        plasare="vanzari",
        fluxuri_legate=["NU-EXISTA"],
    )
    capitol.construieste(doc, capitol.alege_sectiuni(None, ["vanzari"]), numar=5, elemente=[el])
    corp = "\n".join(p.text for p in doc.paragraphs)
    assert "corelat" not in corp.lower()


def test_element_fara_fluxuri_legate_nu_scrie_nicio_fraza_de_corelare():
    doc_fara = stil.document_din_gazda(GAZDA)
    doc_cu = stil.document_din_gazda(GAZDA)
    el_fara = capitol.Element(titlu="X", text="Text identic.", plasare="vanzari")
    el_cu = capitol.Element(titlu="X", text="Text identic.", plasare="vanzari", fluxuri_legate=[])
    capitol.construieste(doc_fara, capitol.alege_sectiuni(None, ["vanzari"]), numar=5, elemente=[el_fara])
    capitol.construieste(doc_cu, capitol.alege_sectiuni(None, ["vanzari"]), numar=5, elemente=[el_cu])
    assert [p.text for p in doc_fara.paragraphs] == [p.text for p in doc_cu.paragraphs]


def test_element_ca_subcapitol_apare_dupa_tabelul_de_fluxuri_al_sectiunii():
    """Regula din brief: elementul plasat sub o secțiune apare DUPĂ tabelul ei
    de fluxuri — nu doar undeva după titlul secțiunii. `Scop`, `Beneficii` și
    tabelul se randează primele. Testele de mai sus verifică doar poziția
    relativă la titlul secțiunii (`texte.index(...) > texte.index(...)`), care
    ar trece și pentru o implementare greșită ce ar scrie elementul imediat
    după titlu, înaintea tabelului — `doc.paragraphs` nici nu conține tabelul,
    deci nu poate proba asta. Aici verificăm ordinea reală a corpului
    (`_corp_in_ordine`), unde tabelul apare ca element `w:tbl` distinct."""
    doc = stil.document_din_gazda(GAZDA)
    el = capitol.Element(titlu="Aprobare comenzi pe niveluri", text="Text.", plasare="achizitii")
    capitol.construieste(doc, capitol.alege_sectiuni(None, ["contabilitate", "achizitii"]),
                         numar=5, elemente=[el])
    corp = _corp_in_ordine(doc)
    idx_titlu = next(i for i, (tip, txt) in enumerate(corp) if tip == "p" and txt == "5.2. Modulul Achiziții")
    idx_tabel = next(i for i, (tip, _) in enumerate(corp) if tip == "tbl" and i > idx_titlu)
    idx_element = next(i for i, (tip, txt) in enumerate(corp)
                        if tip == "p" and txt == "5.2.1. Aprobare comenzi pe niveluri")
    assert idx_element > idx_tabel


def test_fixture_gazda_produce_buline_reale_cu_numpr():
    """Dovadă că `GAZDA` e reprezentativă pentru ce are nevoie `stil.py`, nu
    doar un `.docx` gol: un capitol cu o secțiune care are `detaliere` (deci
    cheamă `stil.bullets`) trebuie să producă paragrafe „List Paragraph” cu
    `w:numPr` real, nu bulete fără glif. `stil._numid_pentru_buline` învață
    numId-ul redeschizând gazda de pe disc (`doc._cale_gazda`), nu din corpul
    golit în memorie — dacă fixture-ul ar fi înlocuit vreodată cu unul fără
    paragrafe „List Paragraph” reale în fișier, acest test trebuie să pice
    zgomotos, nu tăcut."""
    doc = stil.document_din_gazda(GAZDA)
    capitol.construieste(doc, capitol.alege_sectiuni(None, ["contabilitate"]), numar=5)
    liste = [p for p in doc.paragraphs if p.style is not None and p.style.name == "List Paragraph"]
    assert liste, "secțiunea 'contabilitate' trebuie să producă paragrafe cu bulină"
    assert all(stil._numid_din_paragraf(p) is not None for p in liste)
