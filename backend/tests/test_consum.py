# -*- coding: utf-8 -*-
"""Consumul Claude pe generare: numărat corect, notat și când generarea pică,
iar efortul impus de administrator ajunge în toate apelurile."""
import asyncio
from types import SimpleNamespace

import pytest

import claude
import consum
import jobs
from auth import verify_token
from main import app


def _usage(intrare=0, iesire=0, citit=0, scris=0):
    return SimpleNamespace(input_tokens=intrare, output_tokens=iesire,
                           cache_read_input_tokens=citit, cache_creation_input_tokens=scris)


def test_costul_foloseste_preturile_modelului():
    c = claude.Consum()
    # 1M intrare + 1M ieșire + 1M citit + 1M scris, pe Opus 5.5: 4 + 20 + 0,20 + 5
    c.adauga(_usage(1_000_000, 1_000_000, 1_000_000, 1_000_000), "claude-opus-5-5", "medium")
    assert c.cost_usd == pytest.approx(29.20)
    assert c.apeluri == 1 and c.eforturi == {"medium"}


def test_modelul_necunoscut_se_socoteste_la_pretul_implicit():
    c = claude.Consum()
    c.adauga(_usage(iesire=1_000_000), "claude-model-viitor", "low")
    assert c.cost_usd == pytest.approx(20.0)


async def test_contorul_prinde_si_apelurile_paralele():
    """Minuta pornește extragerile cu asyncio.gather: toate intră în același contor."""
    async def apel():
        claude._jurnalizeaza(SimpleNamespace(usage=_usage(100, 10), model="claude-opus-5-5",
                                             stop_reason="end_turn"), "medium")

    with claude.numara() as c:
        await asyncio.gather(apel(), apel(), apel())
    assert c.apeluri == 3 and c.intrare == 300 and c.iesire == 30


def test_efortul_impus_trece_peste_cel_al_modulului():
    with claude.numara("low"):
        p = claude._parametri(continut="x", system=None, max_tokens=10, efort="medium",
                              cu_fallback=False)
    assert p["output_config"] == {"effort": "low"}
    # în afara blocului, modulul își folosește efortul lui
    p = claude._parametri(continut="x", system=None, max_tokens=10, efort="medium", cu_fallback=False)
    assert p["output_config"] == {"effort": "medium"}


def test_efortul_necunoscut_e_ignorat():
    with claude.numara("maxim-te-rog"):
        p = claude._parametri(continut="x", system=None, max_tokens=10, efort="medium",
                              cu_fallback=False)
    assert p["output_config"] == {"effort": "medium"}


def _apel_fals(intrare: int, iesire: int):
    claude._jurnalizeaza(SimpleNamespace(usage=_usage(intrare, iesire), model="claude-opus-5-5",
                                         stop_reason="end_turn"), "medium")


async def test_ruleaza_noteaza_consumul_generarii_reusite():
    job_id = jobs.create_job("ana@totalsoft.ro", "minuta")

    async def lucrare():
        _apel_fals(1000, 200)
        _apel_fals(1000, 300)
        return {"filename": "m.docx"}

    await jobs.ruleaza(job_id, lucrare)
    assert jobs.get_job(job_id)["status"] == "done"
    [intrare] = consum._intrari
    assert intrare["modul"] == "minuta" and intrare["email"] == "ana@totalsoft.ro"
    assert intrare["apeluri"] == 2 and intrare["iesire"] == 500 and intrare["reusit"] is True


async def test_ruleaza_noteaza_consumul_si_cand_generarea_pica(jurnal_in_memorie):
    job_id = jobs.create_job("ana@totalsoft.ro", "scenarii")

    async def lucrare():
        _apel_fals(5000, 100)
        raise RuntimeError("lotul 2 a picat")

    await jobs.ruleaza(job_id, lucrare)
    assert jobs.get_job(job_id)["status"] == "error"
    [intrare] = consum._intrari
    assert intrare["reusit"] is False and intrare["intrare"] == 5000
    assert jurnal_in_memorie[0]["modul"] == "scenarii"


