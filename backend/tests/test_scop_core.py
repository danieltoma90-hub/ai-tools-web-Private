# -*- coding: utf-8 -*-
"""Teste pentru routerul HTTP al scop_core (Task 5).

Urmăresc îndeaproape tiparul din `test_scenarii.py`: `verify_token` suprascris
prin `app.dependency_overrides`, `download_upload`/`upload_file` mock-uite la
nivelul modulului routerului (nu al lui `storage`), iar pipeline-ul propriu-zis
(`propune_job`/`run_scop_core_pipeline`) mock-uit ca să izoleze routerul de
logica deja testată în `test_scop_core_pipeline.py`.

Testul `test_gazda_reala_ramane_neschimbata_dupa_fluxul_prin_router` e
excepția: acolo `download_upload` e înlocuit cu o copie REALĂ a fixture-ului
(nu un mock steril), tocmai ca să verifice — la nivel de router, nu doar de
pipeline — că fișierul gazdă original nu e niciodată atins.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import tempfile
from pathlib import Path as _P
from unittest.mock import patch

import pytest
from docx import Document
from openpyxl import Workbook

from auth import verify_token
from main import app

GAZDA_FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "gazda_reala_anonimizata.docx"


def _hash(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _docx_tempfile(paragrafe=("Text simplu.",)) -> _P:
    fd, name = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    d = Document()
    for text in paragrafe:
        d.add_paragraph(text)
    d.save(name)
    return _P(name)


def _copie_gazda_reala() -> _P:
    fd, name = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    _P(name).write_bytes(GAZDA_FIXTURE.read_bytes())
    return _P(name)


def _xlsx_redenumit_docx() -> _P:
    """Un .xlsx real, salvat sub extensia .docx — reproduce exact cazul din
    itemul 4: un pachet zip valid, dar de alt tip de conținut. python-docx
    ridică `ValueError` pentru el, cu calea temporară internă a serverului
    inclusă în mesaj — exact ce nu are voie să ajungă la utilizator."""
    wb = Workbook()
    wb.active["A1"] = "nu e word"
    fd, name = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    wb.save(name)
    return _P(name)


@pytest.fixture(autouse=True)
def _auth_override():
    app.dependency_overrides[verify_token] = lambda: {"id": "u1", "email": "u1@test.ro"}
    yield
    app.dependency_overrides.clear()


AUTH = {"Authorization": "Bearer fake"}


# --- /scop-core/propune -----------------------------------------------------

async def test_propune_fara_autentificare_da_401(client):
    app.dependency_overrides.clear()
    response = await client.post(
        "/api/scop-core/propune",
        json={"storage_path": "scop-core/x.docx", "filename": "supliment.docx"},
    )
    assert response.status_code == 401


async def test_propune_extensie_gresita_da_422(client):
    response = await client.post(
        "/api/scop-core/propune",
        json={"storage_path": "scop-core/x.pdf", "filename": "supliment.pdf"},
        headers=AUTH,
    )
    assert response.status_code == 422


async def test_propune_upload_lipsa_da_422(client):
    with patch("routers.scop_core.download_upload", side_effect=Exception("object not found")):
        response = await client.post(
            "/api/scop-core/propune",
            json={"storage_path": "scop-core/lipsa.docx", "filename": "supliment.docx"},
            headers=AUTH,
        )
    assert response.status_code == 422
    assert "nu a fost găsit" in response.json()["detail"]


async def test_propune_fara_cheie_api_da_500(client, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    response = await client.post(
        "/api/scop-core/propune",
        json={"storage_path": "scop-core/x.docx", "filename": "supliment.docx"},
        headers=AUTH,
    )
    assert response.status_code == 500
    assert "MISTRAL_API_KEY" in response.json()["detail"]


async def test_propune_succes_intoarce_propunere_id_si_elemente(client, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    supliment = _docx_tempfile()
    elemente_asteptate = [
        {"titlu": "Integrare cântar", "text": "Text extras.", "plasare": "vanzari",
         "fluxuri_legate": ["V2"]},
    ]

    async def fals_propune(path):
        assert path == supliment
        return elemente_asteptate

    with patch("routers.scop_core.download_upload", return_value=supliment), \
         patch("routers.scop_core.propune_job", side_effect=fals_propune):
        response = await client.post(
            "/api/scop-core/propune",
            json={"storage_path": "scop-core/x.docx", "filename": "supliment.docx"},
            headers=AUTH,
        )
    assert response.status_code == 200
    body = response.json()
    assert "propunere_id" in body and body["propunere_id"]
    assert body["elemente"] == elemente_asteptate
    # fisierul temporar descarcat trebuie curatat, cu succes sau fara
    assert not supliment.exists()


async def test_propune_eroare_model_da_502(client, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    supliment = _docx_tempfile()

    async def fals_propune(path):
        raise ValueError("Răspunsul modelului nu este JSON valid")

    with patch("routers.scop_core.download_upload", return_value=supliment), \
         patch("routers.scop_core.propune_job", side_effect=fals_propune):
        response = await client.post(
            "/api/scop-core/propune",
            json={"storage_path": "scop-core/x.docx", "filename": "supliment.docx"},
            headers=AUTH,
        )
    assert response.status_code == 502
    assert not supliment.exists()


# --- /scop-core/genereaza ----------------------------------------------------

async def test_propune_docx_corupt_da_422(client, monkeypatch):
    """Un fisier cu extensia .docx dar continut nevalid (python-docx nu poate
    deschide pachetul) trebuie tratat ca input invalid al utilizatorului —
    422 — nu ca o eroare de server nesurprinsa."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    fd, name = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    _P(name).write_bytes(b"nu sunt un docx valid")
    supliment = _P(name)

    with patch("routers.scop_core.download_upload", return_value=supliment):
        response = await client.post(
            "/api/scop-core/propune",
            json={"storage_path": "scop-core/x.docx", "filename": "supliment.docx"},
            headers=AUTH,
        )
    assert response.status_code == 422
    assert not supliment.exists()


