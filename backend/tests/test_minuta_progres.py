# -*- coding: utf-8 -*-
"""Raportarea progresului la minuta cu Claude.

Cele cinci extrageri rulează în paralel tocmai ca să scadă timpul de la ~90s la
~30s. `asyncio.gather` nu spune nimic până la final, deci bara de progres n-avea
niciun semnal — aici se verifică numărătoarea care i-l dă, fără să strice
ordinea rezultatelor.
"""
import asyncio

from pipelines.minuta_pipeline import _cu_raportare


async def _intarziere(valoare, secunde):
    await asyncio.sleep(secunde)
    return valoare


async def test_raporteaza_fiecare_terminare():
    pasi = []
    rezultate = await _cu_raportare(
        [_intarziere("a", 0.03), _intarziere("b", 0.01), _intarziere("c", 0.02)],
        pasi.append,
    )
    assert rezultate == ["a", "b", "c"]  # ordinea de intrare, nu cea de terminare
    assert pasi == [
        "extrageri:0/3",
        "extrageri:1/3",
        "extrageri:2/3",
        "extrageri:3/3",
    ]


async def test_ordinea_rezultatelor_nu_depinde_de_viteza():
    rezultate = await _cu_raportare(
        [_intarziere(i, (5 - i) / 100) for i in range(5)], None
    )
    assert rezultate == [0, 1, 2, 3, 4]


async def test_fara_raportor_nu_crapa():
    assert await _cu_raportare([_intarziere("x", 0)], None) == ["x"]


async def test_o_eroare_intr_o_extragere_urca():
    async def cade():
        raise RuntimeError("Claude a picat")

    try:
        await _cu_raportare([_intarziere("ok", 0), cade()], None)
        assert False, "eroarea trebuia să urce"
    except RuntimeError as e:
        assert "Claude a picat" in str(e)
