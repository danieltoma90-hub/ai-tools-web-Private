# -*- coding: utf-8 -*-
"""Activarea și dezactivarea conturilor de către administrator.

Ce apără testele:
- un cont dezactivat e oprit și cu o sesiune deja deschisă, nu doar la login;
- administratorul nu se poate încuia singur afară și nu poate dezactiva alt admin;
- doar administratorii pot face asta.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import acces
import auth
from auth import verify_token
from main import app

ADMIN = "daniel.toma@totalsoft.ro"
ANA = "ana@totalsoft.ro"


def _peste(zile: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=zile)).isoformat().replace("+00:00", "Z")


@pytest.fixture(autouse=True)
def _curata(monkeypatch):
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    auth._token_cache.clear()
    yield
    auth._token_cache.clear()
    app.dependency_overrides.clear()


def _ca(email: str):
    app.dependency_overrides[verify_token] = lambda: {"id": f"id-{email}", "email": email}


# ── citirea stării ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "banned_until,asteptat",
    [
        (None, False),
        ("", False),
        (_peste(36500), True),            # dezactivat „pentru totdeauna"
        (_peste(-1), False),              # blocare expirată
        ("nu-e-o-data", False),           # valoare ilizibilă: Supabase rămâne primul strat
        ("2126-10-14T10:00:00", True),    # fără fus orar
    ],
)
def test_e_dezactivat(banned_until, asteptat):
    assert auth.e_dezactivat({"banned_until": banned_until}) is asteptat
    assert auth.e_dezactivat(SimpleNamespace(banned_until=banned_until)) is asteptat


# ── sesiunea deja deschisă ────────────────────────────────────────────────────

def _supabase_cu(user):
    sb = MagicMock()
    sb.auth.get_user.return_value = MagicMock(user=user)
    return sb


async def test_sesiunea_unui_cont_dezactivat_e_refuzata():
    """Supabase refuză login-ul, dar un token emis înainte rămâne valid ~1h — îl oprim noi."""
    blocat = SimpleNamespace(id="u-ana", email=ANA, banned_until=_peste(36500))
    cred = MagicMock(credentials="token-ana")
    with patch("auth.get_supabase", return_value=_supabase_cu(blocat)):
        with pytest.raises(HTTPException) as e:
            await auth.verify_token(cred)
    assert e.value.status_code == 401
    assert "dezactivat" in e.value.detail
    assert auth._token_cache == {}  # și nu rămâne în cache ca valid


async def test_dezactivarea_goleste_cache_ul_doar_pentru_acel_utilizator():
    ana = SimpleNamespace(id="u-ana", email=ANA, banned_until=None)
    ion = SimpleNamespace(id="u-ion", email="ion@totalsoft.ro", banned_until=None)
    for tok, u in [("t1", ana), ("t2", ana), ("t3", ion)]:
        with patch("auth.get_supabase", return_value=_supabase_cu(u)):
            await auth.verify_token(MagicMock(credentials=tok))
    assert len(auth._token_cache) == 3

    assert auth.uita_utilizatorul("u-ana") == 2
    ramase = [u.id for _, u in auth._token_cache.values()]
    assert ramase == ["u-ion"]


def test_seteaza_activ_foloseste_blocarea_supabase_si_goleste_cache_ul():
    sb = MagicMock()
    with patch("acces.get_supabase", return_value=sb), \
         patch("acces.uita_utilizatorul") as uita:
        acces.seteaza_activ("u-ana", False)
        sb.auth.admin.update_user_by_id.assert_called_with(
            "u-ana", {"ban_duration": acces.BAN_PERMANENT}
        )
        uita.assert_called_once_with("u-ana")

        acces.seteaza_activ("u-ana", True)
        sb.auth.admin.update_user_by_id.assert_called_with("u-ana", {"ban_duration": "none"})


# ── ruta ──────────────────────────────────────────────────────────────────────

def _tinta(email: str):
    return SimpleNamespace(id=f"id-{email}", email=email, banned_until=None)


async def test_doar_adminul_schimba_starea(client):
    _ca(ANA)
    with patch("acces.seteaza_activ") as seteaza:
        r = await client.put(
            "/api/acces/utilizatori/id-x/stare", json={"activ": False},
            headers={"Authorization": "Bearer x"},
        )
    assert r.status_code == 403
    seteaza.assert_not_called()


async def test_adminul_dezactiveaza_si_reactiveaza(client):
    _ca(ADMIN)
    with patch("acces.utilizator_dupa_id", return_value=_tinta(ANA)), \
         patch("acces.seteaza_activ") as seteaza:
        r1 = await client.put(
            f"/api/acces/utilizatori/id-{ANA}/stare", json={"activ": False},
            headers={"Authorization": "Bearer x"},
        )
        r2 = await client.put(
            f"/api/acces/utilizatori/id-{ANA}/stare", json={"activ": True},
            headers={"Authorization": "Bearer x"},
        )
    assert r1.status_code == 200 and r1.json()["activ"] is False
    assert r2.status_code == 200 and r2.json()["activ"] is True
    assert [c.args for c in seteaza.call_args_list] == [
        (f"id-{ANA}", False), (f"id-{ANA}", True)
    ]


async def test_adminul_nu_se_poate_dezactiva_singur(client):
    """Altfel nu mai are cine să-l reactiveze."""
    _ca(ADMIN)
    with patch("acces.utilizator_dupa_id", return_value=_tinta(ADMIN)), \
         patch("acces.seteaza_activ") as seteaza:
        r = await client.put(
            f"/api/acces/utilizatori/id-{ADMIN}/stare", json={"activ": False},
            headers={"Authorization": "Bearer x"},
        )
    assert r.status_code == 422
    assert "propriul cont" in r.json()["detail"]
    seteaza.assert_not_called()


async def test_un_alt_admin_nu_se_dezactiveaza_de_aici(client, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", f"{ADMIN},sef@totalsoft.ro")
    _ca(ADMIN)
    with patch("acces.utilizator_dupa_id", return_value=_tinta("sef@totalsoft.ro")), \
         patch("acces.seteaza_activ") as seteaza:
        r = await client.put(
            "/api/acces/utilizatori/id-sef/stare", json={"activ": False},
            headers={"Authorization": "Bearer x"},
        )
    assert r.status_code == 422
    assert "ADMIN_EMAILS" in r.json()["detail"]
    seteaza.assert_not_called()


async def test_utilizator_inexistent(client):
    _ca(ADMIN)
    with patch("acces.utilizator_dupa_id", return_value=None):
        r = await client.put(
            "/api/acces/utilizatori/nu-exista/stare", json={"activ": False},
            headers={"Authorization": "Bearer x"},
        )
    assert r.status_code == 404


async def test_supabase_refuza_modificarea(client):
    _ca(ADMIN)
    with patch("acces.utilizator_dupa_id", return_value=_tinta(ANA)), \
         patch("acces.seteaza_activ", side_effect=Exception("rate limit")):
        r = await client.put(
            f"/api/acces/utilizatori/id-{ANA}/stare", json={"activ": False},
            headers={"Authorization": "Bearer x"},
        )
    assert r.status_code == 502


async def test_lista_arata_starea_fiecarui_cont(client, _acces_la_toate_modulele):
    _ca(ADMIN)
    useri = [
        SimpleNamespace(id="u1", email=ADMIN, last_sign_in_at="2026-11-01T08:00:00Z", banned_until=None),
        SimpleNamespace(id="u2", email=ANA, last_sign_in_at="2026-10-01T08:00:00Z", banned_until=_peste(36500)),
        SimpleNamespace(id="u3", email="nou@totalsoft.ro", last_sign_in_at=None, banned_until=None),
    ]
    with patch("acces.utilizatori_supabase", return_value=useri):
        r = await client.get("/api/acces/config", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    dupa_email = {u["email"]: u for u in r.json()["utilizatori"]}

    assert dupa_email[ADMIN]["eu"] is True and dupa_email[ADMIN]["admin"] is True
    # folosit luni de zile și apoi blocat: „conectat" și „dezactivat" nu se exclud
    assert dupa_email[ANA]["conectat"] is True and dupa_email[ANA]["dezactivat"] is True
    assert dupa_email[ANA]["id"] == "u2" and dupa_email[ANA]["eu"] is False
    assert dupa_email["nou@totalsoft.ro"]["conectat"] is False
    assert dupa_email["nou@totalsoft.ro"]["dezactivat"] is False