async def test_generarea_fara_claude_nu_se_noteaza():
    job_id = jobs.create_job("ana@totalsoft.ro", "training")

    async def lucrare():
        return {"filename": "agenda.docx"}

    await jobs.ruleaza(job_id, lucrare)
    assert consum._intrari == []


async def test_ruleaza_impune_efortul_cerut():
    job_id = jobs.create_job("admin@totalsoft.ro", "minuta")
    vazut = {}

    async def lucrare():
        vazut["efort"] = claude._parametri(continut="x", system=None, max_tokens=10,
                                           efort="medium", cu_fallback=False)["output_config"]
        _apel_fals(10, 10)
        return {}

    await jobs.ruleaza(job_id, lucrare, efort="low")
    assert vazut["efort"] == {"effort": "low"}
    assert consum._intrari[0]["efort"] == "low"


def test_sumarul_aduna_pe_modul_si_pe_coleg():
    c1, c2 = claude.Consum(), claude.Consum()
    c1.adauga(_usage(iesire=100_000), "claude-opus-5-5", "medium")  # 2 $
    c2.adauga(_usage(iesire=50_000), "claude-opus-5-5", "low")  # 1 $
    consum.inregistreaza("minuta", "ana@x.ro", c1)
    consum.inregistreaza("minuta", "dan@x.ro", c2)
    consum.inregistreaza("mockup", "ana@x.ro", c2)

    s = consum.sumar(zile=30)
    assert s["total"]["generari"] == 3 and s["total"]["cost_usd"] == pytest.approx(4.0)
    minuta = next(r for r in s["pe_modul"] if r["modul"] == "minuta")
    assert minuta["generari"] == 2 and minuta["cost_mediu_usd"] == pytest.approx(1.5)
    assert s["pe_utilizator"][0]["email"] == "ana@x.ro"  # cel mai mare cost primul
    assert s["recente"][0]["modul"] == "mockup"  # cea mai nouă prima


def test_sumarul_lasa_deoparte_ce_e_mai_vechi_de_perioada():
    c = claude.Consum()
    c.adauga(_usage(iesire=1000), "claude-opus-5-5", "medium")
    consum.inregistreaza("minuta", "ana@x.ro", c)
    consum._intrari[0]["cand"] = "2020-01-01T00:00:00+00:00"
    assert consum.sumar(zile=30)["total"]["generari"] == 0


async def test_doar_administratorul_vede_consumul(client, monkeypatch):
    import acces

    monkeypatch.setattr(acces, "admin_emails", lambda: {"admin@totalsoft.ro"})
    app.dependency_overrides[verify_token] = lambda: SimpleNamespace(email="coleg@totalsoft.ro")
    try:
        r = await client.get("/api/acces/consum", headers={"Authorization": "Bearer x"})
        assert r.status_code == 403
        app.dependency_overrides[verify_token] = lambda: SimpleNamespace(email="admin@totalsoft.ro")
        r = await client.get("/api/acces/consum?zile=7", headers={"Authorization": "Bearer x"})
        assert r.status_code == 200 and r.json()["zile"] == 7
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("email,asteptat", [
    ("admin@totalsoft.ro", "low"),   # administratorul își poate impune efortul
    ("coleg@totalsoft.ro", None),    # pentru ceilalți, câmpul se ignoră
])
async def test_efortul_minutei_e_doar_al_administratorului(client, monkeypatch, tmp_path, email, asteptat):
    from unittest.mock import AsyncMock, patch

    import acces

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(acces, "admin_emails", lambda: {"admin@totalsoft.ro"})
    transcript = tmp_path / "t.vtt"
    transcript.write_bytes(b"WEBVTT\n\n")
    app.dependency_overrides[verify_token] = lambda: {"id": "u1", "email": email}
    try:
        with patch("routers.minuta._run_job", new_callable=AsyncMock) as rulat, \
             patch("routers.minuta.download_upload", return_value=transcript), \
             patch("routers.minuta.admin_emails", lambda: {"admin@totalsoft.ro"}):
            r = await client.post(
                "/api/minuta",
                data={"storage_path": "minuta/t.vtt", "filename": "t.vtt", "efort": "low"},
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert rulat.call_args.kwargs["efort"] == asteptat
