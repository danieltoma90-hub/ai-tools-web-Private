# -*- coding: utf-8 -*-
"""Teste pentru `/scop-core/catalog` — ce se poate bifa într-un document de scop.

Catalogul e o citire pură: cele zece secțiuni CORE (baza, aceeași la toți) și modulele adiacente
din repertoriu (MultiCash, Fleet, postcalcul…, bifate doar unde au obiect). Testele păzesc
contractul pe care se bazează ecranul: cheile de secțiune sunt exact cele din `charisma_core`,
fiecare element adiacent spune în ce capitol intră și vine cu variantele lui de text — iar
elementul bifat trebuie să treacă prin generare ca orice element suplimentar.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from auth import verify_token
from main import app
from skills.scop_core.charisma_core import SECTIUNI


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[verify_token] = lambda: {"id": "u1", "email": "t@totalsoft.ro"}
    yield
    app.dependency_overrides.pop(verify_token, None)


@pytest.mark.anyio
async def test_core_are_toate_sectiunile_standard(client):
    r = await client.get("/api/scop-core/catalog")
    assert r.status_code == 200, r.text
    chei = [s["cheie"] for s in r.json()["core"]]
    assert chei == [s.cheie for s in SECTIUNI]


@pytest.mark.anyio
async def test_sectiunile_core_spun_cat_contin(client):
    r = await client.get("/api/scop-core/catalog")
    configurare = next(s for s in r.json()["core"] if s["cheie"] == "configurare")
    assert configurare["fluxuri"] > 0 and configurare["puncte"] > 0
    assert configurare["titlu"] == SECTIUNI[0].titlu


@pytest.mark.anyio
async def test_adiacentele_vin_din_repertoriu_cu_capitol_si_variante(client):
    adiacente = (await client.get("/api/scop-core/catalog")).json()["adiacente"]
    assert adiacente, "repertoriul trebuie livrat împreună cu backendul"
    chei = {a["cheie"] for a in adiacente}
    assert "schimbul-de-fisiere-bancare-in-format-multicash" in chei

    multicash = next(a for a in adiacente
                     if a["cheie"] == "schimbul-de-fisiere-bancare-in-format-multicash")
    assert multicash["capitol"] == "financiar"
    assert len(multicash["variante"]) > 1, "același subiect, scris la mai mulți clienți"
    prima = multicash["variante"][0]
    assert prima["intro"] and prima["fluxuri"]
    assert {"cod", "flux", "presupune"} <= set(prima["fluxuri"][0])


@pytest.mark.anyio
async def test_capitolul_fiecarui_element_e_o_cheie_core_sau_propriu(client):
    chei_core = {s.cheie for s in SECTIUNI}
    for a in (await client.get("/api/scop-core/catalog")).json()["adiacente"]:
        assert a["capitol"] is None or a["capitol"] in chei_core, a["cheie"]


@pytest.mark.anyio
async def test_elementul_bifat_ajunge_in_document(client):
    """Drumul complet: un element din catalog, trimis înapoi ca element suplimentar, cu
    secțiunea lui gazdă debifată din restul documentului."""
    catalog = (await client.get("/api/scop-core/catalog")).json()
    el = next(a for a in catalog["adiacente"]
              if a["cheie"] == "schimbul-de-fisiere-bancare-in-format-multicash")
    varianta = el["variante"][0]

    with patch("routers.scop_core.upload_file", return_value="scop-core/u1/doc.docx"):
        r = await client.post("/api/scop-core/genereaza", json={
            "mod": "document",
            "config": {
                "client": {"nume": "Client Test"},
                "sectiuni_core": {"toate": False, "doar": [],
                                  "fara": ["mijloace-fixe", "analiza"]},
                "capitole": {"context": False, "abordare": False, "beneficii": False,
                             "acoperire": False, "delimitare": False, "premise": False,
                             "confirmari": False, "sinteza": True, "validare": False},
            },
            "continut": {
                "client": {"nume": "Client Test"},
                "suplimentare": [{
                    "titlu": el["denumire"], "intro": varianta["intro"],
                    "puncte": varianta["puncte"], "fluxuri": varianta["fluxuri"],
                    "nota": varianta["nota"], "in_modul": el["capitol"],
                    "incadrare": el["incadrare"],
                }],
            },
        })
    assert r.status_code == 200, r.text
    job = (await client.get(f"/api/scop-core/job/{r.json()['job_id']}")).json()
    assert job["status"] == "done"
    sumar = job["summary"]
    assert sumar["elemente_suplimentare_plasate"] == 1
    assert sumar["module_core"] == len(SECTIUNI) - 2, "cele două secțiuni debifate nu intră"
    titluri = " ".join(sumar["capitole"])
    assert "Soluția ofertată" in titluri


@pytest.mark.anyio
async def test_elementul_atasat_unei_sectiuni_excluse_e_422(client):
    """Mesajul deliberat al lui `scope.genereaza` — ecranul trebuie să împiedice combinația,
    dar dacă ajunge totuși aici, iese ca eroare clară, nu ca document tăcut incomplet."""
    r = await client.post("/api/scop-core/genereaza", json={
        "mod": "document",
        "config": {
            "client": {"nume": "Client Test"},
            "sectiuni_core": {"toate": False, "doar": [], "fara": ["financiar"]},
        },
        "continut": {
            "client": {"nume": "Client Test"},
            "suplimentare": [{"titlu": "MultiCash", "intro": "x", "in_modul": "financiar"}],
        },
    })
    assert r.status_code == 422
    assert "financiar" in r.json()["detail"]


@pytest.mark.anyio
async def test_verticalele_spun_cate_proiecte_si_module_au(client):
    c = (await client.get("/api/scop-core/catalog")).json()
    assert c["verticale"], "repertoriul are clienți din mai multe industrii"
    chei = {v["cheie"] for v in c["verticale"]}
    assert {"agricultura", "industrie-alimentara"} <= chei

    agro = next(v for v in c["verticale"] if v["cheie"] == "agricultura")
    assert agro["module"] > 0 and agro["proiecte"] >= 2
    assert len(agro["clienti"]) == agro["proiecte"]


@pytest.mark.anyio
async def test_nu_se_listeaza_verticale_fara_module(client):
    """O industrie la care n-am ofertat încă n-are ce selecta — nu apare în selector."""
    c = (await client.get("/api/scop-core/catalog")).json()
    for v in c["verticale"]:
        assert v["module"] > 0


@pytest.mark.anyio
async def test_elementul_spune_la_ce_verticale_a_fost_propus(client):
    c = (await client.get("/api/scop-core/catalog")).json()
    fiscal = next(a for a in c["adiacente"] if a["cheie"] == "conformitate-fiscala")
    assert "agricultura" in fiscal["verticale"]
    # Repetarea la mai mulți clienți din aceeași industrie e semnul că ține de industrie.
    assert fiscal["proiecte_pe_verticala"]["agricultura"] >= 2
    assert all(v["vertical"] in fiscal["verticale"] or not v["vertical"]
               for v in fiscal["variante"])


@pytest.mark.anyio
async def test_verticalele_elementului_acopera_variantele(client):
    c = (await client.get("/api/scop-core/catalog")).json()
    chei = {v["cheie"] for v in c["verticale"]}
    for a in c["adiacente"]:
        assert set(a["verticale"]) <= chei, a["cheie"]
        assert sum(a["proiecte_pe_verticala"].values()) <= len(a["variante"])
