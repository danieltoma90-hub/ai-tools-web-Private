"""Minuta Free Pipeline — Groq gratuit, acoperire completa prin map-reduce.

Faza MAP: transcriptul e impartit in bucati care incap in limita TPM; fiecare
bucata → 1 apel care extrage notite compacte (subiecte, decizii, actiuni).
Faza REDUCE: 1 apel de sinteza combina toate notitele in minuta finala.
Apeluri la 62s distanta (limita TPM e per minut → 1 apel/minut).

Model default: openai/gpt-oss-120b (8k TPM, 200k tokens/zi — cel mai apropiat
de Claude dintre modelele gratuite Groq). Override prin env GROQ_MODEL.
"""
import asyncio
import json
import os
import re
import sys
import tempfile
from html import escape
from pathlib import Path

from groq import AsyncGroq, RateLimitError
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

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# TPM (tokens/minut) per model pe planul gratuit Groq
MODEL_TPM = {
    "openai/gpt-oss-120b": 8_000,
    "llama-3.3-70b-versatile": 12_000,
}

# Cand limita ZILNICA (TPD) a modelului curent e atinsa, trecem automat pe
# urmatorul — fiecare model are cota zilnica separata (200k gpt-oss, 100k llama)
FALLBACK_CHAIN = [GROQ_MODEL] + [
    m for m in ("llama-3.3-70b-versatile", "openai/gpt-oss-120b") if m != GROQ_MODEL
]


def _next_model(current: str) -> str | None:
    idx = FALLBACK_CHAIN.index(current) if current in FALLBACK_CHAIN else -1
    return FALLBACK_CHAIN[idx + 1] if 0 <= idx < len(FALLBACK_CHAIN) - 1 else None

# Buget de output per tip de apel: sinteza primeste cel mai mult — acolo se
# scrie continutul final al minutei
OUT_TOKENS = {"metadata": 800, "map": 1_200, "reduce": 3_000}
PROMPT_RESERVE_TOKENS = 1_000   # promptul .md + framing
ROMANIAN_CHARS_PER_TOKEN = 2.2  # romana tokenizeaza mult mai des decat engleza
SAFETY = 0.8

CALL_DELAY_S = 62  # limita TPM e pe fereastra de 1 minut

# limita zilnica combinata a lantului de modele (200k gpt-oss + 100k llama),
# cu marja — peste asta recomandam versiunea Claude
MAX_FREE_TOKENS_PER_JOB = 280_000


def _min_tpm() -> int:
    # dimensionam dupa cel mai mic TPM din lant, ca cererea sa incapa
    # si dupa un eventual fallback pe alt model in mijlocul jobului
    return min(MODEL_TPM.get(m, 8_000) for m in FALLBACK_CHAIN)


def _chunk_size_chars() -> int:
    budget_tokens = _min_tpm() - PROMPT_RESERVE_TOKENS - OUT_TOKENS["map"]
    return int(budget_tokens * ROMANIAN_CHARS_PER_TOKEN * SAFETY)


# ── Parsare transcript ─────────────────────────────────────────────────────────

_CUE_ID_RE = re.compile(r"^[\w-]+/\d+-\d+$")
_SPEAKER_RE = re.compile(r"<v\s+([^>]+)>")


def extract_vtt_text(vtt_path: Path) -> str:
    """Text compact din VTT Teams: fara ID-uri de cue si timestamps, cu tag-urile
    <v Vorbitor> transformate in 'Vorbitor: replica' si replicile consecutive
    ale aceluiasi vorbitor comasate (reduce ~50% din volum, fara pierdere)."""
    lines = vtt_path.read_text(encoding="utf-8").splitlines()

    turns: list[tuple[str, list[str]]] = []  # (vorbitor, fragmente de text)
    speaker = ""
    for line in lines:
        line = line.strip()
        if (
            not line
            or line == "WEBVTT"
            or re.match(r"^\d{2}:\d{2}:\d{2}", line)
            or _CUE_ID_RE.match(line)
        ):
            continue
        m = _SPEAKER_RE.search(line)
        if m:
            speaker = m.group(1).strip()
        text = _SPEAKER_RE.sub("", line).replace("</v>", "").strip()
        if not text:
            continue
        if turns and turns[-1][0] == speaker:
            frags = turns[-1][1]
            if not frags or frags[-1] != text:  # sare peste liniile duplicate
                frags.append(text)
        else:
            turns.append((speaker, [text]))

    return "\n".join(
        f"{spk}: {' '.join(frags)}" if spk else " ".join(frags)
        for spk, frags in turns
    )