async def test_propune_xlsx_redenumit_docx_da_422_fara_cale_in_mesaj(client, monkeypatch):
    """Non-regresie pentru itemul 4: un .xlsx redenumit .docx trecea prin
    `except (ValueError, RuntimeError)` — categoria de eroare model/rețea —
    și ajungea 502 cu calea temporară a serverului scursă în mesaj. Acum
    `DocumentInvalid` (ridicat de `stil.deschide_docx`) e prins separat,
    înaintea acelui catch, cu 422 și mesaj curat."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    supliment = _xlsx_redenumit_docx()

    with patch("routers.scop_core.download_upload", return_value=supliment):
        response = await client.post(
            "/api/scop-core/propune",
            json={"storage_path": "scop-core/x.docx", "filename": "supliment.docx"},
            headers=AUTH,
        )
    detail = response.json()["detail"]
    assert response.status_code == 422
    assert not supliment.exists()
    assert str(supliment) not in detail
    assert supliment.name not in detail


async def test_genereaza_fara_autentificare_da_401(client):
    app.dependency_overrides.clear()
    response = await client.post(
        "/api/scop-core/genereaza",
        json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
              "client": "ACME", "elemente": [], "insereaza": False},
    )
    assert response.status_code == 401


async def test_genereaza_extensie_gresita_da_422(client):
    response = await client.post(
        "/api/scop-core/genereaza",
        json={"gazda_storage_path": "scop-core/g.pdf", "gazda_filename": "gazda.pdf",
              "client": "ACME", "elemente": [], "insereaza": False},
        headers=AUTH,
    )
    assert response.status_code == 422


async def test_genereaza_corp_malformat_da_422_nu_500(client):
    """`elemente` care nu e o listă de dicturi trebuie respins de FastAPI/Pydantic
    la nivel de schema — nu trebuie sa ajunga la pipeline si sa produca 500."""
    response = await client.post(
        "/api/scop-core/genereaza",
        json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
              "client": "ACME", "elemente": "nu sunt o lista", "insereaza": False},
        headers=AUTH,
    )
    assert response.status_code == 422


async def test_genereaza_xlsx_redenumit_docx_da_422_fara_cale_in_mesaj(client):
    """Non-regresie pentru itemul 4, pe cealaltă cale: `/genereaza` pornea
    anterior jobul de fundal necondiționat — un .xlsx redenumit .docx trecea
    de verificarea de extensie, iar `stil.document_din_gazda` eșua abia mai
    târziu, în job, cu mesaj tehnic ajuns tel-quel în `jobs.fail` (deci și în
    fața utilizatorului). Acum `valideaza_docx` verifică sincron, înainte de
    a porni jobul — un fișier invalid dă 422 imediat, ca la `/propune`."""
    gazda = _xlsx_redenumit_docx()

    with patch("routers.scop_core.download_upload", return_value=gazda):
        response = await client.post(
            "/api/scop-core/genereaza",
            json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
                  "client": "ACME", "elemente": [], "insereaza": False},
            headers=AUTH,
        )
    detail = response.json()["detail"]
    assert response.status_code == 422
    assert not gazda.exists()
    assert str(gazda) not in detail
    assert gazda.name not in detail


async def test_genereaza_upload_lipsa_da_422(client):
    with patch("routers.scop_core.download_upload", side_effect=Exception("object not found")):
        response = await client.post(
            "/api/scop-core/genereaza",
            json={"gazda_storage_path": "scop-core/lipsa.docx", "gazda_filename": "gazda.docx",
                  "client": "ACME", "elemente": [], "insereaza": False},
            headers=AUTH,
        )
    assert response.status_code == 422
    assert "nu a fost găsit" in response.json()["detail"]


async def test_genereaza_cu_elemente_goale_functioneaza_fara_propune(client):
    gazda = _docx_tempfile()

    async def fals_pipeline(gazda_path, client, elemente, insereaza_in_gazda,
                            delimitari=None, curata_antet_subsol=False, on_step=None):
        assert elemente == []
        capitol_path = _docx_tempfile(("Capitol CORE",))
        return capitol_path, None, {
            "sectiuni": 10, "fluxuri": 47, "elemente_primite": 0, "elemente_plasate": 0,
            "elemente_pe_sectiune": 0, "elemente_proprii": 0, "elemente_respinse": 0,
            "gazda_inserata": False, "avertisment": "",
        }

    with patch("routers.scop_core.download_upload", return_value=gazda), \
         patch("routers.scop_core.run_scop_core_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/capitol.docx"):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
                  "client": "ACME", "elemente": [], "insereaza": False},
            headers=AUTH,
        )
    assert gen_res.status_code == 200
    job_id = gen_res.json()["job_id"]

    job_res = await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)
    assert job_res.status_code == 200
    job = job_res.json()
    assert job["status"] == "done"
    assert job["docx_b64"]
    assert job["gazda_b64"] is None
    assert job["cuprins_avertisment"] is None


async def test_genereaza_forwardeaza_delimitari_si_curata_antet_subsol_catre_pipeline(client):
    """`delimitari` și `curata_antet_subsol` din corpul cererii trebuie să
    ajungă neschimbate la `run_scop_core_pipeline` — routerul nu le validează
    el însuși, doar le trece mai departe (aceeași filosofie ca la `elemente`)."""
    gazda = _docx_tempfile()
    primit: dict = {}

    async def fals_pipeline(gazda_path, client, elemente, insereaza_in_gazda,
                            delimitari=None, curata_antet_subsol=False, on_step=None):
        primit["delimitari"] = delimitari
        primit["curata_antet_subsol"] = curata_antet_subsol
        capitol_path = _docx_tempfile(("Capitol CORE",))
        return capitol_path, None, {
            "sectiuni": 10, "fluxuri": 47, "elemente_primite": 0, "elemente_plasate": 0,
            "elemente_pe_sectiune": 0, "elemente_proprii": 0, "elemente_respinse": 0,
            "delimitari_primite": 1, "delimitari_plasate": 1, "delimitari_respinse": 0,
            "gazda_inserata": False, "antet_subsol_curatat": True, "antet_subsol_avertisment": "",
            "avertisment": "",
        }

    delimitari = [{"element": "Migrarea istoricului", "precizare": "Nu face obiectul acestui scop."}]
    with patch("routers.scop_core.download_upload", return_value=gazda), \
         patch("routers.scop_core.run_scop_core_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/capitol.docx"):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
                  "client": "ACME", "elemente": [], "delimitari": delimitari,
                  "insereaza": False, "curata_antet_subsol": True},
            headers=AUTH,
        )
    assert gen_res.status_code == 200
    job_id = gen_res.json()["job_id"]
    await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)

    assert primit["delimitari"] == delimitari
    assert primit["curata_antet_subsol"] is True


async def test_genereaza_fara_delimitari_si_curata_antet_subsol_foloseste_implicit(client):
    """Corpul cererii poate omite complet `delimitari`/`curata_antet_subsol` —
    modelul Pydantic are valori implicite (`[]`/`False`), la fel ca `elemente`/
    `insereaza` deja acoperite mai sus."""
    gazda = _docx_tempfile()
    primit: dict = {}

    async def fals_pipeline(gazda_path, client, elemente, insereaza_in_gazda,
                            delimitari=None, curata_antet_subsol=False, on_step=None):
        primit["delimitari"] = delimitari
        primit["curata_antet_subsol"] = curata_antet_subsol
        capitol_path = _docx_tempfile(("Capitol CORE",))
        return capitol_path, None, {
            "sectiuni": 10, "fluxuri": 47, "elemente_primite": 0, "elemente_plasate": 0,
            "elemente_pe_sectiune": 0, "elemente_proprii": 0, "elemente_respinse": 0,
            "gazda_inserata": False, "avertisment": "",
        }

    with patch("routers.scop_core.download_upload", return_value=gazda), \
         patch("routers.scop_core.run_scop_core_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/capitol.docx"):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
                  "client": "ACME", "elemente": [], "insereaza": False},
            headers=AUTH,
        )
    assert gen_res.status_code == 200
    job_id = gen_res.json()["job_id"]
    await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)

    assert primit["delimitari"] == []
    assert primit["curata_antet_subsol"] is False


async def test_genereaza_cu_insereaza_true_produce_doua_artefacte(client):
    gazda = _docx_tempfile()

    async def fals_pipeline(gazda_path, client, elemente, insereaza_in_gazda,
                            delimitari=None, curata_antet_subsol=False, on_step=None):
        assert insereaza_in_gazda is True
        capitol_path = _docx_tempfile(("Capitol CORE",))
        gazda_out = _docx_tempfile(("Gazda cu capitol",))
        return capitol_path, gazda_out, {
            "sectiuni": 10, "fluxuri": 47, "elemente_primite": 1, "elemente_plasate": 1,
            "elemente_pe_sectiune": 1, "elemente_proprii": 0, "elemente_respinse": 0,
            "gazda_inserata": True, "avertisment": "",
        }

    def fals_upload(path, tool, filename, user_email):
        assert tool == "scop-core"
        return f"scop-core/u1/{filename}"

    with patch("routers.scop_core.download_upload", return_value=gazda), \
         patch("routers.scop_core.run_scop_core_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", side_effect=fals_upload):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
                  "client": "ACME",
                  "elemente": [{"titlu": "X", "text": "Y", "plasare": "vanzari", "fluxuri_legate": []}],
                  "insereaza": True},
            headers=AUTH,
        )
    assert gen_res.status_code == 200
    job_id = gen_res.json()["job_id"]

    job_res = await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)
    job = job_res.json()
    assert job["status"] == "done"
    assert job["docx_b64"]
    assert job["storage_path"]
    assert job["gazda_b64"]
    assert job["gazda_storage_path"]
    assert job["summary"]["gazda_inserata"] is True
    assert job["cuprins_avertisment"] is not None
    assert "cuprins" in job["cuprins_avertisment"].lower() or "Cuprins" in job["cuprins_avertisment"]


async def test_genereaza_esec_la_inserare_nu_are_avertisment_cuprins(client):
    """Daca insereaza a fost cerut dar pipeline-ul n-a produs gazda (a esuat),
    nu exista un document cu Cuprins invechit de semnalat."""
    gazda = _docx_tempfile()

    async def fals_pipeline(gazda_path, client, elemente, insereaza_in_gazda,
                            delimitari=None, curata_antet_subsol=False, on_step=None):
        capitol_path = _docx_tempfile(("Capitol CORE",))
        return capitol_path, None, {
            "sectiuni": 10, "fluxuri": 47, "elemente_primite": 0, "elemente_plasate": 0,
            "elemente_pe_sectiune": 0, "elemente_proprii": 0, "elemente_respinse": 0,
            "gazda_inserata": False, "avertisment": "Inserarea capitolului în documentul gazdă a eșuat: x",
        }

    with patch("routers.scop_core.download_upload", return_value=gazda), \
         patch("routers.scop_core.run_scop_core_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/capitol.docx"):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
                  "client": "ACME", "elemente": [], "insereaza": True},
            headers=AUTH,
        )
    job_id = gen_res.json()["job_id"]
    job_res = await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)
    job = job_res.json()
    assert job["status"] == "done"
    assert job["gazda_b64"] is None
    assert job["cuprins_avertisment"] is None


async def test_genereaza_esec_pipeline_marcheaza_jobul_ca_eroare(client):
    gazda = _docx_tempfile()

    async def fals_pipeline(*a, **kw):
        raise RuntimeError("pipeline stricat")

    with patch("routers.scop_core.download_upload", return_value=gazda), \
         patch("routers.scop_core.run_scop_core_pipeline", side_effect=fals_pipeline):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
                  "client": "ACME", "elemente": [], "insereaza": False},
            headers=AUTH,
        )
    job_id = gen_res.json()["job_id"]
    job_res = await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)
    job = job_res.json()
    assert job["status"] == "error"
    # fisierul gazda descarcat local trebuie curatat si pe calea de esec
    assert not gazda.exists()


async def test_job_inexistent_da_404(client):
    response = await client.get("/api/scop-core/job/nu-exista", headers=AUTH)
    assert response.status_code == 404


async def test_gazda_reala_ramane_neschimbata_dupa_fluxul_prin_router(client):
    """Non-negociabilul din brief, verificat aici la nivel de router: fisierul
    gazda original (fixture-ul real anonimizat) nu e niciodata atins, chiar
    daca `download_upload` e simulat cu o copie reala a lui, nu un mock steril."""
    hash_inainte = _hash(GAZDA_FIXTURE)

    with patch("routers.scop_core.download_upload", side_effect=lambda sp: _copie_gazda_reala()), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/x.docx"):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"gazda_storage_path": "scop-core/g.docx", "gazda_filename": "gazda.docx",
                  "client": "ACME", "elemente": [], "insereaza": True},
            headers=AUTH,
        )
    job_id = gen_res.json()["job_id"]
    job_res = await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)
    job = job_res.json()
    assert job["status"] == "done"
    assert _hash(GAZDA_FIXTURE) == hash_inainte


# --- mod „capitol” — neregresie explicită (Task 4) --------------------------

async def test_genereaza_mod_capitol_explicit_functioneaza_ca_implicitul(client):
    """Trimiterea explicită a `"mod": "capitol"` trebuie să producă exact
    același răspuns ca lipsa completă a câmpului `mod` (comportamentul
    dinaintea Task 4) — non-regresie pentru clienții care încep să-l trimită."""
    gazda = _docx_tempfile()

    async def fals_pipeline(gazda_path, client, elemente, insereaza_in_gazda,
                            delimitari=None, curata_antet_subsol=False, on_step=None):
        capitol_path = _docx_tempfile(("Capitol CORE",))
        return capitol_path, None, {
            "sectiuni": 10, "fluxuri": 47, "elemente_primite": 0, "elemente_plasate": 0,
            "elemente_pe_sectiune": 0, "elemente_proprii": 0, "elemente_respinse": 0,
            "gazda_inserata": False, "avertisment": "",
        }

    with patch("routers.scop_core.download_upload", return_value=gazda), \
         patch("routers.scop_core.run_scop_core_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/capitol.docx"):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "capitol", "gazda_storage_path": "scop-core/g.docx",
                  "gazda_filename": "gazda.docx", "client": "ACME", "elemente": [],
                  "insereaza": False},
            headers=AUTH,
        )
    assert gen_res.status_code == 200
    job_id = gen_res.json()["job_id"]
    job_res = await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)
    job = job_res.json()
    assert job["status"] == "done"
    assert job["docx_b64"]
    assert job["gazda_b64"] is None
    assert job["cuprins_avertisment"] is None


async def test_genereaza_capitol_fara_gazda_da_422(client):
    """`gazda_storage_path`/`gazda_filename` au devenit opționale la nivel de
    Pydantic (ca modul „document” să poată rula fără gazdă) — dar pentru
    modul „capitol” rămân obligatorii, verificate acum manual în router."""
    response = await client.post(
        "/api/scop-core/genereaza",
        json={"client": "ACME", "elemente": [], "insereaza": False},
        headers=AUTH,
    )
    assert response.status_code == 422
    assert "obligatoriu" in response.json()["detail"]


async def test_genereaza_mod_necunoscut_da_422(client):
    response = await client.post(
        "/api/scop-core/genereaza",
        json={"mod": "nu-exista-asa-ceva", "gazda_storage_path": "scop-core/g.docx",
              "gazda_filename": "gazda.docx"},
        headers=AUTH,
    )
    assert response.status_code == 422


# --- mod „document” (Task 4) -------------------------------------------------

CONFIG_MINIM_DOC = {
    "document": {"titlu": "Descrierea soluției ofertate"},
    "document_frate": {"exista": False},
    "sectiuni_core": {"toate": True},
    "capitole": {"context": True, "abordare": True, "beneficii": True, "acoperire": True,
                "delimitare": True, "premise": True, "confirmari": True, "sinteza": True,
                "validare": True},
    "stil": {"antet": "Antet de test"},
}


def _sumar_document_fals() -> dict:
    return {
        "capitole_scrise": 10, "capitole": ["1. Scopul documentului"], "module_core": 10,
        "elemente_suplimentare_primite": 0, "elemente_suplimentare_plasate": 0,
        "elemente_suplimentare_respinse": 0, "cerinte_primite": 0, "cerinte_plasate": 0,
        "cerinte_respinse": 0, "cerinte_pe_incadrare": {"A": 0, "P": 0, "D": 0, "N": 0},
        "delimitare_randuri_plasate": 0, "delimitare_randuri_respinse": 0,
        "flux_operational_randuri_plasate": 0, "flux_operational_randuri_respinse": 0,
        "confirmari_plasate": 0, "confirmari_respinse": 0, "avertisment": "",
    }


async def test_genereaza_document_fara_autentificare_da_401(client):
    app.dependency_overrides.clear()
    response = await client.post(
        "/api/scop-core/genereaza",
        json={"mod": "document", "config": CONFIG_MINIM_DOC, "continut": {}},
    )
    assert response.status_code == 401


async def test_genereaza_document_fara_gazda_produce_documentul(client):
    """Documentul-gazdă e opțional la modul „document" — funcționează fără el."""
    documentul = _docx_tempfile(("Document de scop",))

    async def fals_pipeline(gazda_path, cfg, continut, on_step=None):
        assert gazda_path is None
        return documentul, _sumar_document_fals()

    with patch("routers.scop_core.run_scope_document_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/doc.docx") as fals_upload:
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "config": CONFIG_MINIM_DOC,
                  "continut": {"client": {"nume": "ACME SRL"}}},
            headers=AUTH,
        )
    assert gen_res.status_code == 200
    fals_upload.assert_called_once()
    job_id = gen_res.json()["job_id"]

    job_res = await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)
    job = job_res.json()
    assert job["status"] == "done"
    assert job["docx_b64"]
    assert job["storage_path"] == "scop-core/u1/doc.docx"
    assert job["summary"]["capitole_scrise"] == 10
    assert job["gazda_filename"] is None
    assert job["gazda_b64"] is None
    assert job["gazda_storage_path"] is None
    assert job["cuprins_avertisment"] is None
    # fisierul temporar produs de pipeline trebuie curatat dupa upload
    assert not documentul.exists()


