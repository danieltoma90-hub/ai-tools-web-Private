# -*- coding: utf-8 -*-
"""Robustețea extragerii: JSON ciobit și nume de module aproximative."""
import pytest

from skills.training.catalog import get_catalog
from skills.training.spec_extract import _parse_json, potriveste_modul

CORE = [m["nume"] for m in get_catalog("core")]

# Denumiri de module așa cum le poate produce AI-ul citind o specificație de
# producție. Nu există catalog standard de producție — potrivirea trebuie să
# funcționeze pe orice set de denumiri, nu doar pe unul cunoscut dinainte.
PRODUCTIE = [
    "Nomenclatoare de producție",
    "Comenzi și ordine de fabricație",
    "Raportarea producției",
    "Trasabilitate și calitate",
    "Costuri de producție",
]


def test_json_curat():
    assert _parse_json('{"particularitati": []}') == {"particularitati": []}


def test_json_in_bloc_markdown():
    text = 'Iată rezultatul:\n```json\n{"particularitati": [{"titlu": "X"}]}\n```'
    assert _parse_json(text)["particularitati"][0]["titlu"] == "X"


def test_json_cu_explicatii_in_jur():
    text = 'Am identificat următoarele:\n{"particularitati": []}\nSper că ajută.'
    assert _parse_json(text) == {"particularitati": []}


def test_json_ciobit_se_repara():
    """Un răspuns tăiat la max_tokens nu are voie să arunce toată extragerea."""
    text = '{"particularitati": [{"modul": "Modul Depozit", "titlu": "Notă cântar"'
    rezultat = _parse_json(text)
    assert rezultat["particularitati"][0]["titlu"] == "Notă cântar"


def test_raspuns_fara_json_da_eroare_explicita():
    with pytest.raises(ValueError):
        _parse_json("Nu am găsit nimic specific în document.")


@pytest.mark.parametrize(
    "propus,asteptat",
    [
        ("Modul Depozit", "Modul Depozit"),
        ("Depozit", "Modul Depozit"),
        ("modul depozit", "Modul Depozit"),
        ("Modul Mijloace Fixe", "Modul Mijloace Fixe"),
        ("Mijloace fixe", "Modul Mijloace Fixe"),
        ("Modul General", "Modul General (Informații Generale)"),
        ("Vanzari", "Modul Vânzări"),
        ("Achizitii", "Modul Achiziții"),
    ],
)
def test_potrivire_nume_core(propus, asteptat):
    assert potriveste_modul(propus, CORE) == asteptat


@pytest.mark.parametrize(
    "propus,asteptat",
    [
        ("Nomenclatoare producție", "Nomenclatoare de producție"),
        ("Nomenclatoare de producție", "Nomenclatoare de producție"),
        ("Comenzi de fabricație", "Comenzi și ordine de fabricație"),
        ("Raportarea producției", "Raportarea producției"),
        ("Trasabilitate", "Trasabilitate și calitate"),
        ("Costuri", "Costuri de producție"),
    ],
)
def test_potrivire_nume_productie(propus, asteptat):
    assert potriveste_modul(propus, PRODUCTIE) == asteptat


def test_atasarea_foloseste_aceeasi_potrivire_ca_extragerea():
    """Ultima poartă înainte de document nu are voie să fie mai proastă.

    Înainte compara la literă și, la orice abatere, trimitea particularitatea
    pe primul modul — care ieșea umflat, iar restul rămâneau goale.
    """
    from skills.training.spec_extract import ataseaza_la_module

    module = ataseaza_la_module(
        get_catalog("core"),
        [
            {"modul": "Depozit", "titlu": "Notă de cântar", "detaliu": "", "cod": ""},
            {"modul": "Mijloace fixe", "titlu": "Amortizare accelerată",
             "detaliu": "", "cod": ""},
            {"modul": "Contabilitate", "titlu": "Note contabile proprii",
             "detaliu": "", "cod": ""},
        ],
    )
    unde = {
        m["nume"]: list(m["grupe"][-1][1])
        for m in module
        if m["grupe"][-1][0] == "Particularități client"
    }
    assert unde["Modul Depozit"] == ["Notă de cântar"]
    assert unde["Modul Mijloace Fixe"] == ["Amortizare accelerată"]
    assert unde["Modul Contabilitate"] == ["Note contabile proprii"]
    assert "Modul General (Informații Generale)" not in unde


def test_nume_complet_strain_cade_pe_primul_modul():
    """Mai bine pe primul modul decât pierdută cu totul."""
    assert potriveste_modul("Managementul flotei auto", CORE) == CORE[0]
    assert potriveste_modul("", CORE) == CORE[0]
