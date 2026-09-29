# -*- coding: utf-8 -*-
"""Teste pentru pipeline-ul scop_core (Task 4 — orchestrare capitol + inserare).

`GAZDA` e același fixture folosit de `test_scop_core_capitol.py` — un document
gazdă real, anonimizat, cu styles.xml/numbering.xml reale. Testul central de
siguranță (`test_gazda_ramane_neschimbata_dupa_inserare`) verifică prin hash
că fișierul de pe disc nu e niciodată atins, indiferent de calea de execuție —
vezi non-negociabilul din brief.
"""
from __future__ import annotations

import copy
import hashlib
import pathlib

import pytest
from docx import Document

from pipelines import scop_core_pipeline as pipeline
from skills.scop_core import extractie, scope
from skills.scop_core.charisma_core import SECTIUNI

GAZDA = pathlib.Path(__file__).resolve().parent / "fixtures" / "gazda_reala_anonimizata.docx"


def _hash(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _texte(path: pathlib.Path) -> list[str]:
    return [p.text for p in Document(str(path)).paragraphs]


def _h2(path: pathlib.Path) -> list[str]:
    return [p.text for p in Document(str(path)).paragraphs if p.style is not None and p.style.name == "Heading 2"]


def _gazda_cu_antet_subsol(tmp_path, antet_text: str = "", subsol_text: str = "") -> pathlib.Path:
    """`GAZDA` cu antetul/subsolul (goale în fixture) populate cu text real —
    simulează gazda reală (Turkish Doner Steakhouse), care numește clientul
    în subsol, ca să poată fi verificate detectarea mismatch-ului și
    `curata_antet_subsol` la nivel de pipeline."""
    doc = Document(str(GAZDA))
    s = doc.sections[0]
    if antet_text:
        s.header.paragraphs[0].add_run(antet_text)
    if subsol_text:
        s.footer.paragraphs[0].add_run(subsol_text)
    cale = tmp_path / "gazda_cu_antet_subsol.docx"
    doc.save(str(cale))
    return cale


@pytest.fixture
def spion_mktemp(monkeypatch):
    """Înlocuiește `_mktemp_path` cu o variantă care reține fiecare cale creată,
    ca testele de eșec să poată verifica direct — nu doar presupune — că
    niciun fișier temporar nu rămâne pe disc după o excepție."""
    create: list[pathlib.Path] = []
    original = pipeline._mktemp_path

    def spion(suffix):
        p = original(suffix)
        create.append(p)
        return p

    monkeypatch.setattr(pipeline, "_mktemp_path", spion)
    return create


# --- capitolul se produce -----------------------------------------------

async def test_pipelineul_produce_capitolul_cu_numele_clientului():
    capitol_path, gazda_out, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME SRL", elemente=[], insereaza_in_gazda=False,
    )
    try:
        assert capitol_path.is_file()
        text = "\n".join(_texte(capitol_path))
        assert "Charisma ERP CORE" in text
        assert "ACME SRL" in text
        assert gazda_out is None
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_client_gol_foloseste_placeholder_implicit():
    capitol_path, _, _ = await pipeline.run_scop_core_pipeline(
        GAZDA, client="", elemente=[], insereaza_in_gazda=False,
    )
    try:
        text = "\n".join(_texte(capitol_path))
        assert pipeline.CLIENT_IMPLICIT in text
    finally:
        capitol_path.unlink(missing_ok=True)


# --- a doua cale (gazdă cu capitol inserat) ------------------------------

async def test_insereaza_in_gazda_true_produce_a_doua_cale():
    capitol_path, gazda_out, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=True,
    )
    try:
        assert gazda_out is not None
        assert gazda_out.is_file()
        assert gazda_out != capitol_path
        assert sumar["gazda_inserata"] is True
    finally:
        capitol_path.unlink(missing_ok=True)
        if gazda_out is not None:
            gazda_out.unlink(missing_ok=True)


async def test_insereaza_in_gazda_false_intoarce_none():
    capitol_path, gazda_out, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=False,
    )
    try:
        assert gazda_out is None
        assert sumar["gazda_inserata"] is False
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_gazda_ramane_neschimbata_dupa_inserare():
    """Non-negociabilul din brief: fișierul gazdă de pe disc nu se modifică
    niciodată — hash identic înainte/după, chiar cu insereaza_in_gazda=True."""
    hash_inainte = _hash(GAZDA)
    capitol_path, gazda_out, _ = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=True,
    )
    try:
        assert _hash(GAZDA) == hash_inainte
    finally:
        capitol_path.unlink(missing_ok=True)
        if gazda_out is not None:
            gazda_out.unlink(missing_ok=True)


# --- elemente malformate din browser --------------------------------------

