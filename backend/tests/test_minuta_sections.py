# -*- coding: utf-8 -*-
"""Secțiunile preluate din minuta de referință: profil, cerințe, puncte deschise."""
from pipelines.minuta_pipeline import (
    _open_points_section,
    _profile_section,
    _requirements_section,
)

PROFILE = {
    "profil_beneficiar": [
        {"aspect": "Domeniu de activitate", "detaliu": "Producător de substanțe active"},
        {"aspect": "Volum resurse", "detaliu": "110 resurse, 16 ore/zi"},
    ],
    "cerinte_beneficiar": [
        {"zona": "Blocaj campanie", "cerinta": "Echipamentele să nu fie realocate."},
    ],
    "puncte_deschise": ["Cuanta de timp: 10 sau 15 minute, de decis la testare."],
}


def test_profile_section_is_a_two_column_table():
    s = _profile_section(PROFILE)
    assert s["titlu"] == "Profilul beneficiarului"
    block = s["blocuri"][0]
    assert block["header"] == ["Aspect", "Detaliu"]
    assert block["rows"][0] == ["Domeniu de activitate", "Producător de substanțe active"]


def test_requirements_section_keeps_zone_and_requirement():
    s = _requirements_section(PROFILE)
    assert "Cerințe" in s["titlu"]
    assert s["blocuri"][0]["rows"] == [["Blocaj campanie", "Echipamentele să nu fie realocate."]]


def test_open_points_section_is_a_bullet_list():
    s = _open_points_section(PROFILE)
    assert s["titlu"] == "Puncte rămase deschise"
    assert s["blocuri"][0]["type"] == "bullets"
    assert len(s["blocuri"][0]["items"]) == 1


def test_sections_absent_when_model_returns_nothing():
    """Fără conținut real nu se adaugă titluri goale în minută."""
    for builder in (_profile_section, _requirements_section, _open_points_section):
        assert builder(None) is None
        assert builder({}) is None
    assert _profile_section({"profil_beneficiar": []}) is None
    assert _open_points_section({"puncte_deschise": ["", "  "]}) is None


def test_incomplete_rows_are_dropped_not_rendered_empty():
    partial = {
        "profil_beneficiar": [{"aspect": "Domeniu"}, {"detaliu": "fără aspect"}],
        "cerinte_beneficiar": [{"zona": "X"}],
    }
    assert _profile_section(partial) is None
    assert _requirements_section(partial) is None
