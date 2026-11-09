# -*- coding: utf-8 -*-
"""Teste pentru segmentarea documentului suplimentar și propunerea de plasare
(Task 3 — `skills/scop_core/extractie.py`).

Regula pe care aceste teste o apără, mai presus de oricare alta: modelul NU
are voie să introducă o denumire de flux Charisma în datele întoarse — vezi
`test_denumire_charisma_inventata_de_model_nu_ajunge_in_rezultat`, testul
care probează exact asta.

Toate testele lucrează pe răspunsuri de model SIMULATE, injectate în locul lui
`claude.raspunde` — drumul comun spre Claude — fără niciun apel de rețea real.
Forma cererii pe fir (SDK-ul real) e verificată separat, în test_claude.py.
"""
from __future__ import annotations

import json

import pytest
from docx import Document

import claude
from skills.scop_core import extractie
from skills.scop_core.charisma_core import SECTIUNI

# Ce întoarce Claude în testul curent; `_simuleaza` îl setează.
_SIM: dict = {}


@pytest.fixture(autouse=True)
def _claude_simulat(monkeypatch):
    _SIM.clear()

    async def _raspunde(intrebare, **kw):
        captura = _SIM.get("captura")
        if captura is not None:
            captura["intrebare"] = intrebare
            captura.update(kw)
        if "eroare" in _SIM:
            raise _SIM["eroare"]
        return claude.Raspuns(_SIM.get("payload", ""), _SIM.get("stop", "end_turn"))

    monkeypatch.setattr(claude, "raspunde", _raspunde)


def _docx(tmp_path, paragrafe=("Text simplu despre o cerință suplimentară.",)):
    p = tmp_path / "suplimentar.docx"
    d = Document()
    for text in paragrafe:
        d.add_paragraph(text)
    d.save(str(p))
    return p


def _simuleaza(payload: str, captura: dict | None = None, stop: str = "end_turn") -> None:
    """Claude întoarce `payload`, oprit cu `stop`. Cu `captura`, se salvează acolo
    întrebarea și parametrii apelului — ca să verificăm ce se trimite."""
    _SIM.update(payload=payload, captura=captura, stop=stop)