async def test_element_fara_titlu_e_respins_dar_nu_pica_pipeline_ul():
    elemente = [
        {"titlu": "", "text": "Text valid.", "plasare": "vanzari", "fluxuri_legate": []},
        {"titlu": "Titlu bun", "text": "Text bun.", "plasare": "vanzari", "fluxuri_legate": []},
    ]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=elemente, insereaza_in_gazda=False,
    )
    try:
        assert sumar["elemente_respinse"] == 1
        assert sumar["elemente_plasate"] == 1
        assert "Titlu bun" in "\n".join(_texte(capitol_path))
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_element_fara_text_e_respins():
    elemente = [{"titlu": "Titlu fără corp", "text": "   ", "plasare": "propriu", "fluxuri_legate": []}]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=elemente, insereaza_in_gazda=False,
    )
    try:
        assert sumar["elemente_respinse"] == 1
        assert sumar["elemente_plasate"] == 0
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_element_care_nu_e_dict_e_ignorat():
    elemente = ["nu sunt un dict", 42, {"titlu": "T", "text": "X", "plasare": "propriu"}]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=elemente, insereaza_in_gazda=False,
    )
    try:
        assert sumar["elemente_respinse"] == 2
        assert sumar["elemente_plasate"] == 1
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_plasare_invalida_devine_propriu_si_nu_pica():
    elemente = [{"titlu": "Element rătăcit", "text": "Y", "plasare": "sectiune-care-nu-exista",
                 "fluxuri_legate": []}]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=elemente, insereaza_in_gazda=False,
    )
    try:
        assert sumar["elemente_proprii"] == 1
        assert sumar["elemente_pe_sectiune"] == 0
        assert _h2(capitol_path)[-1].endswith("Element rătăcit")
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_plasare_lipsa_devine_propriu():
    elemente = [{"titlu": "X", "text": "Y", "fluxuri_legate": []}]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=elemente, insereaza_in_gazda=False,
    )
    try:
        assert sumar["elemente_proprii"] == 1
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_elemente_care_nu_e_lista_nu_pica_pipeline_ul():
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=None, insereaza_in_gazda=False,  # type: ignore[arg-type]
    )
    try:
        assert sumar["elemente_plasate"] == 0
        assert sumar["elemente_respinse"] == 0
        assert sumar["elemente_primite"] == 0
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_fluxuri_legate_care_nu_e_lista_devine_lista_goala():
    elemente = [{"titlu": "X", "text": "Y", "plasare": "vanzari", "fluxuri_legate": "V2"}]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=elemente, insereaza_in_gazda=False,
    )
    try:
        assert sumar["elemente_plasate"] == 1
        assert "corelat" not in "\n".join(_texte(capitol_path)).lower()
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_cod_de_flux_valid_produce_fraza_de_corelare():
    elemente = [{"titlu": "X", "text": "Y", "plasare": "vanzari", "fluxuri_legate": [" V2 "]}]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=elemente, insereaza_in_gazda=False,
    )
    try:
        v2 = next(f for s in SECTIUNI if s.cheie == "vanzari" for f in s.fluxuri if f.cod == "V2")
        assert v2.flux in "\n".join(_texte(capitol_path))
    finally:
        capitol_path.unlink(missing_ok=True)


# --- sumarul ---------------------------------------------------------------

async def test_sumarul_are_numerele_corecte():
    elemente = [
        {"titlu": "Sub A", "text": "Text A.", "plasare": "vanzari", "fluxuri_legate": []},
        {"titlu": "Sub B", "text": "Text B.", "plasare": "propriu", "fluxuri_legate": []},
    ]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=elemente, insereaza_in_gazda=False,
    )
    try:
        assert sumar["sectiuni"] == len(SECTIUNI) == 10
        assert sumar["fluxuri"] == sum(len(s.fluxuri) for s in SECTIUNI) == 47
        assert sumar["elemente_primite"] == 2
        assert sumar["elemente_plasate"] == 2
        assert sumar["elemente_pe_sectiune"] == 1
        assert sumar["elemente_proprii"] == 1
        assert sumar["elemente_respinse"] == 0
    finally:
        capitol_path.unlink(missing_ok=True)


# --- on_step ----------------------------------------------------------------

async def test_on_step_semnaleaza_parsing_si_building_fara_inserare():
    pasi: list[str] = []
    capitol_path, _, _ = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=False, on_step=pasi.append,
    )
    try:
        assert pasi[0] == "parsing"
        assert "building" in pasi
        assert "inserare" not in pasi
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_on_step_semnaleaza_si_inserarea_cand_e_ceruta():
    pasi: list[str] = []
    capitol_path, gazda_out, _ = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=True, on_step=pasi.append,
    )
    try:
        assert "inserare" in pasi
        assert pasi.index("building") < pasi.index("inserare")
    finally:
        capitol_path.unlink(missing_ok=True)
        if gazda_out is not None:
            gazda_out.unlink(missing_ok=True)


