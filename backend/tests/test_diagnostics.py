# -*- coding: utf-8 -*-
"""Diagnosticul cheii Claude — butonul „Verifică acum" din pagina Cont.

Diagnosticul trece pe drumul generărilor reale (`claude.raspunde`), deci aici
se verifică ce raportează pentru fiecare situație, cu Claude simulat.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import claude
from auth import verify_token
from main import app
from routers.diagnostics import _check_anthropic, _classify


class _EroareApi(Exception):
    """Forma unei erori de status din SDK: are status_code și body."""

    def __init__(self, status: int, mesaj: str):
        super().__init__(mesaj)
        self.status_code = status
        self.body = {"type": "error", "error": {"type": "x", "message": mesaj}}


def _ok(citit: int = 0, scris: int = 0):
    return claude.Raspuns("OK", "end_turn", SimpleNamespace(
        cache_read_input_tokens=citit, cache_creation_input_tokens=scris, input_tokens=12))


def _incalzire(scris: int = 6000, eroare: str = "", cu_fallback: bool = True):
    usage = SimpleNamespace(cache_creation_input_tokens=scris) if scris or not eroare else None
    return claude.Incalzire(usage, cu_fallback, eroare)


@pytest.fixture(autouse=True)
def _cheie(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-test-cheie-de-proba-KwAA")


def test_classify_200():
    assert _classify(200, {})[0] == "ok"


def test_classify_401():
    stare, mesaj = _classify(401, {"error": {"message": "invalid x-api-key"}})
    assert stare == "cheie_invalida" and "invalidă" in mesaj


def test_classify_fara_credit():
    stare, mesaj = _classify(400, {"error": {"message": "Your credit balance is too low"}})
    assert stare == "fara_credit" and "credite" in mesaj


def test_classify_429():
    assert _classify(429, {})[0] == "limita_atinsa"


def test_classify_403_nu_mai_trimite_la_mistral():
    stare, mesaj = _classify(403, {"error": {"message": "forbidden"}})
    assert stare == "model_nepermis"
    assert "CLAUDE_MODEL" in mesaj and "MISTRAL" not in mesaj


async def test_cheie_lipsa(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = await _check_anthropic()
    assert r["state"] == "lipsa" and r["configured"] is False


async def test_totul_functioneaza_si_cache_ul_citeste(monkeypatch):
    raspunsuri = AsyncMock(side_effect=[_ok(), _ok(citit=1024)])
    monkeypatch.setattr(claude, "raspunde", raspunsuri)
    monkeypatch.setattr(claude, "incalzeste_cache", AsyncMock(return_value=_incalzire()))

    r = await _check_anthropic()

    assert r["state"] == "ok"
    assert r["key_hint"].startswith("sk-ant-api03-tes") and "cheie-de-proba" not in r["key_hint"]
    detalii = " | ".join(r["detalii"])
    assert claude.model() in detalii
    assert "Cache: funcționează (1024 tokeni" in detalii
    assert "Încălzire: 6000 tokeni scriși în cache (cu fallback)" in detalii
    # a doua cerere poartă prefixul de cache, după încălzire
    assert raspunsuri.call_args_list[1].kwargs["prefix_cache"]


async def test_cache_ul_rescris_de_cererea_reala_spune_ca_incalzirea_nu_se_potriveste(monkeypatch):
    monkeypatch.setattr(claude, "incalzeste_cache", AsyncMock(return_value=_incalzire()))
    monkeypatch.setattr(claude, "raspunde", AsyncMock(side_effect=[_ok(), _ok(citit=0, scris=6000)]))
    r = await _check_anthropic()
    detalii = " | ".join(r["detalii"])
    assert r["state"] == "ok"
    assert "NU a citit" in detalii and "încălzirea nu se potrivește" in detalii
    assert "0 citiți din cache · 6000 scriși" in detalii


async def test_incalzirea_refuzata_isi_spune_motivul(monkeypatch):
    monkeypatch.setattr(claude, "incalzeste_cache", AsyncMock(
        return_value=_incalzire(scris=0, eroare="cu fallback: max_tokens invalid")))
    monkeypatch.setattr(claude, "raspunde", AsyncMock(side_effect=[_ok(), _ok(citit=0, scris=6000)]))
    r = await _check_anthropic()
    assert any("Încălzire: refuzată — cu fallback: max_tokens invalid" in d for d in r["detalii"])


async def test_prefix_sub_prag_e_semnalat(monkeypatch):
    monkeypatch.setattr(claude, "incalzeste_cache", AsyncMock(return_value=_incalzire(scris=0)))
    monkeypatch.setattr(claude, "raspunde", AsyncMock(side_effect=[_ok(), _ok(citit=0, scris=0)]))
    r = await _check_anthropic()
    assert any("sub pragul minim" in d for d in r["detalii"])


async def test_cheie_invalida_raportata_din_exceptia_sdk(monkeypatch):
    monkeypatch.setattr(
        claude, "raspunde", AsyncMock(side_effect=_EroareApi(401, "invalid x-api-key")))
    r = await _check_anthropic()
    assert r["state"] == "cheie_invalida"


async def test_fara_credit_raportat(monkeypatch):
    monkeypatch.setattr(
        claude, "raspunde",
        AsyncMock(side_effect=_EroareApi(400, "Your credit balance is too low to access the API")))
    r = await _check_anthropic()
    assert r["state"] == "fara_credit"


async def test_ruta_cere_autentificare(client):
    assert (await client.get("/api/diagnostics/providers")).status_code == 401


async def test_ruta_raporteaza_un_singur_furnizor(client, monkeypatch):
    monkeypatch.setattr(claude, "raspunde", AsyncMock(side_effect=[_ok(), _ok(citit=900)]))
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        r = await client.get("/api/diagnostics/providers", headers={"Authorization": "Bearer x"})
    finally:
        app.dependency_overrides.clear()
    furnizori = r.json()["providers"]
    assert [f["provider"] for f in furnizori] == ["Claude (Anthropic)"]
