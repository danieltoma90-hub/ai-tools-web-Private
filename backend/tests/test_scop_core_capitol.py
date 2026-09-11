# -*- coding: utf-8 -*-
"""Teste pentru elementele suplimentare din capitolul CORE (Task 2).

`GAZDA` e un document minimal, generat cu python-docx implicit (fără nicio
personalizare), și comis în acest repo — nu documentul real de la client, care
trăiește într-un alt repo (`d:\\AI_Claude`) și nu trebuie să fie o dependență a
suitei de teste a acestui repo. Un `Document()` gol are deja stilurile de care
`stil.py`/`capitol.py` au nevoie (Heading 1-9, "Table Grid", "List Paragraph"),
deci ajunge pentru tot ce testează acest fișier: poziția și numerotarea
elementelor, nu fidelitatea vizuală față de o gazdă reală (asta e verificată
separat, cu gazda reală, în testele portate din skill-ul CLI).
"""
from __future__ import annotations

import pathlib

from skills.scop_core import capitol, stil
from skills.scop_core.charisma_core import SECTIUNI

GAZDA = pathlib.Path(__file__).resolve().parent / "fixtures" / "gazda_minima.docx"


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