# --- avertisment -------------------------------------------------------------

async def test_avertisment_gol_fara_elemente_si_fara_insereaza():
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=False,
    )
    try:
        assert sumar["avertisment"] == ""
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_elementele_suplimentare_ajung_si_in_gazda_cu_capitol():
    """Limitarea din raportul Task 4 a fost rezolvată: `insereaza.insereaza_capitol`
    primește acum `elemente` — cele două fișiere întoarse de pipeline conțin
    identic aceleași elemente suplimentare, nu doar capitolul standalone.
    Fără avertisment: nu mai există nimic de semnalat pe această cale."""
    elemente = [{"titlu": "Element unic pentru test", "text": "Y", "plasare": "propriu",
                 "fluxuri_legate": []}]
    capitol_path, gazda_out, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=elemente, insereaza_in_gazda=True,
    )
    try:
        assert sumar["avertisment"] == ""
        assert gazda_out is not None
        assert "Element unic pentru test" in "\n".join(_texte(gazda_out))
        assert "5.11. Element unic pentru test" in _h2(gazda_out)
    finally:
        capitol_path.unlink(missing_ok=True)
        if gazda_out is not None:
            gazda_out.unlink(missing_ok=True)


async def test_fara_elemente_insereaza_in_gazda_nu_are_avertisment():
    capitol_path, gazda_out, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=True,
    )
    try:
        assert sumar["avertisment"] == ""
    finally:
        capitol_path.unlink(missing_ok=True)
        if gazda_out is not None:
            gazda_out.unlink(missing_ok=True)


# --- eșecuri și curățare de fișiere temporare -------------------------------

async def test_gazda_inexistenta_ridica_eroare_fara_fisier_temporar_ramas(tmp_path, spion_mktemp):
    gazda_inexistenta = tmp_path / "nu_exista.docx"
    with pytest.raises(FileNotFoundError):
        await pipeline.run_scop_core_pipeline(
            gazda_inexistenta, client="ACME", elemente=[], insereaza_in_gazda=False,
        )
    assert spion_mktemp, "cel puțin un fișier temporar trebuia creat înainte de eroare"
    assert not any(p.exists() for p in spion_mktemp), "niciun fișier temporar nu trebuie să rămână pe disc"


async def test_esecul_la_inserare_pastreaza_capitolul_si_avertizeaza(monkeypatch, spion_mktemp):
    """Un eșec la pasul opțional de inserare nu trebuie să tragă după el
    capitolul deja construit cu succes — vezi docstring-ul funcției."""
    def insereaza_stricata(cale_gazda, sectiuni, numar=5, nivel=1, client="[NUME CLIENT]",
                           elemente=None):
        raise RuntimeError("gazdă simulat coruptă")

    monkeypatch.setattr(pipeline.insereaza, "insereaza_capitol", insereaza_stricata)

    capitol_path, gazda_out, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=True,
    )
    try:
        assert capitol_path.is_file()
        assert gazda_out is None
        assert sumar["gazda_inserata"] is False
        assert "eșuat" in sumar["avertisment"]
        # candidatul creat pentru a doua cale nu trebuie să rămână orfan pe disc
        candidati_ramasi = [p for p in spion_mktemp if p != capitol_path and p.exists()]
        assert candidati_ramasi == []
    finally:
        capitol_path.unlink(missing_ok=True)


# --- „Delimitări de scop” (feature nou) -------------------------------------

