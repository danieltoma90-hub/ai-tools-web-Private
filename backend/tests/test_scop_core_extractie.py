# -*- coding: utf-8 -*-
"""Teste pentru segmentarea documentului suplimentar și propunerea de plasare
(Task 3 — `skills/scop_core/extractie.py`).

Regula pe care aceste teste o apără, mai presus de oricare alta: modelul NU
are voie să introducă o denumire de flux Charisma în datele întoarse — vezi
`test_denumire_charisma_inventata_de_model_nu_ajunge_in_rezultat`, testul
care probează exact asta. Toate testele lucrează pe răspunsuri de model
SIMULATE (monkeypatch pe `_call_groq`) — fără niciun apel de rețea.
"""
from __future__ import annotations

import json

import pytest
from docx import Document

from skills.scop_core import extractie
from skills.scop_core.charisma_core import SECTIUNI


def _docx(tmp_path, paragrafe=("Text simplu despre o cerință suplimentară.",)):
    p = tmp_path / "suplimentar.docx"
    d = Document()
    for text in paragrafe:
        d.add_paragraph(text)
    d.save(str(p))
    return p


def _simuleaza(monkeypatch, payload: str):
    async def fals(prompt, continut, max_tokens=4_000):
        return payload
    monkeypatch.setattr(extractie, "_call_groq", fals)


