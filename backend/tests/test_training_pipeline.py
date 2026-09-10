# -*- coding: utf-8 -*-
"""Ce se întâmplă când specificația nu poate fi citită.

Cazul e real: o cheie API revocată face apelul să pice cu 401. Înainte, eroarea
era înghițită și utilizatorul primea o agendă „reușită" fără nicio particularitate
a clientului — exact ce trebuia să aducă tool-ul.
"""
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_errors import mesaj_eroare_ai
from pipelines.training_pipeline import run_training_pipeline


class _Anthropic401(Exception):
    status_code = 401

    def __str__(self):
        return "Error code: 401 - {'type': 'authentication_error', 'message': 'API key is invalid.'}"


def _spec(tmp_path: Path) -> Path:
    from docx import Document

    p = tmp_path / "spec.docx"
    d = Document()
    d.add_paragraph("Rețeta se preia din laborator.")
    d.save(str(p))
    return p


async def test_productie_esueaza_cand_specificatia_nu_poate_fi_citita(tmp_path):
    with patch(
        "pipelines.training_pipeline.extrage_particularitati",
        side_effect=_Anthropic401(),
    ):
        with pytest.raises(RuntimeError) as e:
            await run_training_pipeline(
                tip="productie", zile=3, client="ACME",
                spec_path=_spec(tmp_path), api_key="sk-x",
            )
    mesaj = str(e.value)
    assert "specificația" in mesaj
    assert "invalidă" in mesaj or "revocată" in mesaj


async def test_core_livreaza_standardul_dar_avertizeaza(tmp_path):
    with patch(
        "pipelines.training_pipeline.extrage_particularitati",
        side_effect=_Anthropic401(),
    ):
        docx, xlsx, sumar = await run_training_pipeline(
            tip="core", zile=3, client="ACME",
            spec_path=_spec(tmp_path), api_key="sk-x",
        )
    try:
        assert sumar["particularitati"] == 0
        assert sumar["avertisment"]
        assert "nu au putut fi extrase" in sumar["avertisment"]
        assert sumar["total_ore"] == 17.0  # programul standard e intact
    finally:
        docx.unlink(missing_ok=True)
        xlsx.unlink(missing_ok=True)


async def test_fara_specificatie_nu_exista_avertisment():
    docx, xlsx, sumar = await run_training_pipeline(tip="core", zile=3, client="ACME")
    try:
        assert sumar["avertisment"] == ""
    finally:
        docx.unlink(missing_ok=True)
        xlsx.unlink(missing_ok=True)


async def test_particularitatile_gasite_ajung_in_sumar(tmp_path):
    gasite = [
        {"modul": "Modul Depozit", "titlu": "Notă de cântar", "detaliu": "", "cod": ""},
        {"modul": "Modul Depozit", "titlu": "Retichetare", "detaliu": "", "cod": ""},
    ]
    with patch(
        "pipelines.training_pipeline.extrage_particularitati", return_value=gasite
    ):
        docx, xlsx, sumar = await run_training_pipeline(
            tip="core", zile=3, client="ACME",
            spec_path=_spec(tmp_path), api_key="sk-x",
        )
    try:
        assert sumar["particularitati"] == 2
        assert sumar["avertisment"] == ""
    finally:
        docx.unlink(missing_ok=True)
        xlsx.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "exc,asteptat",
    [
        (_Anthropic401(), "invalidă"),
        (Exception("Your credit balance is too low"), "credite"),
        (type("E", (Exception,), {"status_code": 429})(), "limita"),
    ],
)
def test_mesajele_de_eroare_spun_ce_e_de_facut(exc, asteptat):
    assert asteptat in mesaj_eroare_ai(exc)
