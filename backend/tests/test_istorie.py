# -*- coding: utf-8 -*-
"""Evenimentele zilei: cache permanent, selecție Claude, plasă de siguranță.

Ce apără testele astea e în primul rând costul: fiecare zi din calendar are voie
să coste un singur apel Claude, vreodată.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import istorie
from auth import verify_token
from main import app

FEED = [
    {"an": 1969, "text": "Apollo 11 landed on the Moon."},
    {"an": 1998, "text": "A footballer scored in the championship final."},
    {"an": 1945, "text": "The atomic bomb was dropped on Hiroshima."},
    {"an": 2001, "text": "An airliner crashed near the coast."},
]


@pytest.fixture(autouse=True)
def _fara_lacate():
    istorie._lacate.clear()
    yield
    istorie._lacate.clear()


def _claude(alese):
    resp = MagicMock()
    resp.content = [MagicMock(text=json.dumps({"alese": alese}))]
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=resp)
    return client


async def test_cache_ul_opreste_al_doilea_apel():
    """A doua cerere pentru aceeași zi nu are voie să coste nimic."""
    salvat = {}
    with patch("istorie.cache_citeste", side_effect=lambda c: salvat.get(c)), \
         patch("istorie.cache_scrie", side_effect=lambda c, d: salvat.__setitem__(c, d)), \
         patch("istorie._din_wikipedia", AsyncMock(return_value=FEED)) as wiki, \
         patch("anthropic.AsyncAnthropic", return_value=_claude([0, 2])) as cl:
        prima = await istorie.evenimentele_zilei(7, 20, "sk-x")
        a_doua = await istorie.evenimentele_zilei(7, 20, "sk-x")

    assert prima == a_doua
    assert [e["an"] for e in prima] == [1969, 1945]
    assert wiki.call_count == 1
    assert cl.call_count == 1


async def test_claude_alege_dintre_evenimentele_date():
    with patch("istorie.cache_citeste", return_value=None), \
         patch("istorie.cache_scrie"), \
         patch("istorie._din_wikipedia", AsyncMock(return_value=FEED)), \
         patch("anthropic.AsyncAnthropic", return_value=_claude([2, 0])):
        rezultat = await istorie.evenimentele_zilei(8, 6, "sk-x")
    assert [e["an"] for e in rezultat] == [1945, 1969]


async def test_indici_inventati_sunt_ignorati():
    with patch("istorie.cache_citeste", return_value=None), \
         patch("istorie.cache_scrie"), \
         patch("istorie._din_wikipedia", AsyncMock(return_value=FEED)), \
         patch("anthropic.AsyncAnthropic", return_value=_claude([0, 99, -3, "x"])):
        rezultat = await istorie.evenimentele_zilei(8, 6, "sk-x")
    assert [e["an"] for e in rezultat] == [1969]


async def test_claude_picat_cade_pe_cuvinte_cheie():
    """Fără AI rămâne selecția pe cuvinte — mai bine aproximativ decât gol."""
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=Exception("401"))
    with patch("istorie.cache_citeste", return_value=None), \
         patch("istorie.cache_scrie"), \
         patch("istorie._din_wikipedia", AsyncMock(return_value=FEED)), \
         patch("anthropic.AsyncAnthropic", return_value=client):
        rezultat = await istorie.evenimentele_zilei(8, 6, "sk-x")

    ani = [e["an"] for e in rezultat]
    assert 1969 in ani and 1945 in ani
    assert 1998 not in ani  # sport
    assert 2001 not in ani  # accident aviatic


async def test_fara_cheie_nu_se_apeleaza_claude():
    with patch("istorie.cache_citeste", return_value=None), \
         patch("istorie.cache_scrie"), \
         patch("istorie._din_wikipedia", AsyncMock(return_value=FEED)), \
         patch("anthropic.AsyncAnthropic") as cl:
        rezultat = await istorie.evenimentele_zilei(8, 6, "")
    cl.assert_not_called()
    assert rezultat


async def test_wikipedia_indisponibil_nu_crapa():
    with patch("istorie.cache_citeste", return_value=None), \
         patch("istorie.cache_scrie"), \
         patch("istorie._din_wikipedia", AsyncMock(side_effect=Exception("timeout"))):
        assert await istorie.evenimentele_zilei(8, 6, "sk-x") == []


async def test_cache_stricat_se_recalculeaza():
    with patch("istorie.cache_citeste", return_value=b"nu e json"), \
         patch("istorie.cache_scrie"), \
         patch("istorie._din_wikipedia", AsyncMock(return_value=FEED)), \
         patch("anthropic.AsyncAnthropic", return_value=_claude([0])):
        rezultat = await istorie.evenimentele_zilei(8, 6, "sk-x")
    assert [e["an"] for e in rezultat] == [1969]


async def test_ruta_fara_auth_returns_401(client):
    assert (await client.get("/api/istorie/zi")).status_code == 401


async def test_ruta_intoarce_ziua_curenta(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        with patch(
            "routers.istorie.evenimentele_zilei",
            AsyncMock(return_value=[{"an": 1969, "text": "Apollo 11"}]),
        ):
            r = await client.get(
                "/api/istorie/zi", headers={"Authorization": "Bearer fake"}
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["evenimente"][0]["an"] == 1969


async def test_zi_invalida_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        r = await client.get(
            "/api/istorie/zi?luna=13&zi=40", headers={"Authorization": "Bearer fake"}
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
