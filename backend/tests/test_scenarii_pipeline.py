from pathlib import Path

import pytest
from docx import Document

import llm_client
from pipelines.scenarii_pipeline import (
    _extract_structure,
    estimate_scenarii_job,
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
