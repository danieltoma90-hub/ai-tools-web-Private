import os
import tempfile
from pathlib import Path

from skills.mockup.parser import parse_excel
from skills.mockup.word_parser import parse_word
from skills.mockup.word_writer import write_word
from skills.mockup.html_writer import write_html
from skills.mockup.descriptions_builder import build_descriptions


def _mktemp_path(suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return Path(name)


def _load_spec(input_path: Path):
    """Parseaza fisierul de intrare in (spec, descriptions). Accepta .xlsx sau .docx."""
    ext = input_path.suffix.lower()
    if ext == ".xlsx":
        spec = parse_excel(input_path)
        return spec, build_descriptions(spec)
    if ext == ".docx":
        return parse_word(input_path)
    raise ValueError(f"Format nesuportat: {ext}. Folosiți .xlsx sau .docx.")


def run_mockup_pipeline(input_path: Path) -> tuple[Path, str]:
    """Returns (docx_path, html_content). Accepts .xlsx or .docx."""
    spec, descriptions = _load_spec(input_path)

    html_path = _mktemp_path(".html")
    write_html(spec, html_path)
    html = html_path.read_text(encoding="utf-8") if html_path.stat().st_size else ""
    html_path.unlink()

    docx_path = _mktemp_path(".docx")
    write_word(spec, descriptions, docx_path)
    return docx_path, html
