import asyncio
import json
import re
import sys
import tempfile
from html import escape
from pathlib import Path

from anthropic import AsyncAnthropic
from docx import Document

try:
    from json_repair import repair_json
    _JSON_REPAIR_AVAILABLE = True
except ImportError:
    _JSON_REPAIR_AVAILABLE = False

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


async def _call_claude(client: AsyncAnthropic, prompt_file: str, transcript: str) -> str:
    prompt = (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"{prompt}\n\n---TRANSCRIPT---\n{transcript}"
        }]
    )
    return response.content[0].text


def _parse_json_from_response(text: str) -> dict | list:
    """Extrage primul bloc JSON din răspunsul Claude, cu repair ca fallback."""
    # 1. Încearcă să extragă din bloc ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    candidate = match.group(1) if match else text

    # 2. Încearcă parsare directă
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 3. Extrage cel mai mare bloc { } sau [ ] din text
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", candidate)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 4. Folosește json-repair pentru JSON malformat (ghilimele neescapate, virgule lipsă etc.)
    target = m.group(1) if m else candidate
    if _JSON_REPAIR_AVAILABLE:
        repaired = repair_json(target)
        if repaired and repaired.strip() not in ("", "null", "{}"):
            return json.loads(repaired)

    raise ValueError(f"Nu s-a putut parsa JSON din răspunsul Claude (primii 200 chars): {text[:200]}")


async def _extract_metadata(client: AsyncAnthropic, transcript: str) -> dict:
    raw = await _call_claude(client, "extract_meeting_metadata.md", transcript)
    return _parse_json_from_response(raw)


async def _extract_sections(client: AsyncAnthropic, transcript: str) -> dict:
    raw = await _call_claude(client, "extract_sections.md", transcript)
    return _parse_json_from_response(raw)


async def _extract_action_items(client: AsyncAnthropic, transcript: str) -> list:
    raw = await _call_claude(client, "extract_action_items.md", transcript)
    return _parse_json_from_response(raw)


def _build_preview_html(data: dict) -> str:
    meta = data.get("meta", {})
    sectiuni = data.get("sectiuni", [])
    pasi = data.get("pasi_urmatori", [])

    rows = "".join(
        f"<tr><td>{escape(k)}</td><td>{escape(str(v))}</td></tr>"
        for k, v in [
            ("Data", meta.get("data", "")),
            ("Client", meta.get("nume_client", "")),
            ("Subiect", meta.get("subiect", "")),
            ("Durată", meta.get("durata", "")),
        ]
    )
    sectiuni_html = "".join(
        f"<h3>{escape(s.get('titlu',''))}</h3>"
        for s in sectiuni
    )
    pasi_html = "".join(
        f"<li>{escape(p.get('responsabil',''))}: {escape(p.get('actiune',''))}</li>"
        for p in pasi
    )
    subiect = escape(meta.get("subiect", ""))

    return f"""
    <html><body style="font-family:Calibri,sans-serif;padding:24px;max-width:800px">
    <h2 style="color:#1F3864">MINUTA INTALNIRII</h2>
    <h3 style="color:#2E5496">{subiect}</h3>
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

    client = AsyncAnthropic(api_key=api_key)

    # Cele 3 extrageri rulează în paralel — reduce timpul de la ~90s la ~30s
    meta_raw, sections, action_raw = await asyncio.gather(
        _extract_metadata(client, text),
        _extract_sections(client, text),
        _extract_action_items(client, text),
    )

    # Claude returnează {"meta": {...}, "_observatii": [...]} — extragem doar interiorul
    meta = meta_raw.get("meta", meta_raw) if isinstance(meta_raw, dict) else meta_raw
    # Claude returnează {"pasi_urmatori": [...]} — extragem lista
    action_items = action_raw.get("pasi_urmatori", action_raw) if isinstance(action_raw, dict) else action_raw

    data = {
        "meta": meta,
        "context_si_scop": sections.get("context_si_scop"),
        "sectiuni": sections.get("sectiuni", []),
        "pasi_urmatori": action_items if isinstance(action_items, list) else [],
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
