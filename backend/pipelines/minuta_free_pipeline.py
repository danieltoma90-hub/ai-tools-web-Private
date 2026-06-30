"""Minuta Free Pipeline — foloseste Groq (Llama 3.3 70B) cu apeluri secventiale.

Groq free tier: 12,000 TPM, 30 RPM.
Apeluri secventiale cu 62s pauza intre ele pentru a respecta fereastra de 1 minut.
Trunchiere inteligenta a transcriptului: start (metadata), distribuit (sectiuni), final (actiuni).
"""
import asyncio
import json
import re
import sys
import tempfile
from html import escape
from pathlib import Path

from groq import AsyncGroq
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

GROQ_MODEL = "llama-3.3-70b-versatile"

# Caractere maxime per apel ca sa nu depasim 12,000 TPM
# 35,000 chars ≈ 8,750 tokens + ~500 prompt + ~1,500 raspuns = ~10,750 < 12,000
MAX_CHARS_PER_CALL = 35_000

# Transcrierile scurte (< 30,000 chars ≈ 7,500 tokens per call) pot fi procesate
# fara trunchiere si cu o pauza mai mica intre apeluri
SHORT_THRESHOLD = 30_000


# ── Parsare transcript ─────────────────────────────────────────────────────────

def extract_vtt_text(vtt_path: Path) -> str:
    lines = vtt_path.read_text(encoding="utf-8").splitlines()
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line or line == "WEBVTT" or re.match(r"^\d{2}:\d{2}:\d{2}", line):
            continue
        text_lines.append(line)
    return "\n".join(text_lines)