@pytest.mark.asyncio
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
    """`null` e JSON sintactic valid — parserul îl întoarce ca
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
    trimis lui Claude: acolo trăiesc regulile, nu în mesajul
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
    """Catalogul de fluxuri și regulile de plasare stau în `system`, iar textul
    documentului clientului (și NUMAI el) în mesajul utilizatorului."""
    captura: dict = {}
    _simuleaza(json.dumps({"elemente": []}), captura=captura)

    doc_path = _docx(tmp_path, paragrafe=("Paragraf unic despre o cerință suplimentară.",))
    await extractie.propune_elemente(doc_path)

    assert "vanzari" in captura["system"]  # o cheie de secțiune, din reguli
    assert "Paragraf unic despre o cerință suplimentară." in captura["intrebare"]
    # regulile nu trebuie duplicate în mesajul utilizatorului, nici textul în system
    assert "Paragraf unic despre o cerință suplimentară." not in captura["system"]
    assert "vanzari" not in captura["intrebare"]


@pytest.mark.asyncio
async def test_engine_nu_mai_este_parametru_acceptat(tmp_path):
    """Înainte, `engine="groq"|"claude"` alegea providerul. Cu un singur
    drum comun (`claude.py`), parametrul a fost eliminat — nu păstrat și
    ignorat — tocmai ca un apel vechi care încă îl trimite să pice tare și
    vizibil (`TypeError`), nu tăcut, ca routerul (Task 5) și frontend-ul
    (Task 6) să nu poată oferi o alegere de provider care nu mai există."""
    with pytest.raises(TypeError):
        await extractie.propune_elemente(_docx(tmp_path), engine="claude")


async def test_lipsa_cheie_anthropic_urca_cu_mesaj_clar(tmp_path):
    """O cheie lipsă trebuie să iasă ca mesaj clar, care numește variabila de
    mediu — nu ca un `KeyError` brut și nu înghițită."""
    _SIM["eroare"] = RuntimeError("ANTHROPIC_API_KEY lipsă pe server")

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        await extractie.propune_elemente(_docx(tmp_path))


def test_extrage_text_include_randurile_tabelului(tmp_path):
    """Documentul standard TotalSoft (caietul de sarcini) e o matrice de
    cerințe — un tabel, nu paragrafe. `doc.paragraphs` omite tabelele cu
    totul: fără parcurgerea corpului în ordinea lui reală (`_iter_blocuri`),
    un asemenea document ar produce text aproape gol, `propune_elemente` ar
    întoarce `[]` FĂRĂ SĂ APELEZE deloc modelul, iar utilizatorul ar vedea
    „niciun element găsit” — pierdere tăcută și totală a cerințelor
    clientului. Documentul de test are atât un titlu și un paragraf, cât și
    un tabel de doua randuri — toate trei trebuie să ajungă în text."""
    d = Document()
    d.add_heading("Cerințe suplimentare", level=1)
    d.add_paragraph("Un paragraf normal de context.")
    tabel = d.add_table(rows=2, cols=2)
    tabel.rows[0].cells[0].text = "Cod"
    tabel.rows[0].cells[1].text = "Cerință"
    tabel.rows[1].cells[0].text = "C1"
    tabel.rows[1].cells[1].text = "Sistemul trebuie să valideze codul de bare la recepție."
    cale = tmp_path / "cu_tabel.docx"
    d.save(str(cale))

    text = extractie._extrage_text(cale)

    assert "Cerințe suplimentare" in text
    assert "Un paragraf normal de context." in text
    assert "C1" in text
    assert "Sistemul trebuie să valideze codul de bare la recepție." in text


async def test_apelul_lasa_loc_si_textului_verbatim_si_gandirii(tmp_path):
    """`text` se extrage verbatim — lungimea lui scalează cu documentul. Pe
    Opus 5.5 gândirea se numără tot în `max_tokens`, deci limita trebuie să
    încapă ambele."""
    captura: dict = {}
    _simuleaza(json.dumps({"elemente": []}), captura=captura)

    await extractie.propune_elemente(_docx(tmp_path))

    assert captura["max_tokens"] == extractie.MAX_TOKENS_RASPUNS >= 32000


@pytest.mark.asyncio
async def test_raspuns_trunchiat_da_mesaj_distinct_de_document_prea_mare(tmp_path):
    """Un răspuns tăiat la mijlocul JSON-ului (depășire de `max_tokens`) nu
    trebuie confundat cu un răspuns garbage oarecare din alt motiv (ex.
    modelul refuză cererea) — utilizatorul trebuie să înțeleagă că documentul
    e prea mare pentru un singur apel, nu că extragerea a eșuat aleatoriu."""
    trunchiat = '{"elemente": [{"titlu": "X", "text": "Un text lung care se taie la mij'
    _simuleaza(trunchiat, stop="max_tokens")

    with pytest.raises(ValueError, match="prea mare"):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_raspuns_garbage_nu_trunchiat_pastreaza_mesajul_vechi(tmp_path):
    """Un răspuns care nu seamănă deloc cu JSON (ex. refuzul modelului) nu
    trebuie etichetat drept „document prea mare” — acela vine doar dintr-o
    oprire la `max_tokens`, nu din orice eșec de parsare."""
    _simuleaza("Ne pare rău, nu pot ajuta cu asta.")

    with pytest.raises(ValueError, match="nu este JSON valid"):
        await extractie.propune_elemente(_docx(tmp_path))


async def test_document_gol_nu_apeleaza_deloc_modelul(tmp_path, monkeypatch):
    apelat = {"de_cate_ori": 0}

    async def fals(intrebare, **kw):
        apelat["de_cate_ori"] += 1
        return claude.Raspuns(json.dumps({"elemente": []}), "end_turn")
    monkeypatch.setattr(claude, "raspunde", fals)

    doc_gol = _docx(tmp_path, paragrafe=("   ", ""))
    rezultat = await extractie.propune_elemente(doc_gol)

    assert rezultat == []
    assert apelat["de_cate_ori"] == 0
