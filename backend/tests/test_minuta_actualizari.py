"""Metoda din minutele VEDAŞ, adusă pe site: transcriere pregătită, reguli de redactare, marcaje,
minuta în engleză, structura Fit-Gap și detaliul complet."""
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "minuta" / "scripts"))
from fitgap import fitgap_sections  # noqa: E402
from limba import LEGEND, docx_to_en  # noqa: E402
from reguli import build_rules, with_legend  # noqa: E402

from auth import verify_token  # noqa: E402
from main import app  # noqa: E402
from pipelines import minuta_free_pipeline as free  # noqa: E402
from pipelines.minuta_pipeline import _call_claude, run_minuta_pipeline  # noqa: E402
from routers.minuta import _nume_fisier, _optiuni  # noqa: E402

VTT = "WEBVTT\n\nid-1\n00:00:01.000 --> 00:00:04.000\n<v Ion Popescu>Bugetul este de 5 milioane.</v>\n"
META = {"subiect": "Demo Charisma", "nume_client": "Client Test", "data": "15.10.2026",
        "participanti": {"TotalSoft": ["Ion Popescu"]}}
FITGAP = {
    "title_lines": ["Client Test / Demo – Rezumatul ședinței"],
    "objective": "Demonstrarea soluției.",
    "executive_summary": ["Ședința s-a concentrat pe demo."],
    "topics": [{"title": "1. Estimare", "blocks": [{"p": "S-a arătat devizul."}, {"ul": ["import din Excel"]}]}],
    "pain_points": [{"title": "Situații de lucrări", "blocks": [{"ul": ["semnătură digitală"]}]}],
    "solution": {"intro": "Mai multe componente.", "groups": [{"title": "ERP", "items": ["achiziții"]}]},
    "actions": {"customer": [{"title": "Trimite formatul", "items": ["Excel"], "responsible": "VEDAŞ"}],
                "team": [{"title": "Trimite capturi", "items": ["portal"]}]},
    "risks": [["Risc [DEDUCȚIE: evaluarea redactorului]", "Impact"], ["Integrare YTS", "Ridicat"]],
    "conclusion": ["Charisma acoperă fluxul. [DEDUCȚIE]"],
    "recommendation": "Workshop Fit-Gap. [DEDUCȚIE]",
}


# ── opțiuni și nume de fișier ────────────────────────────────────────────────

def test_optiunile_implicite_cer_marcaje_in_romana():
    assert _optiuni("1", "ro") == {"marcaje": True, "limba": "ro", "structura": "standard", "detaliu": "standard"}
    assert _optiuni("0", "EN", "fitgap", "complet")["marcaje"] is False


@pytest.mark.parametrize("args", [("1", "de"), ("1", "ro", "letter"), ("1", "ro", "standard", "scurt")])
def test_optiunile_invalide_dau_422(args):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        _optiuni(*args)
    assert e.value.status_code == 422


def test_numele_fisierului_arata_limba_si_structura():
    assert _nume_fisier("Sedinta", "20261016_1200", None) == "Minuta_Sedinta_20261016_1200.docx"
    assert _nume_fisier("Sedinta", "T", {"limba": "en", "structura": "fitgap"}) == "Minutes_Sedinta_FitGap_T.docx"


@pytest.mark.asyncio
async def test_ruta_transmite_optiunile_jobului(client, tmp_path):
    transcript = tmp_path / "abc.vtt"
    transcript.write_text(VTT, encoding="utf-8")
    app.dependency_overrides[verify_token] = lambda: {"id": "u1", "email": "t@t.com"}
    try:
        with patch("routers.minuta._run_job", new_callable=AsyncMock) as rulat, \
             patch("routers.minuta.download_upload", return_value=transcript), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}):
            ok = await client.post("/api/minuta", headers={"Authorization": "Bearer x"}, data={
                "storage_path": "minuta/abc.vtt", "filename": "S.vtt",
                "limba": "en", "structura": "fitgap", "detaliu": "complet", "marcaje": "1"})
            gresit = await client.post("/api/minuta", headers={"Authorization": "Bearer x"}, data={
                "storage_path": "minuta/abc.vtt", "filename": "S.vtt", "structura": "letter"})
    finally:
        app.dependency_overrides.clear()
    assert ok.status_code == 200
    assert rulat.call_args[0][6] == {"marcaje": True, "limba": "en", "structura": "fitgap", "detaliu": "complet"}
    assert gresit.status_code == 422