async def test_delimitarile_valide_ajung_in_capitol():
    delimitari = [
        {"element": "Migrarea istoricului", "precizare": "Nu face obiectul acestui scop."},
        {"element": "Cântare suplimentare", "precizare": "Se estimează separat."},
    ]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=False, delimitari=delimitari,
    )
    try:
        assert sumar["delimitari_primite"] == 2
        assert sumar["delimitari_plasate"] == 2
        assert sumar["delimitari_respinse"] == 0
        texte = "\n".join(_texte(capitol_path))
        assert "Delimitări de scop" in texte
        tabel = Document(str(capitol_path)).tables[-1]
        celule = [c.text for r in tabel.rows for c in r.cells]
        assert "Migrarea istoricului" in celule
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_delimitare_fara_element_e_respinsa():
    delimitari = [{"element": "", "precizare": "Text valid."}]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=False, delimitari=delimitari,
    )
    try:
        assert sumar["delimitari_respinse"] == 1
        assert sumar["delimitari_plasate"] == 0
        assert "Delimitări de scop" not in "\n".join(_texte(capitol_path))
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_delimitare_fara_precizare_e_respinsa():
    delimitari = [{"element": "Element valid", "precizare": "   "}]
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=False, delimitari=delimitari,
    )
    try:
        assert sumar["delimitari_respinse"] == 1
        assert sumar["delimitari_plasate"] == 0
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_delimitari_care_nu_e_lista_nu_pica_pipelineul():
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=False, delimitari=None,
    )
    try:
        assert sumar["delimitari_primite"] == 0
        assert sumar["delimitari_plasate"] == 0
        assert sumar["delimitari_respinse"] == 0
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_fara_delimitari_avertisment_gol():
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=False,
    )
    try:
        assert sumar["avertisment"] == ""
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_delimitarile_ajung_si_in_gazda_cu_capitol_inserat():
    delimitari = [{"element": "Migrarea istoricului", "precizare": "Nu face obiectul acestui scop."}]
    capitol_path, gazda_out, sumar = await pipeline.run_scop_core_pipeline(
        GAZDA, client="ACME", elemente=[], insereaza_in_gazda=True, delimitari=delimitari,
    )
    try:
        assert gazda_out is not None
        assert "Delimitări de scop" in "\n".join(_texte(gazda_out))
        assert sumar["avertisment"] == ""
    finally:
        capitol_path.unlink(missing_ok=True)
        if gazda_out is not None:
            gazda_out.unlink(missing_ok=True)


# --- antet/subsol: mismatch de client și curata_antet_subsol ---------------

async def test_antet_subsol_avertisment_cand_clientul_nu_apare(tmp_path):
    gazda = _gazda_cu_antet_subsol(tmp_path, subsol_text="Vechi Client SRL | Charisma ERP | v1.0")
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        gazda, client="Alt Client SRL", elemente=[], insereaza_in_gazda=False,
    )
    try:
        assert sumar["antet_subsol_avertisment"] != ""
        assert "Alt Client SRL" in sumar["antet_subsol_avertisment"]
        assert "Vechi Client SRL" in sumar["antet_subsol_avertisment"]
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_antet_subsol_fara_avertisment_cand_clientul_apare(tmp_path):
    gazda = _gazda_cu_antet_subsol(tmp_path, subsol_text="ACME SRL | Charisma ERP | v1.0")
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        gazda, client="ACME SRL", elemente=[], insereaza_in_gazda=False,
    )
    try:
        assert sumar["antet_subsol_avertisment"] == ""
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_antet_subsol_fara_avertisment_cand_clientul_e_gol(tmp_path):
    """Client necompletat (placeholder implicit) — comparat, ar da mereu
    mismatch fals; nu se compară deloc în acest caz."""
    gazda = _gazda_cu_antet_subsol(tmp_path, subsol_text="Vechi Client SRL | Charisma ERP | v1.0")
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        gazda, client="", elemente=[], insereaza_in_gazda=False,
    )
    try:
        assert sumar["antet_subsol_avertisment"] == ""
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_antet_subsol_fara_avertisment_cand_curata_e_cerut(tmp_path):
    gazda = _gazda_cu_antet_subsol(tmp_path, subsol_text="Vechi Client SRL | Charisma ERP | v1.0")
    capitol_path, _, sumar = await pipeline.run_scop_core_pipeline(
        gazda, client="Alt Client SRL", elemente=[], insereaza_in_gazda=False,
        curata_antet_subsol=True,
    )
    try:
        assert sumar["antet_subsol_avertisment"] == ""
        assert sumar["antet_subsol_curatat"] is True
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_curata_antet_subsol_goleste_capitolul_generat(tmp_path):
    from docx import Document as _Document

    gazda = _gazda_cu_antet_subsol(tmp_path, subsol_text="Vechi Client SRL | Charisma ERP | v1.0")
    capitol_path, _, _ = await pipeline.run_scop_core_pipeline(
        gazda, client="Alt Client SRL", elemente=[], insereaza_in_gazda=False,
        curata_antet_subsol=True,
    )
    try:
        rezultat = _Document(str(capitol_path))
        subsol = rezultat.sections[0].footer.paragraphs[0].text
        assert "Vechi Client SRL" not in subsol
    finally:
        capitol_path.unlink(missing_ok=True)


async def test_curata_antet_subsol_goleste_si_gazda_cu_capitol_inserat(tmp_path):
    from docx import Document as _Document

    gazda = _gazda_cu_antet_subsol(tmp_path, subsol_text="Vechi Client SRL | Charisma ERP | v1.0")
    capitol_path, gazda_out, _ = await pipeline.run_scop_core_pipeline(
        gazda, client="Alt Client SRL", elemente=[], insereaza_in_gazda=True,
        curata_antet_subsol=True,
    )
    try:
        assert gazda_out is not None
        rezultat = _Document(str(gazda_out))
        subsol = rezultat.sections[0].footer.paragraphs[0].text
        assert "Vechi Client SRL" not in subsol
    finally:
        capitol_path.unlink(missing_ok=True)
        if gazda_out is not None:
            gazda_out.unlink(missing_ok=True)


