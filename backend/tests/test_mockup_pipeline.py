from pathlib import Path

import pytest

from pipelines.mockup_pipeline import run_mockup_pipeline
from skills.mockup.parser import ScreenSpec  # verifica pachetizarea

SAMPLE = (
    Path(__file__).parent.parent
    / "skills" / "mockup" / "input"
    / "Ecran generare consum de motorina pe baza de alimentari.docx"
)


@pytest.mark.skipif(not SAMPLE.exists(), reason="fișierul exemplu lipsește local")
def test_mockup_pipeline_smoke_docx():
    docx_path, html = run_mockup_pipeline(SAMPLE)
    try:
        assert docx_path.exists()
        assert docx_path.suffix == ".docx"
        assert "<html" in html.lower()
    finally:
        docx_path.unlink(missing_ok=True)


def test_unsupported_extension_raises(tmp_path):
    bad = tmp_path / "spec.pdf"
    bad.write_bytes(b"%PDF")
    with pytest.raises(ValueError, match="Format nesuportat"):
        run_mockup_pipeline(bad)