# ── reguli și legendă ────────────────────────────────────────────────────────

def test_regulile_urmeaza_optiunile():
    baza = build_rules()
    assert "Nimic peste surse" in baza and "[DEDUCȚIE" not in baza and "engleză" not in baza
    toate = build_rules(marcaje=True, limba="en", detaliu="complet")
    assert "[DEDUCȚIE: …]" in toate and "[INFERENCE: …]" in toate and "Nivel de detaliu: complet" in toate


def test_legenda_se_adauga_la_lista_existenta_sau_ca_paragraf():
    lista = with_legend([{"type": "bullets", "items": ["Scopul ședinței."]}], "LEGENDA")
    assert lista == [{"type": "bullets", "items": ["Scopul ședinței.", "LEGENDA"]}]
    assert with_legend(None, "LEGENDA") == [{"type": "paragraph", "text": "LEGENDA"}]


@pytest.mark.asyncio
async def test_apelul_claude_pune_regulile_dupa_prompt_si_cere_tokenii_dati():
    client = AsyncMock()
    client.messages.create.return_value.content = [type("B", (), {"text": "{}"})()]
    await _call_claude(client, "extract_sections.md", "[00:00:01] A: text", "CONTEXT", "REGULI", 16000)
    kwargs = client.messages.create.call_args.kwargs
    content = kwargs["messages"][0]["content"]
    assert kwargs["max_tokens"] == 16000
    assert content.index("REGULI") < content.index("CONTEXT") < content.index("---TRANSCRIPT---")


# ── Fit-Gap ──────────────────────────────────────────────────────────────────

def test_fitgap_da_capitolele_exemplului_cu_legenda_la_finalul_rezumatului():
    sec = fitgap_sections(FITGAP, "ro", LEGEND["ro"])
    assert [s["titlu"] for s in sec] == [
        "Rezumat executiv", "Subiecte cheie discutate", "Probleme identificate", "Direcții de soluție propuse",
        "Acțiuni de urmărire", "Evaluarea riscurilor de implementare", "Concluzie finală"]
    rezumat = sec[0]["blocuri"]
    assert rezumat[0]["text"].startswith("**Obiectiv:**") and rezumat[-1]["text"] == LEGEND["ro"]
    assert sec[1]["blocuri"][0] == {"type": "subheading", "text": "Estimare"}  # fără numărul pus de model
    assert sec[2]["blocuri"][0]["text"] == "Problema critică 1 – Situații de lucrări"
    assert sec[5]["blocuri"][0]["rows"] == [["Integrare YTS", "Ridicat"]]
    assert sec[6]["blocuri"][-1]["text"].startswith("**Recomandare pentru ofertă:**")


def test_fitgap_in_engleza_si_fara_continut():
    assert fitgap_sections(FITGAP, "en")[0]["titlu"] == "Executive Summary"
    with pytest.raises(ValueError):
        fitgap_sections({"topics": [], "executive_summary": []}, "ro")


# ── minuta în engleză ────────────────────────────────────────────────────────

def _xml(docx_path: Path) -> str:
    with zipfile.ZipFile(docx_path) as z:
        return "".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xml"))


