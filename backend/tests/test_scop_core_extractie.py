# -*- coding: utf-8 -*-
"""Teste pentru segmentarea documentului suplimentar și propunerea de plasare
(Task 3 — `skills/scop_core/extractie.py`).

Regula pe care aceste teste o apără, mai presus de oricare alta: modelul NU
are voie să introducă o denumire de flux Charisma în datele întoarse — vezi
`test_denumire_charisma_inventata_de_model_nu_ajunge_in_rezultat`, testul
care probează exact asta.

Toate testele lucrează pe răspunsuri de model SIMULATE, injectate la nivelul
de transport HTTP al lui `llm_client` (`llm_client.TRANSPORT`, un
`httpx.MockTransport`) — fără niciun apel de rețea real. Acesta e seam-ul
comun al repo-ului pentru asta, vezi `test_llm_client.py`: modulul nu mai
are apeluri proprii `_call_groq`/`_call_claude` de monkeypatch-uit direct.
"""
from __future__ import annotations

import json

import httpx
import pytest
from docx import Document

import llm_client
from skills.scop_core import extractie
from skills.scop_core.charisma_core import SECTIUNI


@pytest.fixture(autouse=True)
def _reset_llm_client(monkeypatch):
    """Cheie validă implicit, fără throttle/retry de test — la fel ca în
    `test_llm_client.py`. Testele care vor să probeze cheia lipsă o șterg
    explicit din mediu."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "MIN_CALL_INTERVAL_S", 0)
    monkeypatch.setattr(llm_client, "RETRY_DELAYS", [0, 0, 0])
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0
    yield
    llm_client.TRANSPORT = None


def _docx(tmp_path, paragrafe=("Text simplu despre o cerință suplimentară.",)):
    p = tmp_path / "suplimentar.docx"
    d = Document()
    for text in paragrafe:
        d.add_paragraph(text)
    d.save(str(p))
    return p


def _raspuns_mistral(content: str, total_tokens: int = 50) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"total_tokens": total_tokens},
    }


def _simuleaza(payload: str, captura: dict | None = None) -> None:
    """Instalează un `MockTransport` care întoarce `payload` ca text de
    răspuns al modelului, indiferent de conținutul cererii. Dacă i se dă
    `captura`, salvează acolo body-ul cererii trimise — util ca să verificăm
    ce ajunge de fapt în `system`/`user`."""
    def handler(request: httpx.Request) -> httpx.Response:
        if captura is not None:
            captura["body"] = json.loads(request.content)
            captura["headers"] = request.headers
        return httpx.Response(200, json=_raspuns_mistral(payload))

    llm_client.TRANSPORT = httpx.MockTransport(handler)


def _simuleaza_eroare(status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "eroare simulată"})

    llm_client.TRANSPORT = httpx.MockTransport(handler)


async def test_raspuns_bine_format_produce_elementele_asteptate(tmp_path):
    payload = json.dumps({"elemente": [
        {"titlu": "Integrare cu cântarul electronic", "text": "Cântarul trimite greutatea automat.",
         "plasare": "vanzari", "fluxuri_legate": ["V2"]},
    ]})
    _simuleaza(payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat == [{
        "titlu": "Integrare cu cântarul electronic",
        "text": "Cântarul trimite greutatea automat.",
        "plasare": "vanzari",
        "fluxuri_legate": ["V2"],
    }]


async def test_plasare_invalida_devine_propriu(tmp_path):
    payload = json.dumps({"elemente": [
        {"titlu": "X", "text": "Y", "plasare": "modul-inexistent", "fluxuri_legate": []},
    ]})
    _simuleaza(payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat[0]["plasare"] == "propriu"


async def test_plasare_lipsa_devine_propriu(tmp_path):
    """`plasare` absentă din răspuns e la fel de invalidă ca una greșită —
    nu trebuie să ridice excepție, ci să cadă tot pe "propriu"."""
    payload = json.dumps({"elemente": [{"titlu": "X", "text": "Y", "fluxuri_legate": []}]})
    _simuleaza(payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat[0]["plasare"] == "propriu"


async def test_cod_de_flux_inexistent_se_filtreaza(tmp_path):
    payload = json.dumps({"elemente": [
        {"titlu": "X", "text": "Y", "plasare": "vanzari", "fluxuri_legate": ["V2", "ZZ9"]},
    ]})
    _simuleaza(payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat[0]["fluxuri_legate"] == ["V2"]


async def test_cod_cu_spatii_parazite_e_recuperat_dar_minuscule_tot_se_arunca(tmp_path):
    """Zgomot de formatare de la un model gratuit (spații în plus în jurul
    codului) nu trebuie să piardă un flux legat valid — dar nu facem
    case-folding: "MF1" și "M1" sunt coduri distincte, ale unor secțiuni
    diferite, iar a le confunda ar fi un pas spre ghicit."""
    payload = json.dumps({"elemente": [
        {"titlu": "X", "text": "Y", "plasare": "vanzari", "fluxuri_legate": [" V2 ", "v2"]},
    ]})
    _simuleaza(payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat[0]["fluxuri_legate"] == ["V2"]


async def test_element_fara_titlu_se_arunca(tmp_path):
    payload = json.dumps({"elemente": [
        {"titlu": "", "text": "Text valid.", "plasare": "propriu", "fluxuri_legate": []},
        {"titlu": "Titlu valid", "text": "Alt text.", "plasare": "propriu", "fluxuri_legate": []},
    ]})
    _simuleaza(payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert len(rezultat) == 1
    assert rezultat[0]["titlu"] == "Titlu valid"


async def test_element_fara_text_se_arunca(tmp_path):
    payload = json.dumps({"elemente": [
        {"titlu": "Titlu fără corp", "text": "   ", "plasare": "propriu", "fluxuri_legate": []},
    ]})
    _simuleaza(payload)

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat == []


async def test_json_invalid_ridica_value_error(tmp_path):
    _simuleaza("Ne pare rău, nu pot ajuta cu asta.")

    with pytest.raises(ValueError):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_raspuns_json_null_ridica_value_error(tmp_path):
    """`null` e JSON sintactic valid — `llm_client.parse_json` îl întoarce ca
    `None`, fără să ridice excepție. Fără verificarea de tip imediat după,
    `None.get("elemente")` ar pica cu `AttributeError` necontrolat, nu cu
    mesajul românesc pe care routerul îl poate arăta."""
    _simuleaza("null")

    with pytest.raises(ValueError):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_raspuns_json_lista_bruta_ridica_value_error(tmp_path):
    """O listă JSON la nivelul de bază (fără obiectul cu cheia "elemente")
    e tot sintactic validă — trebuie tratată ca formă greșită, nu ca o
    excepție brută de tip `AttributeError`."""
    _simuleaza(json.dumps(["a", "b", "c"]))

    with pytest.raises(ValueError):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_raspuns_json_numar_brut_ridica_value_error(tmp_path):
    _simuleaza("42")

    with pytest.raises(ValueError):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_raspuns_json_sir_brut_ridica_value_error(tmp_path):
    _simuleaza(json.dumps("doar un șir, nu un obiect"))

    with pytest.raises(ValueError):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_lista_elemente_lipsa_nu_ridica_eroare_ci_da_lista_goala(tmp_path):
    """JSON valid, dar fără cheia "elemente" (sau cu alt tip) — un răspuns
    garbage de conținut, nu de sintaxă. Nu trebuie să pice routerul, doar să
    nu propună nimic."""
    _simuleaza(json.dumps({"altceva": "fara elemente"}))

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat == []


async def test_denumire_charisma_inventata_de_model_nu_ajunge_in_rezultat(tmp_path):
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
    _simuleaza(payload)

    doc_path = _docx(tmp_path, paragrafe=("Cerință suplimentară despre discount la volum mare.",))
    rezultat = await extractie.propune_elemente(doc_path)

    assert rezultat[0]["fluxuri_legate"] == ["V2"]
    assert denumire_reala not in json.dumps(rezultat, ensure_ascii=False)


async def test_prompt_cere_extras_verbatim_nu_reformulare():
    """Nu poate exista un test unitar care să detecteze o invenție a modelului
    (asta ar cere un apel real) — dar putem apăra promptul care o previne: dacă
    o editare viitoare scoate accidental instrucțiunea de extras verbatim,
    acest test trebuie să pice, ca semnal că fidelitatea textului către sursă
    nu mai e garantată prin prompt. Nu dovedește nimic despre ce face modelul
    efectiv — dovedește doar că instrucțiunea încă există în textul trimis."""
    system_prompt = extractie._construieste_system_prompt()
    assert "EXTRAS COPIAT" in system_prompt
    assert "praguri valorice" in system_prompt
    assert "nu inventa un titlu" in system_prompt.lower()


async def test_prompt_refera_toate_cele_zece_chei_de_sectiune():
    """Promptul e sursa constrângerii — dacă nu enumeră toate cele zece chei
    valide, modelul nu are cum să le respecte. Rulează pe mesajul `system`
    trimis lui `llm_client.chat`: acolo trăiesc regulile, nu în mesajul
    `user` (care e strict textul documentului clientului)."""
    system_prompt = extractie._construieste_system_prompt()
    for cheie in extractie.CHEI_SECTIUNI:
        assert cheie in system_prompt
    assert len(extractie.CHEI_SECTIUNI) == 10


async def test_context_fluxuri_contine_toate_cele_47_de_coduri_dar_nu_apar_ca_text_liber():
    context = extractie._context_fluxuri()
    coduri = extractie._coduri_valide()
    assert len(coduri) == 47
    for cod in coduri:
        assert cod in context


async def test_apelul_trimite_reguli_in_system_si_documentul_in_user(tmp_path):
    """Cu un singur provider comun (`llm_client`), nu mai există un `engine`
    de ales — dar rămâne de verificat CE se trimite: catalogul de fluxuri și
    regulile de plasare trebuie să fie în mesajul `system`, iar textul
    documentului clientului (și NUMAI el) în mesajul `user`, cu apelul cerut
    explicit în format JSON. Această cerere de format e motivul pentru care
    varianta veche a acestui test ("engine implicit e groq") nu mai poate fi
    exprimată identic: nu mai există un al doilea furnizor cu care să
    comparăm alegerea implicită — vezi și
    `test_engine_nu_mai_este_parametru_acceptat` mai jos."""
    captura: dict = {}
    _simuleaza(json.dumps({"elemente": []}), captura=captura)

    doc_path = _docx(tmp_path, paragrafe=("Paragraf unic despre o cerință suplimentară.",))
    await extractie.propune_elemente(doc_path)

    body = captura["body"]
    assert body["messages"][0]["role"] == "system"
    assert "vanzari" in body["messages"][0]["content"]  # o cheie de secțiune, din reguli
    assert body["messages"][1]["role"] == "user"
    assert "Paragraf unic despre o cerință suplimentară." in body["messages"][1]["content"]
    # regulile nu trebuie duplicate în mesajul user, nici textul in system
    assert "Paragraf unic despre o cerință suplimentară." not in body["messages"][0]["content"]
    assert body["response_format"] == {"type": "json_object"}
    assert captura["headers"]["authorization"] == "Bearer test-key"


async def test_engine_nu_mai_este_parametru_acceptat(tmp_path):
    """Înainte, `engine="groq"|"claude"` alegea providerul. Cu un singur
    furnizor comun (`llm_client`), parametrul a fost eliminat — nu păstrat și
    ignorat — tocmai ca un apel vechi care încă îl trimite să pice tare și
    vizibil (`TypeError`), nu tăcut, ca routerul (Task 5) și frontend-ul
    (Task 6) să nu poată oferi o alegere de provider care nu mai există."""
    with pytest.raises(TypeError):
        await extractie.propune_elemente(_docx(tmp_path), engine="claude")


async def test_lipsa_cheie_mistral_ridica_mesaj_clar(tmp_path, monkeypatch):
    """O cheie lipsă e un mod de eșec frecvent (vezi apelul real din Step 5,
    unde GROQ_API_KEY lipsea efectiv) — trebuie să iasă ca mesaj clar în
    română, care numește variabila de mediu, nu ca un `KeyError` brut.
    Verificarea trăiește acum în `llm_client._api_key` (`RuntimeError`, nu
    `ValueError` — modulul nu mai reimplementează propria verificare de
    cheie, ci se bazează pe cea a clientului comun), dar claritatea
    mesajului pentru utilizator rămâne."""
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_lipsa_groq_si_anthropic_key_nu_afecteaza_apelul(tmp_path, monkeypatch):
    """Regresie pentru cuplarea veche: acest modul nu mai citește deloc
    `GROQ_API_KEY`/`ANTHROPIC_API_KEY` — chiar șterse amândouă din mediu,
    apelul trebuie să meargă normal, cât timp `MISTRAL_API_KEY` (singura
    cheie folosită acum) e prezentă."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _simuleaza(json.dumps({"elemente": []}))

    rezultat = await extractie.propune_elemente(_docx(tmp_path))

    assert rezultat == []


async def test_document_gol_nu_apeleaza_deloc_modelul(tmp_path, monkeypatch):
    apelat = {"de_cate_ori": 0}

    async def fals(system, user, max_tokens=4000, json_mode=True):
        apelat["de_cate_ori"] += 1
        return json.dumps({"elemente": []})
    monkeypatch.setattr(llm_client, "chat", fals)

    doc_gol = _docx(tmp_path, paragrafe=("   ", ""))
    rezultat = await extractie.propune_elemente(doc_gol)

    assert rezultat == []
    assert apelat["de_cate_ori"] == 0
