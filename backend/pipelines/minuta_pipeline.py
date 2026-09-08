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
from context_parser import parse_context


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


async def _call_claude(
    client: AsyncAnthropic, prompt_file: str, transcript: str, context: str = ""
) -> str:
    prompt = (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")
    # Contextul precede transcriptul: numele, rolurile si glosarul trebuie citite
    # inainte de discutie, ca sa corecteze ce a stalcit transcrierea automata.
    parts = [prompt]
    if context:
        parts.append(context)
    parts.append(f"---TRANSCRIPT---\n{transcript}")
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": "\n\n".join(parts)}],
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


async def _extract_metadata(client: AsyncAnthropic, transcript: str, context: str = "") -> dict:
    raw = await _call_claude(client, "extract_meeting_metadata.md", transcript, context)
    return _parse_json_from_response(raw)


async def _extract_sections(client: AsyncAnthropic, transcript: str, context: str = "") -> dict:
    raw = await _call_claude(client, "extract_sections.md", transcript, context)
    return _parse_json_from_response(raw)


async def _extract_action_items(client: AsyncAnthropic, transcript: str, context: str = "") -> list:
    raw = await _call_claude(client, "extract_action_items.md", transcript, context)
    return _parse_json_from_response(raw)


async def _extract_followup(client: AsyncAnthropic, transcript: str, context: str) -> dict:
    """Stadiul actiunilor deschise din context, dupa aceasta sedinta."""
    raw = await _call_claude(client, "extract_followup.md", transcript, context)
    return _parse_json_from_response(raw)


async def _extract_profile(client: AsyncAnthropic, transcript: str, context: str = "") -> dict:
    """Profilul beneficiarului, cerintele lui explicite si punctele ramase deschise."""
    raw = await _call_claude(client, "extract_profile_requirements.md", transcript, context)
    return _parse_json_from_response(raw)


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
    client = escape(meta.get("nume_client", ""))

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
<p style="color:#555;margin:0 0 12px">{client}</p>
<table>{meta_rows}</table>
{body}
</body></html>"""


def _profile_section(profile: dict | None) -> dict | None:
    """„Profilul beneficiarului" — cine e clientul, ca tabel."""
    if not isinstance(profile, dict):
        return None
    rows = [
        [p.get("aspect", ""), p.get("detaliu", "")]
        for p in profile.get("profil_beneficiar", [])
        if isinstance(p, dict) and p.get("aspect") and p.get("detaliu")
    ]
    if not rows:
        return None
    return {
        "titlu": "Profilul beneficiarului",
        "blocuri": [{"type": "table_2col", "header": ["Aspect", "Detaliu"], "rows": rows}],
    }


def _requirements_section(profile: dict | None) -> dict | None:
    """„Cerințe exprimate de beneficiar" — ce a cerut clientul, separat de rest."""
    if not isinstance(profile, dict):
        return None
    rows = [
        [c.get("zona", ""), c.get("cerinta", "")]
        for c in profile.get("cerinte_beneficiar", [])
        if isinstance(c, dict) and c.get("cerinta")
    ]
    if not rows:
        return None
    return {
        "titlu": "Cerințe și așteptări exprimate de beneficiar",
        "blocuri": [{"type": "table_2col", "header": ["Zonă", "Cerință exprimată"], "rows": rows}],
    }


def _open_points_section(profile: dict | None) -> dict | None:
    """„Puncte rămase deschise" — ce NU s-a decis. Separat de pașii următori:
    acolo stau sarcini atribuite, aici întrebări fără răspuns."""
    if not isinstance(profile, dict):
        return None
    items = [p for p in profile.get("puncte_deschise", []) if isinstance(p, str) and p.strip()]
    if not items:
        return None
    return {
        "titlu": "Puncte rămase deschise",
        "blocuri": [{"type": "bullets", "items": items}],
    }


def _followup_section(followup: dict | None) -> dict | None:
    """Sectiunea „Stadiul actiunilor anterioare", ca tabel. None daca nu e cazul."""
    if not isinstance(followup, dict):
        return None
    rows = []
    for item in followup.get("stadiu_actiuni", []):
        if not isinstance(item, dict) or not item.get("actiune"):
            continue
        detaliu = item.get("detaliu") or "—"
        rows.append([
            item.get("actiune", ""),
            item.get("responsabil", "") or "—",
            item.get("stare", "Nediscutată"),
            detaliu,
        ])
    if not rows:
        return None
    return {
        "titlu": "Stadiul acțiunilor anterioare",
        "blocuri": [{
            "type": "table",
            "header": ["Acțiune", "Responsabil", "Stare", "Detaliu"],
            "rows": rows,
        }],
    }


async def run_minuta_pipeline(
    transcript_path: Path, api_key: str, context_path: Path | None = None
) -> tuple[Path, str]:
    """Pipeline complet: transcript (.vtt sau .docx) → (docx_path, preview_html).

    context_path: fisierul optional de Context Proiect (.docx). Cand e prezent,
    numele/rolurile si glosarul din el corecteaza transcrierea, deciziile deja
    luate nu mai sunt raportate ca noi, iar minuta primeste in plus sectiunea
    „Stadiul actiunilor anterioare".
    """
    if transcript_path.suffix.lower() == ".vtt":
        text = extract_vtt_text(transcript_path)
    else:
        text = extract_docx_text(transcript_path)

    project_ctx = parse_context(context_path) if context_path else None
    context_block = project_ctx.as_prompt_block() if project_ctx else ""

    client = AsyncAnthropic(api_key=api_key)

    # Extragerile rulează în paralel — reduce timpul de la ~90s la ~30s
    tasks = [
        _extract_metadata(client, text, context_block),
        _extract_sections(client, text, context_block),
        _extract_action_items(client, text, context_block),
        _extract_profile(client, text, context_block),
    ]
    # A cincea extragere doar daca exista actiuni deschise de urmarit
    track_followup = bool(project_ctx and project_ctx.actiuni_deschise)
    if track_followup:
        tasks.append(_extract_followup(client, text, context_block))

    results = await asyncio.gather(*tasks)
    meta_raw, sections, action_raw, profile = results[0], results[1], results[2], results[3]
    followup = results[4] if track_followup else None

    # Claude returnează {"meta": {...}, "_observatii": [...]} — extragem doar interiorul
    meta = meta_raw.get("meta", meta_raw) if isinstance(meta_raw, dict) else meta_raw
    # Codul de proiect = descrierea meeting-ului (nu un cod generat)
    if isinstance(meta, dict):
        # Codul de proiect il stabileste modelul; il completam din subiect doar
        # daca lipseste, ca antetul sa nu ramana gol.
        if not meta.get("cod_proiect"):
            meta["cod_proiect"] = meta.get("subiect", "")
    # Claude returnează {"pasi_urmatori": [...]} — extragem lista
    action_items = action_raw.get("pasi_urmatori", action_raw) if isinstance(action_raw, dict) else action_raw

    # Ordinea de citire a minutei: cine e beneficiarul → ce s-a închis din trecut
    # → ce s-a discutat acum → ce a cerut clientul → ce a rămas nerezolvat.
    sectiuni = list(sections.get("sectiuni", []))

    profil = _profile_section(profile)
    cerinte = _requirements_section(profile)
    deschise = _open_points_section(profile)
    followup_section = _followup_section(followup)

    if followup_section:
        sectiuni.insert(0, followup_section)
    if profil:
        sectiuni.insert(0, profil)
    if cerinte:
        sectiuni.append(cerinte)
    if deschise:
        sectiuni.append(deschise)

    data = {
        "meta": meta,
        "context_si_scop": sections.get("context_si_scop"),
        "sectiuni": sectiuni,
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
