# -*- coding: utf-8 -*-
"""Erorile pe înțeles și jurnalul administratorului.

Ce apără testele:
- o eroare de API ajunge la utilizator tradusă, nu ca „Error code: 401 - {...}";
- o eroare de document își păstrează mesajul — nu devine „Claude nu a răspuns";
- fiecare eșec lasă în jurnal cine, ce modul și de ce;
- jurnalul îl vede doar administratorul.
"""
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx2
import pytest

import claude
import jobs
from ai_errors import e_eroare_ai, mesaj_pentru_utilizator
from auth import verify_token
from main import app

ADMIN = "daniel.toma@totalsoft.ro"


def _eroare_sdk(cls, status: int, mesaj: str):
    """O excepție reală a SDK-ului, cum o ridică în producție."""
    cerere = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(mesaj, response=httpx2.Response(status, request=cerere),
               body={"type": "error", "error": {"type": "x", "message": mesaj}})


@pytest.mark.parametrize(
    "exc,contine",
    [
        (_eroare_sdk(anthropic.AuthenticationError, 401, "invalid x-api-key"), "invalidă sau a fost revocată"),
        (_eroare_sdk(anthropic.BadRequestError, 400, "Your credit balance is too low"), "nu are credite"),
        (_eroare_sdk(anthropic.RateLimitError, 429, "rate_limit_error"), "limita de utilizare"),
        (_eroare_sdk(anthropic.InternalServerError, 529, "Overloaded"), "suprasolicitat"),
        (claude.RefuzModel("bio"), "a refuzat cererea"),
        (RuntimeError("ANTHROPIC_API_KEY lipsă pe server"), "lipsește pe server"),
    ],
)
def test_erorile_ai_sunt_traduse(exc, contine):
    assert e_eroare_ai(exc)
    mesaj = mesaj_pentru_utilizator(exc)
    assert contine in mesaj.lower()
    assert mesaj[0].isupper()
    assert "Error code" not in mesaj


def test_erorile_de_document_isi_pastreaza_mesajul():
    """Un fișier greșit nu e vina lui Claude — altfel omul ar căuta problema în cheie."""
    exc = ValueError("Specificația nu conține text care să poată fi citit.")
    assert not e_eroare_ai(exc)
    assert mesaj_pentru_utilizator(exc) == "Specificația nu conține text care să poată fi citit."


def test_esueaza_marcheaza_jobul_si_scrie_in_jurnal(jurnal_in_memorie):
    job_id = jobs.create_job("ana@totalsoft.ro", "minuta")
    jobs.esueaza(job_id, _eroare_sdk(anthropic.AuthenticationError, 401, "invalid x-api-key"))

    job = jobs.get_job(job_id)
    assert job["status"] == "error"
    assert "invalidă sau a fost revocată" in job["error"]
    assert "modul" not in job  # modulul e doar pentru jurnal, nu ajunge în pagină

    intrare = jurnal_in_memorie[0]
    assert intrare["modul"] == "minuta"
    assert intrare["email"] == "ana@totalsoft.ro"
    assert intrare["mesaj"] == job["error"]
    assert "AuthenticationError" in intrare["tehnic"]  # pentru admin: și eroarea brută


def test_mesajul_explicit_are_prioritate(jurnal_in_memorie):
    job_id = jobs.create_job("ion@totalsoft.ro", "scop-core")
    jobs.esueaza(job_id, ValueError("x"), "Documentul suplimentar e prea mare.")
    assert jobs.get_job(job_id)["error"] == "Documentul suplimentar e prea mare."
    assert jurnal_in_memorie[0]["mesaj"] == "Documentul suplimentar e prea mare."


async def test_jurnalul_il_vede_doar_adminul(client, jurnal_in_memorie):
    jurnal_in_memorie.append({"modul": "minuta", "email": "a@b.ro", "mesaj": "m", "tehnic": "t"})

    app.dependency_overrides[verify_token] = lambda: {"id": "u", "email": "ana@totalsoft.ro"}
    try:
        r = await client.get("/api/acces/jurnal", headers={"Authorization": "Bearer x"})
        assert r.status_code == 403

        app.dependency_overrides[verify_token] = lambda: {"id": "u", "email": ADMIN}
        r = await client.get("/api/acces/jurnal", headers={"Authorization": "Bearer x"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["intrari"][0]["modul"] == "minuta"


async def test_o_generare_esuata_in_productie_ajunge_in_jurnal(client, jurnal_in_memorie, monkeypatch):
    """De la capăt la capăt: Training cu cheia revocată → job cu mesaj tradus + intrare în jurnal."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    # ca obiectul User din Supabase: emailul e atribut, nu cheie
    app.dependency_overrides[verify_token] = lambda: SimpleNamespace(id="u", email="ana@totalsoft.ro")
    try:
        with patch("routers.training.run_training_pipeline",
                   side_effect=_eroare_sdk(anthropic.AuthenticationError, 401, "invalid x-api-key")):
            r = await client.post(
                "/api/training/generate", data={"tip": "core", "zile": "3"},
                headers={"Authorization": "Bearer x"},
            )
            job = await client.get(f"/api/training/job/{r.json()['job_id']}",
                                   headers={"Authorization": "Bearer x"})
    finally:
        app.dependency_overrides.clear()
    assert "invalidă sau a fost revocată" in job.json()["error"]
    assert jurnal_in_memorie[0]["modul"] == "training"
    assert jurnal_in_memorie[0]["email"] == "ana@totalsoft.ro"
