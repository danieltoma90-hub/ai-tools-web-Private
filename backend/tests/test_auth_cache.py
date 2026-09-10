# -*- coding: utf-8 -*-
"""Clientul Supabase unic + cache-ul de verificare a token-ului."""
import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import auth


@pytest.fixture(autouse=True)
def _curata():
    auth._token_cache.clear()
    auth.reset_supabase_client()
    yield
    auth._token_cache.clear()
    auth.reset_supabase_client()


def _token(exp_peste_secunde: int | None = 3600) -> str:
    payload = {"sub": "u1"}
    if exp_peste_secunde is not None:
        payload["exp"] = int(time.time()) + exp_peste_secunde
    codat = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{codat}.semnatura"


def _credentiale(token: str):
    c = MagicMock()
    c.credentials = token
    return c


def _supabase_mock(user="USER"):
    sb = MagicMock()
    sb.auth.get_user.return_value = MagicMock(user=user)
    return sb


def test_clientul_se_construieste_o_singura_data(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "k")
    with patch("auth.create_client", return_value="CLIENT") as creat:
        assert auth.get_supabase() == "CLIENT"
        assert auth.get_supabase() == "CLIENT"
    assert creat.call_count == 1


async def test_al_doilea_apel_nu_mai_intreaba_supabase():
    sb = _supabase_mock()
    with patch("auth.get_supabase", return_value=sb):
        c = _credentiale(_token())
        assert await auth.verify_token(c) == "USER"
        assert await auth.verify_token(c) == "USER"
    assert sb.auth.get_user.call_count == 1


async def test_token_diferit_se_verifica_separat():
    sb = _supabase_mock()
    with patch("auth.get_supabase", return_value=sb):
        await auth.verify_token(_credentiale(_token()))
        await auth.verify_token(_credentiale(_token(1800)))
    assert sb.auth.get_user.call_count == 2


async def test_cache_expirat_reintreaba_supabase(monkeypatch):
    sb = _supabase_mock()
    monkeypatch.setattr(auth, "TOKEN_CACHE_TTL_S", 0)
    with patch("auth.get_supabase", return_value=sb):
        c = _credentiale(_token())
        await auth.verify_token(c)
        await auth.verify_token(c)
    assert sb.auth.get_user.call_count == 2


async def test_token_aproape_expirat_nu_se_cacheaza_peste_expirare():
    """Un token cu 5 secunde ramase nu are voie sa fie acceptat 60."""
    sb = _supabase_mock()
    with patch("auth.get_supabase", return_value=sb):
        await auth.verify_token(_credentiale(_token(5)))
    (valabil_pana, _), = _token_cache_values()
    assert valabil_pana - time.monotonic() <= 5.1


def _token_cache_values():
    return list(auth._token_cache.values())


async def test_token_respins_nu_ramane_in_cache():
    sb = MagicMock()
    sb.auth.get_user.side_effect = Exception("invalid")
    with patch("auth.get_supabase", return_value=sb):
        with pytest.raises(HTTPException) as e:
            await auth.verify_token(_credentiale(_token()))
    assert e.value.status_code == 401
    assert auth._token_cache == {}


async def test_token_invalidat_dupa_ce_a_fost_cacheat_nu_mai_trece(monkeypatch):
    """Cache-ul intarzie revocarea cu cel mult TTL-ul, nu o anuleaza."""
    monkeypatch.setattr(auth, "TOKEN_CACHE_TTL_S", 0)
    sb = _supabase_mock()
    c = _credentiale(_token())
    with patch("auth.get_supabase", return_value=sb):
        await auth.verify_token(c)
        sb.auth.get_user.side_effect = Exception("revocat")
        with pytest.raises(HTTPException):
            await auth.verify_token(c)


async def test_cache_ul_nu_creste_nelimitat(monkeypatch):
    monkeypatch.setattr(auth, "_MAX_CACHED_TOKENS", 10)
    sb = _supabase_mock()
    with patch("auth.get_supabase", return_value=sb):
        for i in range(25):
            await auth.verify_token(_credentiale(_token(3600 + i)))
    assert len(auth._token_cache) <= 10


async def test_token_fara_exp_foloseste_ttl_ul_implicit():
    sb = _supabase_mock()
    with patch("auth.get_supabase", return_value=sb):
        await auth.verify_token(_credentiale(_token(None)))
    (valabil_pana, _), = _token_cache_values()
    assert valabil_pana - time.monotonic() > auth.TOKEN_CACHE_TTL_S - 1


async def test_token_lipsa_ramane_401():
    with pytest.raises(HTTPException) as e:
        await auth.verify_token(None)
    assert e.value.status_code == 401


async def test_token_ilizibil_nu_crapa_la_citirea_exp():
    sb = _supabase_mock()
    with patch("auth.get_supabase", return_value=sb):
        assert await auth.verify_token(_credentiale("nu-e-un-jwt")) == "USER"