def extract_docx_text(docx_path: Path) -> str:
    doc = Document(str(docx_path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _split_chunks(text: str, chunk_chars: int) -> list[str]:
    """Imparte pe granite de linie, bucati de ~chunk_chars."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        if current_len + len(line) > chunk_chars and current:
            chunks.append("\n".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


# ── Apel LLM cu retry ─────────────────────────────────────────────────────────

async def _call_groq(
    client: AsyncGroq, prompt_file: str, content: str, state: dict, out_tokens: int
) -> str:
    """state["model"] = modelul curent; la limita zilnica trece pe urmatorul din lant."""
    prompt = (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")

    last_error: Exception | None = None
    for attempt in range(4):
        model = state["model"]
        kwargs = {}
        if model.startswith("openai/"):
            kwargs["reasoning_effort"] = "low"  # gpt-oss: reasoning tokens conteaza la TPM
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"{prompt}\n\n{content}"}],
                max_tokens=out_tokens,
                temperature=0.1,
                **kwargs,
            )
            return response.choices[0].message.content
        except RateLimitError as e:
            last_error = e
            if "per day" in str(e) or "TPD" in str(e):
                nxt = _next_model(model)
                if nxt is None:
                    raise RuntimeError(
                        "Limita zilnică gratuită Groq a fost atinsă pentru toate modelele. "
                        "Reîncercați mâine sau folosiți versiunea cu AI (Claude)."
                    ) from e
                state["model"] = nxt
                continue  # reincearca imediat pe modelul de rezerva (cota separata)
            if attempt < 3:
                await asyncio.sleep(65)  # limita pe minut — asteapta resetul ferestrei
    raise last_error


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


# ── Compresie notite (daca sinteza nu incape in TPM) ──────────────────────────

def _compress_notes(notes: list[dict], max_chars: int) -> list[dict]:
    """Reduce progresiv punctele per subiect pana ce notitele incap in budget."""
    for max_puncte in (3, 2, 1):
        total = sum(len(json.dumps(n, ensure_ascii=False)) for n in notes)
        if total <= max_chars:
            return notes
        for n in notes:
            for s in n.get("subiecte", []):
                s["puncte"] = s.get("puncte", [])[:max_puncte]
    return notes


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


# ── Estimare job (pre-check inainte de pornire) ───────────────────────────────

def estimate_free_job(transcript_path: Path) -> dict:
    """Estimeaza numarul de apeluri, tokens si durata pentru un transcript.

    Returneaza {"chunks", "calls", "est_tokens", "est_minutes", "fits_free_tier"}.
    """
    if transcript_path.suffix.lower() == ".vtt":
        text = extract_vtt_text(transcript_path)
    else:
        text = extract_docx_text(transcript_path)

    chunk_chars = _chunk_size_chars()
    chunks = max(1, len(_split_chunks(text, chunk_chars)))
    calls = chunks + 2  # metadata + map + reduce

    avg_call_tokens = (
        int(chunk_chars / ROMANIAN_CHARS_PER_TOKEN)
        + PROMPT_RESERVE_TOKENS
        + OUT_TOKENS["map"]
    )
    est_tokens = calls * avg_call_tokens
    return {
        "chunks": chunks,
        "calls": calls,
        "est_tokens": est_tokens,
        "est_minutes": max(1, round(calls * CALL_DELAY_S / 60)),
        "fits_free_tier": est_tokens <= MAX_FREE_TOKENS_PER_JOB,
    }


# ── Pipeline principal ─────────────────────────────────────────────────────────

async def run_minuta_free_pipeline(
    transcript_path: Path,
    api_key: str,
    on_step=None,  # callable async(step: str) pentru progres UI
) -> tuple[Path, str]:
    """Map-reduce cu Groq: transcript (.vtt/.docx) → (docx_path, preview_html).

    Acoperire completa a transcriptului. ~1 apel/minut → un meeting de 1h
    (10-12 bucati) dureaza ~12 minute.
    """
    if transcript_path.suffix.lower() == ".vtt":
        text = extract_vtt_text(transcript_path)
    else:
        text = extract_docx_text(transcript_path)

    chunk_chars = _chunk_size_chars()
    chunks = _split_chunks(text, chunk_chars)
    total = len(chunks)

    client = AsyncGroq(api_key=api_key)
    state = {"model": GROQ_MODEL}  # mutat de _call_groq la fallback pe limita zilnica

    # 1) Metadata — doar inceputul sedintei (participanti, subiect, agenda)
    if on_step:
        await on_step("metadata")
    meta_raw = await _call_groq(
        client, "extract_meeting_metadata.md",
        f"---TRANSCRIPT (inceput)---\n{text[:int(chunk_chars * 0.7)]}",
        state, OUT_TOKENS["metadata"],
    )
    meta_raw = _parse_json(meta_raw)

    # 2) MAP — notite compacte din fiecare bucata
    notes: list[dict] = []
    for i, chunk in enumerate(chunks, start=1):
        await asyncio.sleep(CALL_DELAY_S)
        if on_step:
            await on_step(f"chunk:{i}/{total}")
        raw = await _call_groq(
            client, "map_chunk_notes.md",
            f"---FRAGMENT {i}/{total}---\n{chunk}",
            state, OUT_TOKENS["map"],
        )
        try:
            notes.append(_parse_json(raw))
        except ValueError:
            # o bucata esuata nu strica intregul job — continuam fara ea
            continue

    if not notes:
        raise RuntimeError("Nicio bucata din transcript nu a putut fi procesata")

    # 3) REDUCE — sinteza finala din toate notitele
    await asyncio.sleep(CALL_DELAY_S)
    if on_step:
        await on_step("synthesis")
    # notitele trebuie sa incapa alaturi de prompt si de output-ul mare al sintezei
    reduce_input_budget = _min_tpm() - PROMPT_RESERVE_TOKENS - OUT_TOKENS["reduce"]
    notes = _compress_notes(
        notes, max_chars=int(reduce_input_budget * ROMANIAN_CHARS_PER_TOKEN * 0.9)
    )
    notes_text = "\n\n".join(
        f"---FRAGMENT {i}/{total}---\n{json.dumps(n, ensure_ascii=False)}"
        for i, n in enumerate(notes, start=1)
    )
    final_raw = await _call_groq(
        client, "reduce_synthesis.md", notes_text, state, OUT_TOKENS["reduce"]
    )
    final = _parse_json(final_raw)

    if on_step:
        await on_step("building")

    meta = meta_raw.get("meta", meta_raw) if isinstance(meta_raw, dict) else meta_raw
    if isinstance(meta, dict):
        meta["cod_proiect"] = meta.get("subiect", "")
    action_items = final.get("pasi_urmatori", [])

    data = {
        "meta": meta,
        "context_si_scop": final.get("context_si_scop"),
        "sectiuni": final.get("sectiuni", []),
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
