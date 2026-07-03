import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from docx import Document

import llm_client
import openpyxl
from pipelines.scenarii_pipeline import (
    _extract_structure,
    estimate_scenarii_job,
    run_scenarii_pipeline,
)


@pytest.fixture
def spec_docx(tmp_path) -> Path:
    doc = Document()
    doc.add_heading("Modul Achizitii", level=1)
    doc.add_heading("Facturi furnizor", level=2)
    doc.add_paragraph("Utilizatorul introduce factura cu numar si data.")
    doc.add_paragraph("Sistemul valideaza duplicatele dupa numar si furnizor.")
    doc.add_heading("Receptie marfa", level=3)
    doc.add_paragraph("Receptia se face pe baza comenzii aprobate.")
    doc.add_heading("Modul Vanzari", level=1)
    doc.add_heading("Oferte", level=2)
    doc.add_paragraph("Oferta se transforma in comanda cu un click.")
    path = tmp_path / "spec.docx"
    doc.save(str(path))
    return path


def test_extract_structure_captures_body_text(spec_docx):
    structure = _extract_structure(spec_docx)
    assert set(structure) == {"Modul Achizitii", "Modul Vanzari"}

    cap = structure["Modul Achizitii"][0]
    assert cap["titlu"] == "Facturi furnizor"
    assert "Utilizatorul introduce factura cu numar si data." in cap["text"]
    assert "Sistemul valideaza duplicatele dupa numar si furnizor." in cap["text"]

    sub = cap["subcapitole"][0]
    assert sub["titlu"] == "Receptie marfa"
    assert sub["text"] == ["Receptia se face pe baza comenzii aprobate."]

    vanzari = structure["Modul Vanzari"][0]
    assert vanzari["text"] == ["Oferta se transforma in comanda cu un click."]


def test_extract_structure_h1_only_body_text(tmp_path):
    doc = Document()
    doc.add_heading("Modul Simplu", level=1)
    doc.add_paragraph("Functionalitatea se activeaza din meniul principal.")
    doc.add_paragraph("Sistemul blocheaza accesul utilizatorilor fara drepturi.")
    path = tmp_path / "h1only.docx"
    doc.save(str(path))

    structure = _extract_structure(path)
    cap = structure["Modul Simplu"][0]
    assert cap["titlu"] == "Modul Simplu"
    assert cap["text"] == [
        "Functionalitatea se activeaza din meniul principal.",
        "Sistemul blocheaza accesul utilizatorilor fara drepturi.",
    ]
    assert cap["subcapitole"] == []


def test_estimate_scenarii_job(spec_docx, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "500000")
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0

    est = estimate_scenarii_job(spec_docx)
    assert est["modules"] == 2
    assert est["est_tokens"] > 2 * 7200  # overhead + output per modul
    assert est["est_minutes"] >= 1
    assert est["fits_budget"] is True


def test_estimate_scenarii_job_over_budget(spec_docx, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "100")
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0

    est = estimate_scenarii_job(spec_docx)
    assert est["fits_budget"] is False


_AI_RESPONSE = json.dumps({
    "scenarii": [
        {
            "capitol": "Facturi furnizor",
            "subcapitol": "",
            "titlu_scenariu": "Introducere factura valida",
            "obiectiv": "Verifica introducerea unei facturi cu date complete.",
            "preconditii": "• Furnizor activ in nomenclator",
            "pasi": "1. Deschide ecranul Facturi\n2. Completeaza numar si data\n3. Salveaza",
            "rezultat_asteptat": "Factura este salvata si apare in lista.",
            "tip_test": "Funcțional - Pozitiv",
            "prioritate": "High",
            "dependente": "—",
            "observatii": "",
        },
        {
            "capitol": "Facturi furnizor",
            "subcapitol": "",
            "titlu_scenariu": "Factura duplicata este respinsa",
            "obiectiv": "Verifica validarea duplicatelor.",
            "preconditii": "• O factura cu acelasi numar exista deja",
            "pasi": "1. Introdu factura cu numar existent\n2. Salveaza",
            "rezultat_asteptat": "Sistemul respinge salvarea cu mesaj de duplicat.",
            "tip_test": "Funcțional - Negativ",
            "prioritate": "High",
            "dependente": "—",
            "observatii": "",
        },
    ]
})


