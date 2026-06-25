import json
import re
import sys
import tempfile
from pathlib import Path

from anthropic import Anthropic
from docx import Document

SKILL_DIR = Path(__file__).parent.parent / "skills" / "minuta"
PROMPTS_DIR = SKILL_DIR / "prompts"
TEMPLATE_PATH = SKILL_DIR / "template" / "F05_minuta_template.docx"

sys.path.insert(0, str(SKILL_DIR / "scripts"))
from build_minuta import build_minuta


def extract_vtt_text(vtt_path: Path) -> str:
    """Extrage textul pur dintr-un fișier .vtt (elimină timecodes și header)."""
    lines = vtt_path.read_text(encoding="utf-8").splitlines()
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line or line == "WEBVTT" or re.match(r"^\d{2}:\d{2}:\d{2}", line):
            continue
        text_lines.append(line)
    return "\n".join(text_lines)


def extract_docx_text(docx_path: Path) -> str:
    """Extrage textul pur dintr-un fișier .docx transcript."""
    doc = Document(str(docx_path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _call_claude(client: Anthropic, prompt_file: str, transcript: str) -> str:
    prompt = (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"{prompt}\n\n---TRANSCRIPT---\n{transcript}"
        }]
    )
    return response.content[0].text


def _parse_json_from_response(text: str) -> dict | list:
    """Extrage primul bloc JSON din răspunsul Claude."""
    match = re.search(r"```json\s*([\s\S]+?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    return json.loads(text)


def extract_metadata(client: Anthropic, transcript: str) -> dict:
    raw = _call_claude(client, "extract_meeting_metadata.md", transcript)
    return _parse_json_from_response(raw)


def extract_sections(client: Anthropic, transcript: str) -> dict:
    raw = _call_claude(client, "extract_sections.md", transcript)
    return _parse_json_from_response(raw)


def extract_action_items(client: Anthropic, transcript: str) -> list:
    raw = _call_claude(client, "extract_action_items.md", transcript)
    return _parse_json_from_response(raw)


def _build_preview_html(data: dict) -> str:
    meta = data.get("meta", {})
    sectiuni = data.get("sectiuni", [])
    pasi = data.get("pasi_urmatori", [])

    rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in [
            ("Data", meta.get("data", "")),
            ("Client", meta.get("nume_client", "")),
            ("Subiect", meta.get("subiect", "")),
            ("Durată", meta.get("durata", "")),
        ]
    )
    sectiuni_html = "".join(
        f"<h3>{s.get('titlu','')}</h3>"
        for s in sectiuni
    )
    pasi_html = "".join(
        f"<li>{p.get('responsabil','')}: {p.get('actiune','')}</li>"
        for p in pasi
    )

    return f"""
    <html><body style="font-family:Calibri,sans-serif;padding:24px;max-width:800px">
    <h2 style="color:#1F3864">MINUTA INTALNIRII</h2>
    <h3 style="color:#2E5496">{meta.get('subiect','')}</h3>
    <table border="1" cellpadding="6" style="border-collapse:collapse;width:100%">{rows}</table>
    {sectiuni_html}
    {'<h3>Pași următori</h3><ol>' + pasi_html + '</ol>' if pasi else ''}
    </body></html>
    """


async def run_minuta_pipeline(
    transcript_path: Path, api_key: str
) -> tuple[Path, str]:
    """Pipeline complet: transcript (.vtt sau .docx) → (docx_path, preview_html)."""
    if transcript_path.suffix.lower() == ".vtt":
        text = extract_vtt_text(transcript_path)
    else:
        text = extract_docx_text(transcript_path)

    client = Anthropic(api_key=api_key)
    meta = extract_metadata(client, text)
    sections = extract_sections(client, text)
    action_items = extract_action_items(client, text)

    data = {
        "meta": meta,
        "context_si_scop": sections.get("context_si_scop"),
        "sectiuni": sections.get("sectiuni", []),
        "pasi_urmatori": action_items,
        "include_signature": False,
    }

    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    ) as f:
        json.dump(data, f, ensure_ascii=False)
        json_path = Path(f.name)

    output_path = Path(tempfile.mktemp(suffix=".docx"))
    build_minuta(json_path, output_path, template_path=TEMPLATE_PATH)
    json_path.unlink()

    preview_html = _build_preview_html(data)
    return output_path, preview_html