async def test_genereaza_document_fara_config_sau_continut_functioneaza(client):
    """`config`/`continut` lipsă complet (nu doar goale) nu trebuie să pice —
    routerul le tratează ca dicturi goale, la fel ca pipeline-ul."""
    documentul = _docx_tempfile(("Document minimal",))

    async def fals_pipeline(gazda_path, cfg, continut, on_step=None):
        assert cfg == {}
        assert continut == {}
        return documentul, _sumar_document_fals()

    with patch("routers.scop_core.run_scope_document_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/doc.docx"):
        gen_res = await client.post(
            "/api/scop-core/genereaza", json={"mod": "document"}, headers=AUTH,
        )
    assert gen_res.status_code == 200


async def test_genereaza_document_cu_gazda_produce_documentul(client):
    gazda = _docx_tempfile()
    documentul = _docx_tempfile(("Document cu stiluri de gazdă",))

    async def fals_pipeline(gazda_path, cfg, continut, on_step=None):
        assert gazda_path == gazda
        return documentul, _sumar_document_fals()

    with patch("routers.scop_core.download_upload", return_value=gazda), \
         patch("routers.scop_core.run_scope_document_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/doc.docx"):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "gazda_storage_path": "scop-core/g.docx",
                  "gazda_filename": "gazda.docx", "config": CONFIG_MINIM_DOC, "continut": {}},
            headers=AUTH,
        )
    assert gen_res.status_code == 200
    # gazda descarcata local trebuie curatata dupa folosire
    assert not gazda.exists()