async def test_run_pipeline_ai_generates_from_llm(spec_docx):
    steps: list[str] = []
    with patch("pipelines.scenarii_pipeline.llm_client.chat", new=AsyncMock(return_value=_AI_RESPONSE)) as mock_chat:
        xlsx_path, scenarios = await run_scenarii_pipeline(spec_docx, use_ai=True, on_step=steps.append)
    try:
        assert mock_chat.await_count == 2  # un apel per modul H1
        # 2 module x 2 scenarii din mock
        assert len(scenarios) == 4
        assert scenarios[0]["id"] == "TC-001"
        assert scenarios[0]["ai"] is True
        assert scenarios[0]["titlu_scenariu"] == "Introducere factura valida"
        assert any(s.startswith("module:1/2:") for s in steps)
        assert "building" in steps

        wb = openpyxl.load_workbook(str(xlsx_path), data_only=True)
        try:
            ws = wb["Scenarii"]
            assert ws.cell(row=1, column=1).value == "ID"
            assert ws.cell(row=2, column=1).value == "TC-001"
            assert ws.cell(row=2, column=4).value == "Introducere factura valida"
            assert ws.max_column == 12
        finally:
            wb.close()
    finally:
        import gc
        gc.collect()
        xlsx_path.unlink(missing_ok=True)


async def test_run_pipeline_ai_falls_back_per_module(spec_docx):
    async def flaky(system, user, **kwargs):
        # primul modul reuseste, al doilea pica
        if "Achizitii" in user:
            return _AI_RESPONSE
        raise RuntimeError("Eroare LLM (429)")

    with patch("pipelines.scenarii_pipeline.llm_client.chat", side_effect=flaky):
        xlsx_path, scenarios = await run_scenarii_pipeline(spec_docx, use_ai=True)
    try:
        ai_rows = [s for s in scenarios if s["ai"]]
        stub_rows = [s for s in scenarios if not s["ai"]]
        assert len(ai_rows) == 2
        assert len(stub_rows) >= 1
        assert all("fără AI" in s["observatii"] for s in stub_rows)
    finally:
        xlsx_path.unlink(missing_ok=True)


async def test_run_pipeline_without_ai_keeps_stub_behavior(spec_docx):
    xlsx_path, scenarios = await run_scenarii_pipeline(spec_docx, use_ai=False)
    try:
        assert all(s["ai"] is False for s in scenarios)
        assert scenarios[0]["id"] == "TC-001"
        assert scenarios[0]["titlu_scenariu"].startswith("Verificare:")
    finally:
        xlsx_path.unlink(missing_ok=True)


async def test_run_pipeline_ai_tolerates_null_fields(spec_docx):
    response = json.dumps({
        "scenarii": [{
            "capitol": "Facturi furnizor",
            "subcapitol": None,
            "titlu_scenariu": "Scenariu cu null-uri",
            "obiectiv": "Verifica toleranta la null.",
            "preconditii": None,
            "pasi": "1. Pas unic",
            "rezultat_asteptat": "OK",
            "tip_test": None,
            "prioritate": None,
            "dependente": None,
            "observatii": None,
        }]
    })
    with patch("pipelines.scenarii_pipeline.llm_client.chat", new=AsyncMock(return_value=response)):
        xlsx_path, scenarios = await run_scenarii_pipeline(spec_docx, use_ai=True)
    try:
        ai_rows = [s for s in scenarios if s["ai"]]
        assert len(ai_rows) == 2  # un scenariu AI per modul (2 module in fixture)
        assert ai_rows[0]["titlu_scenariu"] == "Scenariu cu null-uri"
        assert ai_rows[0]["subcapitol"] == ""
        assert ai_rows[0]["tip_test"] == "Funcțional - Pozitiv"
        assert ai_rows[0]["dependente"] == "—"
    finally:
        xlsx_path.unlink(missing_ok=True)