def extract_docx_text(docx_path: Path) -> str:
    doc = Document(str(docx_path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


# ── Trunchiere inteligenta ────────────────────────────────────────────────────

def _truncate_metadata(text: str) -> str:
    """Metadata: de la inceputul intrevederii (participanti, agenda)."""
    return text[:MAX_CHARS_PER_CALL]


def _truncate_sections(text: str) -> str:
    """Sectiuni: 4 fragmente distribuite uniform pe tot transcriptul."""
    if len(text) <= MAX_CHARS_PER_CALL:
        return text
    chunk = MAX_CHARS_PER_CALL // 4
    step = len(text) // 4
    parts = [text[i * step: i * step + chunk] for i in range(4)]
    return "\n\n[...]\n\n".join(parts)


def _truncate_actions(text: str) -> str:
    """Action items: de la finalul intrevederii (decizii, responsabilitati)."""
    return text[-MAX_CHARS_PER_CALL:] if len(text) > MAX_CHARS_PER_CALL else text


# ── Apel LLM ─────────────────────────────────────────────────────────────────

async def _call_groq(client: AsyncGroq, prompt_file: str, transcript: str) -> str:
    prompt = (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": f"{prompt}\n\n---TRANSCRIPT---\n{transcript}"}],
        max_tokens=4096,
        temperature=0.1,
    )
    return response.choices[0].message.content


# ── Parsare JSON ─────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict | list:
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    candidate = match.group(1) if match else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", candidate)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    target = m.group(1) if m else candidate
    if _JSON_REPAIR_AVAILABLE:
        repaired = repair_json(target)
        if repaired and repaired.strip() not in ("", "null", "{}"):
            return json.loads(repaired)

    raise ValueError(f"Nu s-a putut parsa JSON (primii 200 chars): {text[:200]}")


# ── Preview HTML ──────────────────────────────────────────────────────────────

def _block_to_html(block: dict) -> str:
    btype = block.get("type", "")
    if btype == "paragraph":
        return f"<p>{escape(block.get('text', ''))}</p>"
    if btype == "subheading":
        return f"<h4 style='color:#2E5496;margin:14px 0 4px'>{escape(block.get('text', ''))}</h4>"
    if btype == "bullets":
        items = "".join(f"<li>{escape(str(i))}</li>" for i in block.get("items", []))
        return f"<ul>{items}</ul>"
    if btype in ("table_2col", "table"):
        header = block.get("header", [])
        th = "".join(
            f"<th style='background:#1F3864;color:white;padding:6px 10px;text-align:left;border:1px solid #1F3864'>{escape(h)}</th>"
            for h in header
        )
        tr_rows = ""
        for i, row in enumerate(block.get("rows", [])):
            bg = "#f2f6fb" if i % 2 == 0 else "white"
            cells = "".join(
                f"<td style='padding:6px 10px;border:1px solid #dde3ed;background:{bg}'>{escape(str(c))}</td>"
                for c in row
            )
            tr_rows += f"<tr>{cells}</tr>"
        return f"<table style='border-collapse:collapse;width:100%;margin:8px 0'><tr>{th}</tr>{tr_rows}</table>"
    return ""


def _build_preview_html(data: dict) -> str:
    meta = data.get("meta", {})
    sectiuni = data.get("sectiuni", [])
    pasi = data.get("pasi_urmatori", [])
    context = data.get("context_si_scop") or []

    meta_rows = "".join(
        f"<tr><td style='font-weight:600;padding:6px 10px;background:#f2f6fb;width:130px;border:1px solid #dde3ed'>{escape(lbl)}</td>"
        f"<td style='padding:6px 10px;border:1px solid #dde3ed'>{escape(str(meta.get(key, '') or ''))}</td></tr>"
        for lbl, key in [
            ("Data", "data"), ("Client", "nume_client"), ("Subiect", "subiect"),
            ("Inițiator", "initiator"), ("Locație", "locatia"), ("Durată", "durata"),
        ]
        if meta.get(key)
    )

    body = ""
    sec_idx = 1
    if context:
        body += f"<h3>{sec_idx}. Context și Scop</h3>"
        for blk in context:
            body += _block_to_html(blk)
        sec_idx += 1

    for sec in sectiuni:
        body += f"<h3>{sec_idx}. {escape(sec.get('titlu', ''))}</h3>"
        for blk in sec.get("blocuri", []):
            body += _block_to_html(blk)
        sec_idx += 1

    if pasi:
        body += f"<h3>{sec_idx}. Pași următori</h3><ol>"
        for p in pasi:
            resp = escape(p.get("responsabil", ""))
            act = escape(p.get("actiune", ""))
            term = escape(p.get("termen", ""))
            body += f"<li><strong>{resp}</strong>: {act}"
            if term:
                body += f" <em style='color:#555'>({term})</em>"
            body += "</li>"
        body += "</ol>"

    subiect = escape(meta.get("subiect", ""))
    client_name = escape(meta.get("nume_client", ""))

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body{{font-family:Calibri,sans-serif;padding:24px;max-width:860px;margin:0 auto;color:#222}}
  h2{{color:#1F3864;margin-bottom:2px}}
  h3{{color:#1F3864;border-bottom:2px solid #1F3864;padding-bottom:4px;margin-top:22px}}
  h4{{color:#2E5496;margin:14px 0 4px}}
  table{{border-collapse:collapse;width:100%;margin:8px 0}}
  ul,ol{{padding-left:22px}} li{{margin:3px 0}}
</style>
</head><body>
<h2>MINUTA INTALNIRII</h2>
<p style="color:#2E5496;font-size:1.1em;font-weight:600;margin:2px 0">{subiect}</p>
<p style="color:#555;margin:0 0 12px">{client_name}</p>
<table>{meta_rows}</table>
{body}
</body></html>"""


# ── Pipeline principal ─────────────────────────────────────────────────────────

async def run_minuta_free_pipeline(
    transcript_path: Path,
    api_key: str,
    on_step=None,  # callable async(step: str) pentru progres UI
) -> tuple[Path, str]:
    """Pipeline cu Groq (gratuit): transcript (.vtt/.docx) → (docx_path, preview_html).

    Apeluri secventiale cu 62s intre ele pentru a respecta TPM limit Groq (12,000/min).
    Trunchiere inteligenta: metadata din start, sectiuni distribuite, actiuni din final.
    """
    if transcript_path.suffix.lower() == ".vtt":
        text = extract_vtt_text(transcript_path)
    else:
        text = extract_docx_text(transcript_path)

    long = len(text) > SHORT_THRESHOLD
    delay = 62 if long else 8  # scurt: 8s; lung: 62s (reset TPM window)

    client = AsyncGroq(api_key=api_key)

    if on_step:
        await on_step("metadata")
    meta_raw = await _call_groq(client, "extract_meeting_metadata.md", _truncate_metadata(text))
    meta_raw = _parse_json(meta_raw)

    await asyncio.sleep(delay)
    if on_step:
        await on_step("sections")
    sections_raw = await _call_groq(client, "extract_sections.md", _truncate_sections(text))
    sections = _parse_json(sections_raw)

    await asyncio.sleep(delay)
    if on_step:
        await on_step("actions")
    action_raw = await _call_groq(client, "extract_action_items.md", _truncate_actions(text))
    action_raw = _parse_json(action_raw)

    if on_step:
        await on_step("building")

    meta = meta_raw.get("meta", meta_raw) if isinstance(meta_raw, dict) else meta_raw
    if isinstance(meta, dict):
        meta["cod_proiect"] = meta.get("subiect", "")
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

    return output_path, _build_preview_html(data)