@pytest.mark.asyncio
async def test_minuta_in_engleza_cu_marcaje(tmp_path):
    vtt = tmp_path / "t.vtt"
    vtt.write_text(VTT, encoding="utf-8")
    sections = {"context_si_scop": [{"type": "bullets", "items": ["Purpose of the meeting."]}],
                "sectiuni": [{"titlu": "Budget", "blocuri": [{"type": "paragraph", "text": "5 million."}]}]}
    profile = {"profil_beneficiar": [{"aspect": "Sector", "detaliu": "Energy"}], "cerinte_beneficiar": [],
               "puncte_deschise": []}
    with patch("pipelines.minuta_pipeline._extract_metadata", return_value=META) as meta, \
         patch("pipelines.minuta_pipeline._extract_sections", return_value=sections), \
         patch("pipelines.minuta_pipeline._extract_action_items", return_value=[]), \
         patch("pipelines.minuta_pipeline._extract_profile", return_value=profile):
        docx_path, html = await run_minuta_pipeline(vtt, "k", marcaje=True, limba="en")
    # modelul primește transcrierea pregătită (cu ora) și regulile în engleză
    transcript_arg, extra_arg = meta.call_args[0][1], meta.call_args[0][3]
    assert transcript_arg == "[00:00:01] Ion Popescu: Bugetul este de 5 milioane."
    assert "[INFERENCE: …]" in extra_arg
    assert "MEETING MINUTES" in html and "Client Profile" in html and "Marker legend" in html
    xml = _xml(docx_path)
    assert "MEETING MINUTES" in xml and "Context and Purpose" in xml and "Client Name" in xml
    assert "MINUTA INTALNIRII" not in xml and "Minuta Intalnirii" not in xml
    docx_path.unlink()


@pytest.mark.asyncio
async def test_minuta_fitgap_pe_formatul_f05(tmp_path):
    vtt = tmp_path / "t.vtt"
    vtt.write_text(VTT, encoding="utf-8")
    with patch("pipelines.minuta_pipeline._extract_metadata", return_value=META), \
         patch("pipelines.minuta_pipeline._extract_fitgap", return_value=FITGAP) as fg, \
         patch("pipelines.minuta_pipeline._extract_sections") as sectiuni:
        docx_path, html = await run_minuta_pipeline(vtt, "k", marcaje=True, structura="fitgap")
    sectiuni.assert_not_called()
    assert fg.call_count == 1
    assert "Rezumat executiv" in html and "Legenda marcajelor" in html and "Pași următori" not in html
    xml = _xml(docx_path)
    assert "MINUTA INTALNIRII" in xml and "Evaluarea riscurilor de implementare" in xml
    docx_path.unlink()


def test_conversia_in_engleza_nu_lasa_etichete_romanesti(tmp_path):
    from build_minuta import build_minuta
    data = {"meta": META, "context_si_scop": [{"type": "paragraph", "text": "x"}], "sectiuni": [],
            "pasi_urmatori": [{"responsabil": "TotalSoft", "actiune": "Sends the offer."}]}
    src = tmp_path / "m.json"
    src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "m.docx"
    build_minuta(src, out, template_path=Path(__file__).parent.parent / "skills" / "minuta" / "template" / "F05_minuta_template.docx")
    docx_to_en(out)
    xml = _xml(out)
    for ro in ("Cod Proiect", "Participanti", "Pași următori", "Context și scop", "Pag.", 'w:val="ro-RO"'):
        assert ro not in xml, ro
    assert "Next Steps" in xml and "Meeting Minutes | Client Test" in xml


# ── varianta Free ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_free_pune_regulile_doar_la_metadata_si_sinteza(tmp_path, monkeypatch):
    vtt = tmp_path / "t.vtt"
    vtt.write_text(VTT, encoding="utf-8")
    monkeypatch.setattr(free, "CALL_DELAY_S", 0)
    raspunsuri = {
        "extract_meeting_metadata.md": json.dumps({"meta": META}),
        "map_chunk_notes.md": json.dumps({"subiecte": ["buget"]}),
        "reduce_synthesis.md": json.dumps({"context_si_scop": None, "sectiuni": [], "pasi_urmatori": []}),
    }
    apeluri = []

    async def fals(client, prompt_file, content, state, out_tokens, extra=""):
        apeluri.append((prompt_file, content, extra))
        return raspunsuri[prompt_file]

    with patch.object(free, "_call_groq", side_effect=fals):
        docx_path, html = await free.run_minuta_free_pipeline(vtt, "k", marcaje=True, limba="ro")
    extra = {f: e for f, _, e in apeluri}
    assert "Nimic peste surse" in extra["extract_meeting_metadata.md"]
    assert extra["map_chunk_notes.md"] == ""
    assert "[DEDUCȚIE: …]" in extra["reduce_synthesis.md"]
    assert "[00:00:01] Ion Popescu" in apeluri[1][1]
    assert "Legenda marcajelor" in html
    docx_path.unlink()