async def test_raspuns_bine_format_produce_elementele_asteptate(tmp_path, monkeypatch):
    payload = json.dumps({"elemente": [
        {"titlu": "Integrare cu cântarul electronic", "text": "Cântarul trimite greutatea automat.",
         "plasare": "vanzari", "fluxuri_legate": ["V2"]},
    ]})
    _simuleaza(monkeypatch, payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat == [{
        "titlu": "Integrare cu cântarul electronic",
        "text": "Cântarul trimite greutatea automat.",
        "plasare": "vanzari",
        "fluxuri_legate": ["V2"],
    }]


async def test_plasare_invalida_devine_propriu(tmp_path, monkeypatch):
    payload = json.dumps({"elemente": [
        {"titlu": "X", "text": "Y", "plasare": "modul-inexistent", "fluxuri_legate": []},
    ]})
    _simuleaza(monkeypatch, payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat[0]["plasare"] == "propriu"


async def test_plasare_lipsa_devine_propriu(tmp_path, monkeypatch):
    """`plasare` absentă din răspuns e la fel de invalidă ca una greșită —
    nu trebuie să ridice excepție, ci să cadă tot pe "propriu"."""
    payload = json.dumps({"elemente": [{"titlu": "X", "text": "Y", "fluxuri_legate": []}]})
    _simuleaza(monkeypatch, payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat[0]["plasare"] == "propriu"


async def test_cod_de_flux_inexistent_se_filtreaza(tmp_path, monkeypatch):
    payload = json.dumps({"elemente": [
        {"titlu": "X", "text": "Y", "plasare": "vanzari", "fluxuri_legate": ["V2", "ZZ9"]},
    ]})
    _simuleaza(monkeypatch, payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat[0]["fluxuri_legate"] == ["V2"]


async def test_element_fara_titlu_se_arunca(tmp_path, monkeypatch):
    payload = json.dumps({"elemente": [
        {"titlu": "", "text": "Text valid.", "plasare": "propriu", "fluxuri_legate": []},
        {"titlu": "Titlu valid", "text": "Alt text.", "plasare": "propriu", "fluxuri_legate": []},
    ]})
    _simuleaza(monkeypatch, payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert len(rezultat) == 1
    assert rezultat[0]["titlu"] == "Titlu valid"


async def test_element_fara_text_se_arunca(tmp_path, monkeypatch):
    payload = json.dumps({"elemente": [
        {"titlu": "Titlu fără corp", "text": "   ", "plasare": "propriu", "fluxuri_legate": []},
    ]})
    _simuleaza(monkeypatch, payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat == []


async def test_json_invalid_ridica_value_error(tmp_path, monkeypatch):
    _simuleaza(monkeypatch, "Ne pare rău, nu pot ajuta cu asta.")

    with pytest.raises(ValueError):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_lista_elemente_lipsa_nu_ridica_eroare_ci_da_lista_goala(tmp_path, monkeypatch):
    """JSON valid, dar fără cheia "elemente" (sau cu alt tip) — un răspuns
    garbage de conținut, nu de sintaxă. Nu trebuie să pice routerul, doar să
    nu propună nimic."""
    _simuleaza(monkeypatch, json.dumps({"altceva": "fara elemente"}))

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat == []


async def test_denumire_charisma_inventata_de_model_nu_ajunge_in_rezultat():
    """Testul central al Task 3. Modelul primește fluxurile doar ca perechi
    cod -> denumire și trebuie să răspundă STRICT prin cod — dar dacă totuși
    „uită" regula și scrie o denumire completă de tranzacție Charisma (aici,
    denumirea reală a fluxului V2, din `SECTIUNI`) în loc de cod în
    `fluxuri_legate`, acel șir de caractere nu are voie să ajungă în datele
    întoarse: nu se potrivește cu niciun cod real, deci se filtrează, exact ca
    un cod inexistent oarecare. Verificăm nu doar câmpul `fluxuri_legate`, ci
    întregul rezultat serializat — ca să nu existe nicio cale ocolitoare prin
    care denumirea inventată să se strecoare în `titlu` sau `text`."""
    denumire_reala = next(f.flux for s in SECTIUNI for f in s.fluxuri if f.cod == "V2")

    payload = json.dumps({"elemente": [
        {"titlu": "Discount la volum mare", "text": "Se acordă discount pentru comenzi peste 1000 buc.",
         "plasare": "vanzari", "fluxuri_legate": ["V2", denumire_reala]},
    ]})

    async def fals(prompt, continut, max_tokens=4_000):
        return payload

    from unittest.mock import patch
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    doc_path = tmp / "suplimentar.docx"
    d = Document()
    d.add_paragraph("Cerință suplimentară despre discount la volum mare.")
    d.save(str(doc_path))

    with patch.object(extractie, "_call_groq", fals):
        rezultat = await extractie.propune_elemente(doc_path)

    assert rezultat[0]["fluxuri_legate"] == ["V2"]
    assert denumire_reala not in json.dumps(rezultat, ensure_ascii=False)


async def test_prompt_refera_toate_cele_zece_chei_de_sectiune():
    """Promptul e sursa constrângerii — dacă nu enumeră toate cele zece chei
    valide, modelul nu are cum să le respecte."""
    prompt = extractie._construieste_prompt()
    for cheie in extractie.CHEI_SECTIUNI:
        assert cheie in prompt
    assert len(extractie.CHEI_SECTIUNI) == 10


async def test_context_fluxuri_contine_toate_cele_47_de_coduri_dar_nu_apar_ca_text_liber():
    context = extractie._context_fluxuri()
    coduri = extractie._coduri_valide()
    assert len(coduri) == 47
    for cod in coduri:
        assert cod in context


async def test_engine_groq_e_implicit(tmp_path, monkeypatch):
    """Pasul e opțional — nu trebuie să schimbe costul zero al capitolului
    standard, deci implicit rulează pe Groq (gratuit), nu pe Claude."""
    apelat = {}

    async def fals_groq(prompt, continut, max_tokens=4_000):
        apelat["engine"] = "groq"
        return json.dumps({"elemente": []})

    async def fals_claude(prompt, continut, max_tokens=4_000):
        apelat["engine"] = "claude"
        return json.dumps({"elemente": []})

    monkeypatch.setattr(extractie, "_call_groq", fals_groq)
    monkeypatch.setattr(extractie, "_call_claude", fals_claude)

    await extractie.propune_elemente(_docx(tmp_path))

    assert apelat["engine"] == "groq"


async def test_engine_claude_se_poate_alege_explicit(tmp_path, monkeypatch):
    apelat = {}

    async def fals_groq(prompt, continut, max_tokens=4_000):
        apelat["engine"] = "groq"
        return json.dumps({"elemente": []})

    async def fals_claude(prompt, continut, max_tokens=4_000):
        apelat["engine"] = "claude"
        return json.dumps({"elemente": []})

    monkeypatch.setattr(extractie, "_call_groq", fals_groq)
    monkeypatch.setattr(extractie, "_call_claude", fals_claude)

    await extractie.propune_elemente(_docx(tmp_path), engine="claude")

    assert apelat["engine"] == "claude"


async def test_groq_fara_cheie_ridica_mesaj_clar(tmp_path, monkeypatch):
    """O cheie lipsă e un mod de eșec frecvent (vezi apelul real din Step 5,
    unde GROQ_API_KEY lipsea efectiv) — trebuie să iasă ca mesaj clar în
    română, nu ca un `KeyError` brut pe numele variabilei de mediu."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_claude_fara_cheie_ridica_mesaj_clar(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        await extractie.propune_elemente(_docx(tmp_path), engine="claude")


async def test_document_gol_nu_apeleaza_deloc_modelul(tmp_path, monkeypatch):
    apelat = {"de_cate_ori": 0}

    async def fals(prompt, continut, max_tokens=4_000):
        apelat["de_cate_ori"] += 1
        return json.dumps({"elemente": []})
    monkeypatch.setattr(extractie, "_call_groq", fals)

    doc_gol = _docx(tmp_path, paragrafe=("   ", ""))
    rezultat = await extractie.propune_elemente(doc_gol)

    assert rezultat == []
    assert apelat["de_cate_ori"] == 0