# --- propune_job -------------------------------------------------------------

async def test_propune_job_e_wrapper_subtire_peste_extractie(monkeypatch, tmp_path):
    primit: dict = {}

    async def fals(path):
        primit["path"] = path
        return [{"titlu": "X", "text": "Y", "plasare": "propriu", "fluxuri_legate": []}]

    monkeypatch.setattr(pipeline.extractie, "propune_elemente", fals)

    supliment = tmp_path / "supliment.docx"
    supliment.touch()
    rezultat = await pipeline.propune_job(supliment)

    assert primit["path"] == supliment
    assert rezultat == [{"titlu": "X", "text": "Y", "plasare": "propriu", "fluxuri_legate": []}]


async def test_propune_job_propaga_erorile_lui_extractie(monkeypatch, tmp_path):
    async def fals(path):
        raise ValueError("Răspunsul modelului nu este JSON valid")

    monkeypatch.setattr(pipeline.extractie, "propune_elemente", fals)

    supliment = tmp_path / "supliment.docx"
    supliment.touch()
    with pytest.raises(ValueError, match="JSON valid"):
        await pipeline.propune_job(supliment)


# =============================================================================
# `run_scope_document_pipeline` — documentul complet de scop, 11 capitole
# (Task 3 din planul scop-core-web). `GAZDA` de mai sus servește și aici,
# doar ca sursă de stiluri/numbering — conținutul ei nu contează pentru
# `scope.genereaza`, care își golește oricum corpul documentului.
# =============================================================================

CFG_MINIM: dict = {
    "client": {},
    "document": {"titlu": "Descrierea soluției ofertate",
                "subtitlu": "Implementare Charisma ERP CORE"},
    "document_frate": {"exista": False, "titlu": "", "arie_acoperita": "", "coduri": []},
    "sectiuni_core": {"toate": True, "doar": [], "fara": []},
    "capitole": {"context": True, "abordare": True, "beneficii": True, "acoperire": True,
                "delimitare": True, "premise": True, "confirmari": True, "sinteza": True,
                "validare": True},
    "stil": {"antet": "Antet de test"},
}


def _h1(path: pathlib.Path) -> list[str]:
    return [p.text.strip() for p in Document(str(path)).paragraphs
            if p.style is not None and p.style.name == "Heading 1" and p.text.strip()]


def _tot_textul(path: pathlib.Path) -> str:
    """Paragrafe ȘI celule de tabel — spre deosebire de `_texte` de mai sus
    (doar paragrafe), necesar aici pentru că situația actuală, delimitarea și
    confirmările se randează ca tabele, nu ca paragrafe simple."""
    doc = Document(str(path))
    bucati = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for r in t.rows:
            bucati.extend(c.text for c in r.cells)
    return "\n".join(bucati)


# --- documentul de bază — cu/fără gazdă, cu/fără documentul-frate -----------

async def test_document_minim_produce_documentul_cu_capitolele_implicite():
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, {})
    try:
        titluri = _h1(doc_path)
        # fără document_frate.exista, capitolul de delimitare nu se scrie
        assert len(titluri) == 10
        assert sumar["capitole_scrise"] == 10
        assert sumar["capitole"] == titluri
        assert sumar["module_core"] == len(SECTIUNI) == 10
    finally:
        doc_path.unlink(missing_ok=True)


async def test_document_frate_exista_adauga_capitolul_de_delimitare():
    cfg = copy.deepcopy(CFG_MINIM)
    cfg["document_frate"] = {"exista": True, "titlu": "Scop Producție",
                             "arie_acoperita": "Producția", "coduri": ["N1"]}
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, cfg, {})
    try:
        assert sumar["capitole_scrise"] == 11
        assert any("Delimitarea" in t for t in sumar["capitole"])
    finally:
        doc_path.unlink(missing_ok=True)


async def test_fara_gazda_degradeaza_la_document_nou():
    """`gazda_path=None` — non-negociabilul din brief: `scope.genereaza`
    degradează la un document nou, cu stilurile implicite, nu ridică eroare."""
    doc_path, sumar = await pipeline.run_scope_document_pipeline(None, CFG_MINIM, {})
    try:
        assert doc_path.is_file()
        assert sumar["capitole_scrise"] == 10
    finally:
        doc_path.unlink(missing_ok=True)


