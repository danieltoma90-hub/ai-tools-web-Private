import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent / "skills" / "mockup"
sys.path.insert(0, str(SKILL_DIR))

from parser import parse_excel
from word_writer import write_word
from html_writer import write_html, write_html_compact
from descriptions_builder import build_descriptions


def run_mockup_pipeline(xlsx_path: Path) -> tuple[Path, str, str]:
    """Returns (docx_path, html_content, html_compact_content)."""
    spec = parse_excel(xlsx_path)
    descriptions = build_descriptions(spec)

    docx_path = Path(tempfile.mktemp(suffix=".docx"))
    html_path = Path(tempfile.mktemp(suffix=".html"))
    html_compact_path = Path(tempfile.mktemp(suffix=".html"))

    write_word(spec, descriptions, docx_path)
    write_html(spec, html_path)
    write_html_compact(spec, html_compact_path)

    html = html_path.read_text(encoding="utf-8")
    html_compact = html_compact_path.read_text(encoding="utf-8")

    html_path.unlink()
    html_compact_path.unlink()

    return docx_path, html, html_compact