async def test_genereaza_document_doar_storage_path_fara_filename_da_422(client):
    response = await client.post(
        "/api/scop-core/genereaza",
        json={"mod": "document", "gazda_storage_path": "scop-core/g.docx"},
        headers=AUTH,
    )
    assert response.status_code == 422


async def test_genereaza_document_extensie_gresita_da_422(client):
    response = await client.post(
        "/api/scop-core/genereaza",
        json={"mod": "document", "gazda_storage_path": "scop-core/g.pdf",
              "gazda_filename": "gazda.pdf"},
        headers=AUTH,
    )
    assert response.status_code == 422


async def test_genereaza_document_upload_gazda_lipsa_da_422(client):
    with patch("routers.scop_core.download_upload", side_effect=Exception("object not found")):
        response = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "gazda_storage_path": "scop-core/lipsa.docx",
                  "gazda_filename": "gazda.docx"},
            headers=AUTH,
        )
    assert response.status_code == 422
    assert "nu a fost găsit" in response.json()["detail"]


async def test_genereaza_document_xlsx_redenumit_docx_da_422_fara_cale_in_mesaj(client):
    gazda = _xlsx_redenumit_docx()
    with patch("routers.scop_core.download_upload", return_value=gazda):
        response = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "gazda_storage_path": "scop-core/g.docx",
                  "gazda_filename": "gazda.docx"},
            headers=AUTH,
        )
    detail = response.json()["detail"]
    assert response.status_code == 422
    assert not gazda.exists()
    assert str(gazda) not in detail
    assert gazda.name not in detail


