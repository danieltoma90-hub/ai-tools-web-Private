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
