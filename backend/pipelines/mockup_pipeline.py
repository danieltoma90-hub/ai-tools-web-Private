import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent / "skills" / "mockup"
sys.path.insert(0, str(SKILL_DIR))

from parser import parse_excel
from word_parser import parse_word
from word_writer import write_word
from html_writer import write_html
from descriptions_builder import build_descriptions


def run_mockup_pipeline(input_path: Path) -> tuple[Path | None, str]:
    """Returns (docx_path_or_none, html_content). Accepts .xlsx or .docx.
    For .docx input, docx_path is None (only HTML mockup is generated).
    """
    ext = input_path.suffix.lower()
    if ext == ".xlsx":
        spec = parse_excel(input_path)
        descriptions = build_descriptions(spec)
        is_word_input = False
    elif ext == ".docx":
        spec, descriptions = parse_word(input_path)
        is_word_input = True
    else:
        raise ValueError(f"Format nesuportat: {ext}. Folosiți .xlsx sau .docx.")

    html_path = Path(tempfile.mktemp(suffix=".html"))
    write_html(spec, html_path)
    html = html_path.read_text(encoding="utf-8")
    html_path.unlink()

    if is_word_input:
        return None, html

    docx_path = Path(tempfile.mktemp(suffix=".docx"))
    write_word(spec, descriptions, docx_path)
    return docx_path, html
