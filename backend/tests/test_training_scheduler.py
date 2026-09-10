# -*- coding: utf-8 -*-
"""Distributia modulelor pe zile — regulile care fac agenda credibila."""
import pytest

from skills.training.catalog import get_catalog, ore_referinta
from skills.training.scheduler import (
    MIN_ORE,
    ORE_PE_ZI,
    construieste_plan,
    imparte_pe_zile,
    scaleaza,
)
from skills.training.spec_extract import ataseaza_la_module


def _total(plan: dict) -> float:
    return round(sum(m["ore"] for z in plan["zile"] for m in z["module"]), 2)


def _module_din_specificatie() -> list[dict]:
    """Cum arată modulele venite dintr-o specificație de producție.

    Planificatorul nu mai primește doar catalogul CORE: la Producție conținutul
    e ridicat din documentul clientului, cu orice denumiri, orice ore și niciun
    modul protejat de comprimare.
    """
    ore = [4.0, 1.5, 3.0, 0.5, 2.5, 6.0, 1.0]
    return [
        {
            "nr": i + 1,
            "nume": f"Modul din specificație {i + 1}",
            "ore": o,
            "audienta": "Operatori producție",
            "esential": False,
            "grupe": [("Conținut", ["Subiect"])],
        }
        for i, o in enumerate(ore)
    ]


@pytest.mark.parametrize("zile", [1, 2, 3, 4, 5, 10])
def test_nicio_zi_nu_depaseste_programul(zile):
    seturi = {"core": get_catalog("core"), "specificatie": _module_din_specificatie()}
    for eticheta, module in seturi.items():
        plan = construieste_plan(module, zile)
        for z in plan["zile"]:
            assert z["ore"] <= ORE_PE_ZI + 0.01, f"{eticheta} {zile} zile: {z}"
        assert plan["supraincarcat"] is False


@pytest.mark.parametrize("zile", [1, 2, 3, 5])
def test_totalul_incape_in_buget(zile):
    plan = construieste_plan(get_catalog("core"), zile)
    assert _total(plan) <= plan["buget_ore"] + 0.01
    assert plan["total_ore"] == _total(plan)


def test_trei_zile_reproduc_distributia_validata_manual():
    """Cele 3 zile validate cu clientul: 17h, in ordinea catalogului."""
    plan = construieste_plan(get_catalog("core"), 3)
    ore = [
        (m["nume"], m["ore"]) for z in plan["zile"] for m in z["module"]
    ]
    assert ore == [
        ("Modul General (Informații Generale)", 3.5),
        ("Modul Depozit", 2.5),
        ("Modul Achiziții", 2.5),
        ("Modul Vânzări", 2.0),
        ("Modul Financiar", 1.5),
        ("Modul Mijloace Fixe", 2.0),
        ("Modul Contabilitate", 3.0),
    ]
    assert plan["total_ore"] == ore_referinta("core") == 17.0
    assert plan["excluse"] == []


def test_o_singura_zi_pastreaza_toate_modulele_la_minim():
    plan = construieste_plan(get_catalog("core"), 1)
    assert plan["excluse"] == []
    assert len(plan["zile"]) == 1
    assert plan["zile"][0]["ore"] == ORE_PE_ZI


def test_un_modul_nu_apare_de_doua_ori_in_aceeasi_zi():
    for zile in range(1, 11):
        plan = construieste_plan(get_catalog("core"), zile)
        for z in plan["zile"]:
            numere = [m["nr"] for m in z["module"]]
            assert len(numere) == len(set(numere)), f"{zile} zile, ziua {z['zi']}"


def test_modulele_raman_in_ordinea_catalogului():
    plan = construieste_plan(get_catalog("core"), 4)
    numere = [m["nr"] for z in plan["zile"] for m in z["module"]]
    assert numere == sorted(numere)


def test_niciun_modul_sub_pragul_minim():
    plan = construieste_plan(get_catalog("core"), 1)
    for z in plan["zile"]:
        for m in z["module"]:
            assert m["ore"] >= MIN_ORE


def test_buget_insuficient_exclude_neesentialele_si_le_raporteaza():
    """Trei module cu buget de 1h: doar esentialul supravietuieste."""
    module = [
        {"nr": 1, "nume": "A", "ore": 2.0, "esential": True, "grupe": []},
        {"nr": 2, "nume": "B", "ore": 2.0, "esential": False, "grupe": []},
        {"nr": 3, "nume": "C", "ore": 2.0, "esential": False, "grupe": []},
    ]
    incluse, excluse = scaleaza(module, 1.0)
    assert [m["nume"] for m in incluse] == ["A", "B"]
    assert [m["nume"] for m in excluse] == ["C"]


def test_modulele_esentiale_nu_se_exclud_niciodata():
    module = [
        {"nr": i, "nume": f"M{i}", "ore": 2.0, "esential": True, "grupe": []}
        for i in range(1, 4)
    ]
    incluse, excluse = scaleaza(module, 0.5)
    assert excluse == []
    assert len(incluse) == 3


def test_modul_lung_se_sparge_doar_in_bucati_utilizabile():
    """Un modul de 8h in 2 zile: 6h + 2h, nu 6h + o coada de cateva minute."""
    module = [{"nr": 1, "nume": "Lung", "ore": 8.0, "esential": True, "grupe": []}]
    zile = imparte_pe_zile(module, 2)
    assert [z["ore"] for z in zile] == [6.0, 2.0]
    assert zile[1]["module"][0]["continuare"] is True


def test_golul_mic_nu_rupe_modulul():
    """0.5h liber la finalul zilei: modulul urmator trece intreg maine."""
    module = [
        {"nr": 1, "nume": "A", "ore": 5.5, "esential": True, "grupe": []},
        {"nr": 2, "nume": "B", "ore": 3.0, "esential": True, "grupe": []},
    ]
    zile = imparte_pe_zile(module, 2)
    assert [z["ore"] for z in zile] == [5.5, 3.0]
    assert len(zile[0]["module"]) == 1


def test_zile_invalide_dau_eroare():
    with pytest.raises(ValueError):
        construieste_plan(get_catalog("core"), 0)


def test_particularitatile_cresc_efortul_modulului_vizat():
    module = get_catalog("core")
    inainte = next(m for m in module if m["nume"] == "Modul Depozit")["ore"]
    module = ataseaza_la_module(
        module,
        [
            {"modul": "Modul Depozit", "titlu": "Notă de cântar", "detaliu": "", "cod": ""},
            {"modul": "Modul Depozit", "titlu": "Retichetare", "detaliu": "", "cod": ""},
        ],
    )
    depozit = next(m for m in module if m["nume"] == "Modul Depozit")
    assert depozit["ore"] == inainte + 1.0
    assert depozit["grupe"][-1][0] == "Particularități client"
    assert len(depozit["grupe"][-1][1]) == 2


def test_modul_inexistent_in_particularitati_nu_pierde_informatia():
    module = get_catalog("core")
    module = ataseaza_la_module(
        module, [{"modul": "Modul Inventat", "titlu": "X", "detaliu": "", "cod": ""}]
    )
    cu_particularitati = [
        m for m in module if any(g[0] == "Particularități client" for g in m["grupe"])
    ]
    assert len(cu_particularitati) == 1
