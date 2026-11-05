# -*- coding: utf-8 -*-
"""Teste pentru `/scop-core/minute` — minutele de ședință confruntate cu documentul de scop.

Același tipar ca în `test_scop_core.py`: `verify_token` suprascris, `download_upload` mock-uit la
nivelul modulului routerului. Spre deosebire de `/propune`, aici nu există apel de model, deci
testele parcurg pipeline-ul real — e deterministic și rulează în milisecunde.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from docx import Document

from auth import verify_token
from main import app


def _json_tempfile(continut: dict) -> Path:
    fd, name = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    Path(name).write_text(json.dumps(continut, ensure_ascii=False), encoding="utf-8")
    return Path(name)


def _docx_tempfile(paragrafe) -> Path:
    fd, name = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    d = Document()
    for text in paragrafe:
        d.add_paragraph(text)
    d.save(name)
    return Path(name)


MINUTA = {
    "sectiuni": [{"titlu": "Integrare", "blocuri": [{"type": "bullets", "items": [
        "Integrarea cu WMS nu e în scop; cere analiză separată.",
        "Se oferă preluarea comenzii de la magazin prin API CIRA.",
    ]}]}],
}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[verify_token] = lambda: {"id": "u1", "email": "t@totalsoft.ro"}
    yield
    app.dependency_overrides.pop(verify_token, None)


@pytest.mark.anyio
async def test_fara_scop_intoarce_doar_punctele(client):
    minuta = _json_tempfile(MINUTA)
    with patch("routers.scop_core.download_upload", return_value=minuta):
        r = await client.post("/api/scop-core/minute", json={
            "minute": [{"storage_path": "scop-core/a.json", "filename": "a.json"}]})
    assert r.status_code == 200, r.text
    corp = r.json()
    assert corp["sumar"]["puncte"] == 2
    assert corp["raport"] == []
    assert "WMS" in corp["elemente"][0]["text"]


@pytest.mark.anyio
async def test_cu_scop_raporteaza_ce_a_ramas_in_document(client):
    minuta = _json_tempfile(MINUTA)
    scop = _docx_tempfile([
        "11.1. Infrastructura",
        "Conectivitatea cu aplicatia de WMS Priority Software, pentru schimbul de documente.",
    ])
    cai = {"scop-core/a.json": minuta, "scop-core/b.docx": scop}
    with patch("routers.scop_core.download_upload", side_effect=lambda p: cai[p]):
        r = await client.post("/api/scop-core/minute", json={
            "minute": [{"storage_path": "scop-core/a.json", "filename": "a.json"}],
            "scop_storage_path": "scop-core/b.docx",
            "scop_filename": "b.docx",
        })
    assert r.status_code == 200, r.text
    verdicte = {p["verdict"] for p in r.json()["raport"]}
    assert "de_scos" in verdicte, "WMS e cerut afară, dar documentul încă îl oferă"


@pytest.mark.anyio
async def test_extensie_gresita_e_422(client):
    r = await client.post("/api/scop-core/minute", json={
        "minute": [{"storage_path": "scop-core/a.xlsx", "filename": "a.xlsx"}]})
    assert r.status_code == 422
    assert ".json" in r.json()["detail"]


@pytest.mark.anyio
async def test_fara_minute_e_422(client):
    r = await client.post("/api/scop-core/minute", json={"minute": []})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_scop_doar_pe_jumatate_e_422(client):
    r = await client.post("/api/scop-core/minute", json={
        "minute": [{"storage_path": "scop-core/a.json", "filename": "a.json"}],
        "scop_storage_path": "scop-core/b.docx"})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_fisier_care_nu_e_minuta_e_422(client):
    strain = _json_tempfile({"cu totul altceva": 1})
    with patch("routers.scop_core.download_upload", return_value=strain):
        r = await client.post("/api/scop-core/minute", json={
            "minute": [{"storage_path": "scop-core/a.json", "filename": "a.json"}]})
    assert r.status_code == 422
    assert "FitGap" in r.json()["detail"] or "minut" in r.json()["detail"].lower()


@pytest.mark.anyio
async def test_fisierele_descarcate_se_sterg(client):
    """Storage-ul e releu; temporarele locale nu au voie să rămână nici la succes."""
    minuta = _json_tempfile(MINUTA)
    with patch("routers.scop_core.download_upload", return_value=minuta):
        r = await client.post("/api/scop-core/minute", json={
            "minute": [{"storage_path": "scop-core/a.json", "filename": "a.json"}]})
    assert r.status_code == 200
    assert not minuta.exists()