async def test_genereaza_document_in_modul_exclus_da_422_cu_mesaj_actionabil(client):
    """Eroarea deliberată a lui `scope.genereaza` (element atașat unui modul
    exclus) trebuie să ajungă ca 422 cu mesaj clar — NU ca job „error”, pentru
    că pierderea tăcută a conținutului dintr-o ofertă comercială e mai gravă
    decât un cod HTTP."""
    async def fals_pipeline(gazda_path, cfg, continut, on_step=None):
        raise ValueError("Elemente atașate unor module care nu intră în document: financiar")

    with patch("routers.scop_core.run_scope_document_pipeline", side_effect=fals_pipeline):
        response = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "config": CONFIG_MINIM_DOC,
                  "continut": {"suplimentare": [{"titlu": "X", "in_modul": "financiar"}]}},
            headers=AUTH,
        )
    assert response.status_code == 422
    assert "financiar" in response.json()["detail"]


async def test_genereaza_document_ordine_cap4_incompleta_da_422(client):
    async def fals_pipeline(gazda_path, cfg, continut, on_step=None):
        raise ValueError("Elemente absente din ordinea declarată: financiar")

    with patch("routers.scop_core.run_scope_document_pipeline", side_effect=fals_pipeline):
        response = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "config": CONFIG_MINIM_DOC,
                  "continut": {"ordine_cap4": ["contabilitate"]}},
            headers=AUTH,
        )
    assert response.status_code == 422
    assert "financiar" in response.json()["detail"]