async def test_gazda_ramane_neschimbata_documentul_complet():
    """Non-negociabilul din brief, ca la modul „capitol": documentul-gazdă de
    pe disc nu se modifică niciodată — hash identic înainte/după."""
    hash_inainte = _hash(GAZDA)
    doc_path, _ = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, {})
    try:
        assert _hash(GAZDA) == hash_inainte
    finally:
        doc_path.unlink(missing_ok=True)


# --- clientul -----------------------------------------------------------

async def test_client_complet_ajunge_in_document():
    continut = {"client": {"nume": "ACME SRL", "domeniu": "distribuție"}}
    doc_path, _ = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        assert "ACME SRL" in "\n".join(_texte(doc_path))
    finally:
        doc_path.unlink(missing_ok=True)


async def test_client_lipsa_foloseste_placeholder_din_scope():
    doc_path, _ = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, {})
    try:
        assert scope.PLACEHOLDER in "\n".join(_texte(doc_path))
    finally:
        doc_path.unlink(missing_ok=True)


async def test_client_situatie_actuala_si_obiective_ajung_in_document():
    continut = {"client": {
        "nume": "ACME SRL",
        "situatie_actuala": [{"actual": "Problema X", "solutie": "Soluția Y"},
                             {"actual": "", "solutie": "Rând incomplet — se ignoră"}],
        "obiective": ["Obiectiv unu.", "  ", "Obiectiv doi."],
    }}
    doc_path, _ = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        text = _tot_textul(doc_path)
        assert "Problema X" in text and "Soluția Y" in text
        assert "Rând incomplet" not in text
        assert "Obiectiv unu." in text and "Obiectiv doi." in text
    finally:
        doc_path.unlink(missing_ok=True)


# --- forme malformate din browser — nu ridică excepții necontrolate --------

async def test_continut_care_nu_e_dict_nu_pica_pipelineul():
    doc_path, _ = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, None)  # type: ignore[arg-type]
    try:
        assert doc_path.is_file()
    finally:
        doc_path.unlink(missing_ok=True)


async def test_client_care_nu_e_dict_nu_pica():
    doc_path, _ = await pipeline.run_scope_document_pipeline(
        GAZDA, CFG_MINIM, {"client": "nu sunt un dict"})
    try:
        assert doc_path.is_file()
    finally:
        doc_path.unlink(missing_ok=True)


async def test_suplimentar_fara_titlu_e_respins_dar_nu_pica():
    continut = {"suplimentare": [
        {"titlu": "", "intro": "Text fără titlu."},
        {"titlu": "Element bun", "intro": "Text bun."},
    ]}
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        assert sumar["elemente_suplimentare_respinse"] == 1
        assert sumar["elemente_suplimentare_plasate"] == 1
        assert "Element bun" in "\n".join(_texte(doc_path))
    finally:
        doc_path.unlink(missing_ok=True)


async def test_suplimentar_care_nu_e_dict_e_ignorat():
    continut = {"suplimentare": ["nu sunt un dict", 42, {"titlu": "Titlu valid"}]}
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        assert sumar["elemente_suplimentare_respinse"] == 2
        assert sumar["elemente_suplimentare_plasate"] == 1
    finally:
        doc_path.unlink(missing_ok=True)


async def test_suplimentar_cu_in_modul_valid_se_ataseaza_in_interior():
    continut = {"suplimentare": [
        {"titlu": "Element atașat", "intro": "Intro atașată.", "in_modul": "vanzari"},
    ]}
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        assert sumar["elemente_suplimentare_plasate"] == 1
        assert "Element atașat" in "\n".join(_texte(doc_path))
    finally:
        doc_path.unlink(missing_ok=True)


async def test_acoperire_fara_cerinta_sau_raspuns_e_respinsa():
    continut = {"acoperire": [
        {"zona": "Z", "cerinta": "", "raspuns": "R.", "incadrare": "A"},
        {"zona": "Z", "cerinta": "C.", "raspuns": "", "incadrare": "A"},
        {"zona": "Z", "cerinta": "Cerință bună", "raspuns": "Răspuns.", "incadrare": "P"},
    ]}
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        assert sumar["cerinte_respinse"] == 2
        assert sumar["cerinte_plasate"] == 1
        assert sumar["cerinte_pe_incadrare"] == {"A": 0, "P": 1, "D": 0, "N": 0}
    finally:
        doc_path.unlink(missing_ok=True)


async def test_acoperire_incadrare_necunoscuta_devine_d_si_avertizeaza():
    continut = {"acoperire": [{"zona": "Z", "cerinta": "C.", "raspuns": "R.", "incadrare": "X"}]}
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        assert sumar["cerinte_pe_incadrare"]["D"] == 1
        assert "încadrare necunoscută" in sumar["avertisment"]
    finally:
        doc_path.unlink(missing_ok=True)


