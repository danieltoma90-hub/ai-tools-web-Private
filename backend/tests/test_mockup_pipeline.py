import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from docx import Document as WordDocument

from pipelines.mockup_pipeline import run_mockup_pipeline, estimate_mockup_job
from skills.mockup import ai_enricher
from skills.mockup.parser import ScreenSpec, Section, FilterField

SAMPLE = (
    Path(__file__).parent.parent
    / "skills" / "mockup" / "input"
    / "Ecran generare consum de motorina pe baza de alimentari.docx"
)

_ENRICH_RESPONSE = json.dumps({
    "prezentare_generala": {
        "scop": "Ecranul permite generarea consumului de motorină.",
        "flux": ["Selectează gestiunea", "Filtrează alimentările", "Generează bonul"],
        "legaturi": "Câmpul Data controlează intrările vizibile.",
    },
    "descrieri_filtre": {"Data": "Data de referință pentru calculul stocului FIFO."},
    "descrieri_butoane": {},
    "descrieri_coloane": {},
})


def _mini_spec() -> tuple[ScreenSpec, dict]:
    sec = Section(title="Test", filter_fields=[FilterField(label="Data", mandatory=True)])
    spec = ScreenSpec(screen_title="Ecran Test", source_file="t.xlsx", sections=[sec])
    descriptions = {
        "descriere_generala": "Ecran de test.",
        "reguli_business": [],
        "descrieri_filtre": {"Data": "Data raport."},
        "descrieri_butoane": {},
        "descrieri_coloane": {},
        "mod_de_lucru": [],
    }
    return spec, descriptions


async def test_enrich_merges_overview_and_descriptions():
    spec, descriptions = _mini_spec()
    with patch("skills.mockup.ai_enricher.llm_client.chat", new=AsyncMock(return_value=_ENRICH_RESPONSE)):
        merged = await ai_enricher.enrich(spec, descriptions)
    assert merged["prezentare_generala"]["scop"].startswith("Ecranul permite")
    assert merged["descrieri_filtre"]["Data"] == "Data de referință pentru calculul stocului FIFO."
    # cheile existente raman
    assert merged["descriere_generala"] == "Ecran de test."


async def test_enrich_ignores_unknown_fields():
    spec, descriptions = _mini_spec()
    response = json.dumps({
        "prezentare_generala": {"scop": "x", "flux": [], "legaturi": ""},
        "descrieri_filtre": {"CampInexistent": "nu trebuie sa apara"},
    })
    with patch("skills.mockup.ai_enricher.llm_client.chat", new=AsyncMock(return_value=response)):
        merged = await ai_enricher.enrich(spec, descriptions)
    assert "CampInexistent" not in merged["descrieri_filtre"]


@pytest.mark.skipif(not SAMPLE.exists(), reason="fișierul exemplu lipsește local")
async def test_pipeline_with_ai_failure_falls_back_deterministic():
    with patch(
        "pipelines.mockup_pipeline.ai_enricher.enrich",
        new=AsyncMock(side_effect=RuntimeError("LLM down")),
    ):
        docx_path, html, ai_used = await run_mockup_pipeline(SAMPLE, use_ai=True)
    try:
        assert ai_used is False
        assert docx_path.exists()
    finally:
        docx_path.unlink(missing_ok=True)


@pytest.mark.skipif(not SAMPLE.exists(), reason="fișierul exemplu lipsește local")
def test_estimate_mockup_job_returns_budget_info():
    est = estimate_mockup_job(SAMPLE)
    assert est["est_tokens"] > 0
    assert est["est_minutes"] == 1
    assert isinstance(est["fits_budget"], bool)


@pytest.mark.skipif(not SAMPLE.exists(), reason="fișierul exemplu lipsește local")
async def test_mockup_pipeline_smoke_docx():
    docx_path, html, ai_used = await run_mockup_pipeline(SAMPLE)
    try:
        assert docx_path.exists()
        assert docx_path.suffix == ".docx"
        assert "<html" in html.lower()
        assert ai_used is False
    finally:
        docx_path.unlink(missing_ok=True)


async def test_unsupported_extension_raises(tmp_path):
    bad = tmp_path / "spec.pdf"
    bad.write_bytes(b"%PDF")
    with pytest.raises(ValueError, match="Format nesuportat"):
        await run_mockup_pipeline(bad)