async def test_genereaza_document_eroare_neasteptata_da_500_fara_detaliu_tehnic(client):
    async def fals_pipeline(gazda_path, cfg, continut, on_step=None):
        raise RuntimeError(r"eroare internă cu cale C:\Users\server\temp\secret.docx")

    with patch("routers.scop_core.run_scope_document_pipeline", side_effect=fals_pipeline):
        response = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "config": CONFIG_MINIM_DOC, "continut": {}},
            headers=AUTH,
        )
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "secret.docx" not in detail
    assert "C:\\" not in detail


async def test_genereaza_document_upload_esuat_da_500(client):
    documentul = _docx_tempfile(("Document",))

    async def fals_pipeline(gazda_path, cfg, continut, on_step=None):
        return documentul, _sumar_document_fals()

    with patch("routers.scop_core.run_scope_document_pipeline", side_effect=fals_pipeline), \
         patch("routers.scop_core.upload_file", side_effect=Exception("storage indisponibil")):
        response = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "config": CONFIG_MINIM_DOC, "continut": {}},
            headers=AUTH,
        )
    assert response.status_code == 500
    # fisierul temporar produs de pipeline trebuie curatat chiar daca uploadul pica
    assert not documentul.exists()


async def test_genereaza_document_fisier_gazda_curatat_la_esecul_pipelineului(client):
    """Gazda descărcată local (fișier temporar pe server) trebuie ștearsă și
    pe calea de eșec — nu doar la succes."""
    gazda = _docx_tempfile()

    async def fals_pipeline(gazda_path, cfg, continut, on_step=None):
        raise ValueError("configurare invalidă")

    with patch("routers.scop_core.download_upload", return_value=gazda), \
         patch("routers.scop_core.run_scope_document_pipeline", side_effect=fals_pipeline):
        response = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "gazda_storage_path": "scop-core/g.docx",
                  "gazda_filename": "gazda.docx", "config": CONFIG_MINIM_DOC, "continut": {}},
            headers=AUTH,
        )
    assert response.status_code == 422
    assert not gazda.exists()


async def test_genereaza_document_gazda_reala_ramane_neschimbata(client):
    """Non-negociabilul din brief, la modul „document”: documentul-gazdă
    original nu e niciodată atins — verificat cu pipeline-ul REAL (nu mock-uit),
    la fel ca testul echivalent al modului „capitol” de mai sus."""
    hash_inainte = _hash(GAZDA_FIXTURE)

    with patch("routers.scop_core.download_upload", side_effect=lambda sp: _copie_gazda_reala()), \
         patch("routers.scop_core.upload_file", return_value="scop-core/u1/doc.docx"):
        gen_res = await client.post(
            "/api/scop-core/genereaza",
            json={"mod": "document", "gazda_storage_path": "scop-core/g.docx",
                  "gazda_filename": "gazda.docx", "config": CONFIG_MINIM_DOC,
                  "continut": {"client": {"nume": "ACME SRL"}}},
            headers=AUTH,
        )
    assert gen_res.status_code == 200
    job_id = gen_res.json()["job_id"]
    job_res = await client.get(f"/api/scop-core/job/{job_id}", headers=AUTH)
    job = job_res.json()
    assert job["status"] == "done"
    assert _hash(GAZDA_FIXTURE) == hash_inainte