async def test_delimitare_randuri_incomplete_sunt_respinse():
    cfg = copy.deepcopy(CFG_MINIM)
    cfg["document_frate"] = {"exista": True, "titlu": "Frate", "arie_acoperita": "X", "coduri": []}
    continut = {"delimitare": [
        {"zona": "Z1", "tratat_in": "Altundeva", "interfatare": ""},
        {"zona": "Z2", "tratat_in": "Altundeva", "interfatare": "Punct de interfațare."},
    ]}
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, cfg, continut)
    try:
        assert sumar["delimitare_randuri_respinse"] == 1
        assert sumar["delimitare_randuri_plasate"] == 1
        assert "Z2" in _tot_textul(doc_path)
    finally:
        doc_path.unlink(missing_ok=True)


async def test_flux_operational_randuri_incomplete_sunt_respinse():
    continut = {"flux_operational": [
        {"etapa": "E1", "ce_se_intampla": "", "rezultat": "R"},
        {"etapa": "E2", "ce_se_intampla": "Se întâmplă ceva.", "rezultat": "Rezultatul."},
    ]}
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        assert sumar["flux_operational_randuri_respinse"] == 1
        assert sumar["flux_operational_randuri_plasate"] == 1
    finally:
        doc_path.unlink(missing_ok=True)


async def test_confirmari_incomplete_sunt_respinse():
    continut = {"confirmari": [
        {"aspect": "Aspect fără motiv", "motiv": ""},
        {"aspect": "Aspect complet", "motiv": "Motivul."},
    ]}
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        assert sumar["confirmari_respinse"] == 1
        assert sumar["confirmari_plasate"] == 1
        assert "Aspect complet" in _tot_textul(doc_path)
    finally:
        doc_path.unlink(missing_ok=True)


async def test_beneficii_valide_ajung_in_document_iar_golurile_dispar():
    continut = {"beneficii": ["Beneficiu unu.", "", "   ", "Beneficiu doi."]}
    doc_path, _ = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        text = "\n".join(_texte(doc_path))
        assert "Beneficiu unu." in text
        assert "Beneficiu doi." in text
    finally:
        doc_path.unlink(missing_ok=True)


async def test_ordine_cap4_care_nu_e_lista_foloseste_ordinea_implicita():
    doc_path, _ = await pipeline.run_scope_document_pipeline(
        GAZDA, CFG_MINIM, {"ordine_cap4": "nu sunt o listă"})
    try:
        assert doc_path.is_file()
    finally:
        doc_path.unlink(missing_ok=True)


# --- cele două erori deliberate NU se înghit -------------------------------

async def test_in_modul_exclus_ridica_eroare_nu_se_inghite():
    """`scope.genereaza` ridică deliberat `ValueError` pentru un element
    atașat unui modul care nu intră în document — pipeline-ul NU o prinde,
    o lasă să treacă neschimbată (routerul o transformă în 422)."""
    cfg = copy.deepcopy(CFG_MINIM)
    cfg["sectiuni_core"] = {"toate": False, "doar": ["contabilitate"], "fara": []}
    continut = {"suplimentare": [{"titlu": "Element orfan", "in_modul": "financiar"}]}
    with pytest.raises(ValueError, match="financiar"):
        await pipeline.run_scope_document_pipeline(GAZDA, cfg, continut)


async def test_ordine_cap4_incompleta_ridica_eroare_nu_se_inghite():
    cfg = copy.deepcopy(CFG_MINIM)
    cfg["sectiuni_core"] = {"toate": False, "doar": ["contabilitate", "financiar"], "fara": []}
    continut = {"ordine_cap4": ["contabilitate"]}
    with pytest.raises(ValueError, match="financiar"):
        await pipeline.run_scope_document_pipeline(GAZDA, cfg, continut)


async def test_ordine_cap4_cu_element_necunoscut_ridica_eroare():
    cfg = copy.deepcopy(CFG_MINIM)
    cfg["sectiuni_core"] = {"toate": False, "doar": ["contabilitate", "financiar"], "fara": []}
    continut = {"ordine_cap4": ["contabilitate", "financiar", "nu-exista-asa-ceva"]}
    with pytest.raises(ValueError, match="nu-exista-asa-ceva"):
        await pipeline.run_scope_document_pipeline(GAZDA, cfg, continut)


# --- curățarea fișierelor temporare pe calea de eșec -----------------------

async def test_esec_deliberat_nu_lasa_fisier_temporar(spion_mktemp):
    cfg = copy.deepcopy(CFG_MINIM)
    cfg["sectiuni_core"] = {"toate": False, "doar": ["contabilitate"], "fara": []}
    continut = {"suplimentare": [{"titlu": "X", "in_modul": "financiar"}]}
    with pytest.raises(ValueError):
        await pipeline.run_scope_document_pipeline(GAZDA, cfg, continut)
    assert spion_mktemp, "cel puțin un fișier temporar trebuia creat înainte de eroare"
    assert not any(p.exists() for p in spion_mktemp)


