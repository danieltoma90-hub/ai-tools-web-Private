import sys
from pathlib import Path

from docx import Document

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "minuta" / "scripts"))
from transcript_prep import hms, is_hesitation, prepare_transcript, read_docx, read_vtt  # noqa: E402


def _vtt(tmp_path, body: str) -> Path:
    p = tmp_path / "t.vtt"
    p.write_text("WEBVTT\n\n" + body, encoding="utf-8")
    return p


def test_vtt_teams_unifica_replicile_si_pastreaza_ora_si_vorbitorul(tmp_path):
    p = _vtt(tmp_path,
             "444da140-7f23/5-0\n00:00:01.000 --> 00:00:03.000\n<v Ion Popescu>Bună ziua.</v>\n\n"
             "444da140-7f23/6-0\n00:00:03.500 --> 00:00:06.000\n<v Ion Popescu>Începem ședința.</v>\n\n"
             "444da140-7f23/7-0\n00:00:06.500 --> 00:00:08.000\n<v Maria Ionescu>Mulțumim.</v>\n")
    assert prepare_transcript(p).splitlines() == [
        "[00:00:01] Ion Popescu: Bună ziua. Începem ședința.",
        "[00:00:06] Maria Ionescu: Mulțumim.",
    ]


def test_vtt_fara_etichete_de_vorbitor(tmp_path):
    p = _vtt(tmp_path, "00:00:01.000 --> 00:00:03.000\nIon Popescu: Buna ziua.\n")
    assert prepare_transcript(p) == "[00:00:01] Ion Popescu: Buna ziua."


def test_ezitarile_pure_dispar_raspunsurile_scurte_raman(tmp_path):
    p = _vtt(tmp_path,
             "00:00:01.000 --> 00:00:02.000\n<v A>Ăă, hmm.</v>\n\n"
             "00:00:10.000 --> 00:00:11.000\n<v A>Da.</v>\n\n"
             "00:00:20.000 --> 00:00:21.000\n<v A>Evet.</v>\n")
    assert prepare_transcript(p).splitlines() == ["[00:00:10] A: Da.", "[00:00:20] A: Evet."]
    assert is_hesitation("ııı") and is_hesitation("Hmm...") and not is_hesitation("ok")


def test_unirea_respecta_pauza_durata_si_vorbitorul(tmp_path):
    p = _vtt(tmp_path,
             "00:00:00.000 --> 00:00:02.000\n<v A>unu</v>\n\n"
             "00:00:06.000 --> 00:00:07.000\n<v A>doi</v>\n\n"        # pauză de 4 s: bloc nou
             "00:00:07.500 --> 00:01:20.000\n<v A>trei</v>\n\n"       # ar depăși un minut: bloc nou
             "00:01:21.000 --> 00:01:22.000\n<v B>patru</v>\n")      # alt vorbitor
    assert [ln.split("] ")[1] for ln in prepare_transcript(p).splitlines()] == ["A: unu", "A: doi", "A: trei", "B: patru"]


def test_replica_repetata_de_teams_nu_se_dubleaza(tmp_path):
    p = _vtt(tmp_path,
             "00:00:01.000 --> 00:00:02.000\n<v A>trimitem oferta mâine dimineață</v>\n\n"
             "00:00:02.100 --> 00:00:03.000\n<v A>trimitem oferta mâine dimineață</v>\n\n"
             "00:00:03.100 --> 00:00:04.000\n<v A>da</v>\n\n"
             "00:00:04.100 --> 00:00:05.000\n<v A>da</v>\n")
    assert prepare_transcript(p) == "[00:00:01] A: trimitem oferta mâine dimineață da da"


def test_ora_peste_o_ora():
    assert hms(3723.9) == "01:02:03"


def _docx(tmp_path, paragraphs: list[str]) -> Path:
    d = Document()
    for t in paragraphs:
        d.add_paragraph(t)
    p = tmp_path / "t.docx"
    d.save(str(p))
    return p


def test_docx_teams_cu_randuri_in_acelasi_paragraf(tmp_path):
    p = _docx(tmp_path, [
        "Ședință-20261007-Meeting Recording", "October 7, 2026",
        "\nIon Popescu started transcription",
        "\nIon Popescu   0:04\nBună ziua.\nÎncepem.\nMaria Ionescu   1:02:03\nMulțumim.",
        "\nIon Popescu stopped transcription",
    ])
    cues = read_docx(p)
    assert [(c.speaker, c.start, c.end) for c in cues] == [("Ion Popescu", 4, 3723), ("Maria Ionescu", 3723, 3723)]
    assert prepare_transcript(p).splitlines() == [
        "[00:00:04] Ion Popescu: Bună ziua. Începem.",
        "[01:02:03] Maria Ionescu: Mulțumim.",
    ]


def test_docx_un_singur_cont_se_imparte_in_bucati(tmp_path):
    rows = [f"rândul {i}" for i in range(50)]
    p = _docx(tmp_path, ["\nSala   0:04\n" + "\n".join(rows)])
    lines = prepare_transcript(p).splitlines()
    assert len(lines) == 5  # 50 de rânduri în bucăți de 12, fără reunire
    assert all(ln.startswith("[00:00:04] Sala: ") for ln in lines)


def test_docx_fara_format_teams_ramane_textul(tmp_path):
    p = _docx(tmp_path, ["Ion Popescu: Buna ziua tuturor.", "Maria Ionescu: Incepem sedinta."])
    assert read_docx(p) == []
    assert prepare_transcript(p) == "Ion Popescu: Buna ziua tuturor.\nMaria Ionescu: Incepem sedinta."
