"""Notițele echipei din ședință și înregistrările aceleiași zile reunite într-o minută — metoda din
minutele VEDAŞ (16–19.10.2026), adusă pe site."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "minuta" / "scripts"))
from build_minuta import _fara_marcaje  # noqa: E402
from limba import LEGEND, legenda  # noqa: E402
from reguli import build_rules  # noqa: E402
from transcript_prep import prepare_transcript, prepare_transcripts  # noqa: E402

from auth import verify_token  # noqa: E402
from main import app  # noqa: E402
from pipelines.minuta_pipeline import run_minuta_pipeline  # noqa: E402

VTT_1 = "WEBVTT\n\nid-1\n00:00:01.000 --> 00:00:04.000\n<v Ion Popescu>Bugetul este de 5 milioane.</v>\n"
VTT_2 = "WEBVTT\n\nid-1\n00:00:01.000 --> 00:00:03.000\n<v Ana Ionescu>Contoarele se schimbă la 10 ani.</v>\n"
META = {"subiect": "Analiză", "nume_client": "Client Test", "data": "16.10.2026",
        "participanti": {"TotalSoft": ["Ion Popescu"]}}
SECTIONS = {"context_si_scop": [{"type": "bullets", "items": ["Scopul ședinței."]}],
            "sectiuni": [{"titlu": "Buget", "blocuri": [{"type": "paragraph", "text": "5 milioane."}]}]}
PROFILE = {"profil_beneficiar": [], "cerinte_beneficiar": [], "puncte_deschise": []}


def _vtt(tmp_path: Path, nume: str, text: str) -> Path:
    cale = tmp_path / nume
    cale.write_text(text, encoding="utf-8")
    return cale


# ── transcrierea ─────────────────────────────────────────────────────────────

def test_o_singura_inregistrare_ramane_ca_inainte(tmp_path):
    cale = _vtt(tmp_path, "a.vtt", VTT_1)
    assert prepare_transcripts([(cale, "a")]) == prepare_transcript(cale)


def test_mai_multe_inregistrari_au_antet_si_numarul_inaintea_orei(tmp_path):
    a, b = _vtt(tmp_path, "a.vtt", VTT_1), _vtt(tmp_path, "b.vtt", VTT_2)
    text = prepare_transcripts([(a, "Ziua 3"), (b, "Ziua 3 (1)")])
    assert text.index("=== Înregistrarea 1 din 2: „Ziua 3” ===") < text.index(
        "=== Înregistrarea 2 din 2: „Ziua 3 (1)” ===")
    assert "[(1) 00:00:01] Ion Popescu: Bugetul este de 5 milioane." in text
    assert "[(2) 00:00:01] Ana Ionescu: Contoarele se schimbă la 10 ani." in text


# ── reguli, legendă, titlul fișierului ───────────────────────────────────────

def test_regulile_pentru_notite_si_inregistrari_apar_doar_cand_e_cazul():
    baza = build_rules(marcaje=True)
    assert "Notițele echipei din ședință" not in baza and "Mai multe înregistrări" not in baza
    assert "[NOTIȚE" not in baza

    cu_notite = build_rules(marcaje=True, notite=True)
    assert "Notițele echipei din ședință" in cu_notite
    assert "[NOTIȚE: în transcriere" in cu_notite and "[NOTES: …]" in cu_notite
    # marcajul se cere numai împreună cu celelalte marcaje
    assert "[NOTIȚE" not in build_rules(marcaje=False, notite=True)

    assert "Mai multe înregistrări din aceeași zi" in build_rules(inregistrari=3)


def test_legenda_adauga_marcajul_notitelor_doar_cu_notite():
    assert legenda("ro") == LEGEND["ro"]
    assert "**[NOTIȚE]**" in legenda("ro", notite=True)
    assert "**[NOTES]**" in legenda("en", notite=True) and "[NOTIȚE]" not in legenda("en", notite=True)


def test_titlul_fisierului_nu_pastreaza_marcajul_notitelor():
    assert _fara_marcaje("VEDAŞ [NOTIȚE: din notițe] – Analiză [NOTES]") == "VEDAŞ – Analiză"


# ── pipeline-ul ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notitele_ajung_la_model_dupa_context_si_in_legenda(tmp_path):
    vtt = _vtt(tmp_path, "t.vtt", VTT_1)
    with patch("pipelines.minuta_pipeline._extract_metadata", return_value=META) as meta, \
         patch("pipelines.minuta_pipeline._extract_sections", return_value=SECTIONS), \
         patch("pipelines.minuta_pipeline._extract_action_items", return_value=[]), \
         patch("pipelines.minuta_pipeline._extract_profile", return_value=PROFILE):
        docx_path, html = await run_minuta_pipeline(
            vtt, "k", marcaje=True, notite="Bugetul real: 4,5 milioane (Ion Popescu).")
    context_arg, extra_arg = meta.call_args[0][2], meta.call_args[0][3]
    assert context_arg == "---NOTIȚELE ECHIPEI DIN ȘEDINȚĂ---\nBugetul real: 4,5 milioane (Ion Popescu)."
    assert "Notițele echipei din ședință" in extra_arg and "[NOTIȚE: în transcriere" in extra_arg
    assert "[NOTIȚE]" in html
    docx_path.unlink()


@pytest.mark.asyncio
async def test_fara_notite_minuta_ramane_neschimbata(tmp_path):
    vtt = _vtt(tmp_path, "t.vtt", VTT_1)
    with patch("pipelines.minuta_pipeline._extract_metadata", return_value=META) as meta, \
         patch("pipelines.minuta_pipeline._extract_sections", return_value=SECTIONS), \
         patch("pipelines.minuta_pipeline._extract_action_items", return_value=[]), \
         patch("pipelines.minuta_pipeline._extract_profile", return_value=PROFILE):
        docx_path, html = await run_minuta_pipeline(vtt, "k", marcaje=True, notite="   ")
    assert meta.call_args[0][2] == ""
    assert "Notițele echipei" not in meta.call_args[0][3] and "[NOTIȚE]" not in html
    docx_path.unlink()


@pytest.mark.asyncio
async def test_inregistrarile_aceleiasi_zile_ajung_intr_o_singura_transcriere(tmp_path):
    a, b = _vtt(tmp_path, "a.vtt", VTT_1), _vtt(tmp_path, "b.vtt", VTT_2)
    with patch("pipelines.minuta_pipeline._extract_metadata", return_value=META) as meta, \
         patch("pipelines.minuta_pipeline._extract_sections", return_value=SECTIONS), \
         patch("pipelines.minuta_pipeline._extract_action_items", return_value=[]), \
         patch("pipelines.minuta_pipeline._extract_profile", return_value=PROFILE):
        docx_path, _ = await run_minuta_pipeline(a, "k", inregistrari=[(a, "Ziua 3"), (b, "Ziua 3 (1)")])
    transcript_arg, extra_arg = meta.call_args[0][1], meta.call_args[0][3]
    assert "Înregistrarea 2 din 2" in transcript_arg and "[(2) 00:00:01] Ana Ionescu" in transcript_arg
    assert "Mai multe înregistrări din aceeași zi" in extra_arg
    docx_path.unlink()


# ── ruta ─────────────────────────────────────────────────────────────────────

async def _posteaza(client, data, descarcari):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1", "email": "t@t.com"}
    try:
        with patch("routers.minuta._run_job", new_callable=AsyncMock) as rulat, \
             patch("routers.minuta.download_upload", side_effect=descarcari), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}):
            raspuns = await client.post("/api/minuta", headers={"Authorization": "Bearer x"}, data=data)
    finally:
        app.dependency_overrides.clear()
    return raspuns, rulat


@pytest.mark.asyncio
async def test_ruta_transmite_notitele_si_inregistrarile_jobului(client, tmp_path):
    a, b = _vtt(tmp_path, "a.vtt", VTT_1), _vtt(tmp_path, "b.vtt", VTT_2)
    raspuns, rulat = await _posteaza(client, {
        "storage_path": "minuta/a.vtt", "filename": "Ziua 3.vtt",
        "notite": "  Pervin Hanım – directoare  ",
        "inregistrari": json.dumps([{"storage_path": "minuta/b.vtt", "filename": "Ziua 3 (1).vtt"}]),
    }, [a, b])
    assert raspuns.status_code == 200
    kwargs = rulat.call_args.kwargs
    assert kwargs["notite"] == "Pervin Hanım – directoare"
    assert kwargs["alte_inregistrari"] == [(b, "Ziua 3 (1)")]
    assert rulat.call_args[0][3] == "Ziua 3"  # numele minutei vine din prima înregistrare


@pytest.mark.asyncio
@pytest.mark.parametrize("inregistrari", [
    "nu e json",
    json.dumps({"storage_path": "minuta/b.vtt"}),
    json.dumps([{"filename": "fara cale.vtt"}]),
    json.dumps([{"storage_path": f"minuta/{i}.vtt", "filename": f"{i}.vtt"} for i in range(5)]),
])
async def test_ruta_respinge_lista_de_inregistrari_invalida(client, tmp_path, inregistrari):
    a = _vtt(tmp_path, "a.vtt", VTT_1)
    raspuns, rulat = await _posteaza(client, {
        "storage_path": "minuta/a.vtt", "filename": "Ziua 3.vtt", "inregistrari": inregistrari,
    }, [a] + [_vtt(tmp_path, f"x{i}.vtt", VTT_2) for i in range(5)])
    assert raspuns.status_code == 422
    rulat.assert_not_called()
    assert not a.exists()  # fișierul temporar al primei înregistrări nu rămâne pe server


@pytest.mark.asyncio
async def test_ruta_respinge_inregistrarea_cu_extensie_gresita_si_curata_ce_a_descarcat(client, tmp_path):
    a, b = _vtt(tmp_path, "a.vtt", VTT_1), _vtt(tmp_path, "b.vtt", VTT_2)
    raspuns, rulat = await _posteaza(client, {
        "storage_path": "minuta/a.vtt", "filename": "Ziua 3.vtt",
        "inregistrari": json.dumps([{"storage_path": "minuta/b.vtt", "filename": "Ziua 3 (1).vtt"},
                                    {"storage_path": "minuta/c.pdf", "filename": "c.pdf"}]),
    }, [a, b])
    assert raspuns.status_code == 422
    rulat.assert_not_called()
    assert not a.exists() and not b.exists()


@pytest.mark.asyncio
async def test_ruta_respinge_notitele_prea_lungi(client, tmp_path):
    a = _vtt(tmp_path, "a.vtt", VTT_1)
    raspuns, rulat = await _posteaza(client, {
        "storage_path": "minuta/a.vtt", "filename": "Ziua 3.vtt", "notite": "x" * 30_001,
    }, [a])
    assert raspuns.status_code == 422 and "30000" in raspuns.json()["detail"]
    rulat.assert_not_called()