async def test_gazda_invalida_ridica_eroare_fara_fisier_temporar_ramas(tmp_path, spion_mktemp):
    gazda_inexistenta = tmp_path / "nu_exista.docx"
    with pytest.raises(FileNotFoundError):
        await pipeline.run_scope_document_pipeline(gazda_inexistenta, CFG_MINIM, {})
    assert spion_mktemp
    assert not any(p.exists() for p in spion_mktemp)


# --- cfg malformat / securitatea gazdei din cfg -----------------------------

async def test_cfg_care_nu_e_dict_nu_pica_pipelineul():
    doc_path, _ = await pipeline.run_scope_document_pipeline(GAZDA, None, {})  # type: ignore[arg-type]
    try:
        assert doc_path.is_file()
    finally:
        doc_path.unlink(missing_ok=True)


async def test_cfg_cu_subdicturi_malformate_nu_pica():
    cfg = {"document_frate": "nu sunt un dict", "capitole": ["nu", "sunt", "dict"],
          "sectiuni_core": 42, "stil": "text", "document": None}
    doc_path, _ = await pipeline.run_scope_document_pipeline(GAZDA, cfg, {})
    try:
        assert doc_path.is_file()
    finally:
        doc_path.unlink(missing_ok=True)


async def test_cfg_document_gazda_din_browser_e_ignorat():
    """Securitate: `cfg['stil']['document_gazda']` vine din browser și NU se
    folosește niciodată ca o cale de fișier de pe disc — vezi docstring-ul
    `_cfg_pregatit`. O cale inexistentă aici nu trebuie să ridice
    `FileNotFoundError`: pipeline-ul o ignoră complet, indiferent de gazda
    reală primită ca parametru separat."""
    cfg = copy.deepcopy(CFG_MINIM)
    cfg["stil"]["document_gazda"] = r"C:\nu\exista\niciodata.docx"
    doc_path, _ = await pipeline.run_scope_document_pipeline(GAZDA, cfg, {})
    try:
        assert doc_path.is_file()
    finally:
        doc_path.unlink(missing_ok=True)


async def test_cfg_document_gazda_din_browser_e_ignorat_fara_gazda_reala():
    cfg = copy.deepcopy(CFG_MINIM)
    cfg["stil"]["document_gazda"] = r"C:\nu\exista\niciodata.docx"
    doc_path, sumar = await pipeline.run_scope_document_pipeline(None, cfg, {})
    try:
        assert doc_path.is_file()
        assert sumar["capitole_scrise"] == 10
    finally:
        doc_path.unlink(missing_ok=True)


# --- on_step -----------------------------------------------------------

async def test_on_step_semnaleaza_parsing_si_building():
    pasi: list[str] = []
    doc_path, _ = await pipeline.run_scope_document_pipeline(
        GAZDA, CFG_MINIM, {}, on_step=pasi.append)
    try:
        assert pasi == ["parsing", "building"]
    finally:
        doc_path.unlink(missing_ok=True)


# --- sumarul ----------------------------------------------------------------

async def test_capitole_scrise_lista_titlurile_corecte():
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, {})
    try:
        assert any("Scopul documentului" in t for t in sumar["capitole"])
        assert any("Soluția ofertată" in t for t in sumar["capitole"])
        assert len(sumar["capitole"]) == sumar["capitole_scrise"]
    finally:
        doc_path.unlink(missing_ok=True)


async def test_sumarul_document_are_numerele_corecte():
    continut = {
        "suplimentare": [{"titlu": "Sub A", "in_modul": "vanzari"}, {"titlu": "Sub B"}],
        "acoperire": [
            {"zona": "Z", "cerinta": "C1", "raspuns": "R1", "incadrare": "A"},
            {"zona": "Z", "cerinta": "C2", "raspuns": "R2", "incadrare": "N"},
        ],
    }
    doc_path, sumar = await pipeline.run_scope_document_pipeline(GAZDA, CFG_MINIM, continut)
    try:
        assert sumar["module_core"] == 10
        assert sumar["elemente_suplimentare_primite"] == 2
        assert sumar["elemente_suplimentare_plasate"] == 2
        assert sumar["elemente_suplimentare_respinse"] == 0
        assert sumar["cerinte_primite"] == 2
        assert sumar["cerinte_plasate"] == 2
        assert sumar["cerinte_pe_incadrare"] == {"A": 1, "P": 0, "D": 0, "N": 1}
        assert sumar["avertisment"] == ""
    finally:
        doc_path.unlink(missing_ok=True)
