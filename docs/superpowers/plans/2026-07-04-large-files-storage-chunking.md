# Fișiere mari prin Supabase Storage + chunking AI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fișierele de 20-25MB+ urcă din browser direct în Supabase Storage (ocolind limitele Vercel/Render), iar generarea scenariilor acoperă integral textul spec-ului prin bucăți de ~15k tokeni pe granițe de capitol, acumulate într-un singur Excel.

**Architecture:** Un endpoint `POST /api/uploads/sign` emite URL-uri de upload semnate (bucket privat `uploads`, auto-creat); estimate devine JSON `{storage_path, filename}` și descarcă fișierul din storage (apoi îl șterge — storage e releu). În pipeline, `_pack_chunks` grupează capitolele H2 în bucăți ≤ `CHUNK_INPUT_TOKENS`, cu spargere la subcapitole/paragrafe pentru capitole uriașe; un apel Mistral per bucată, fallback per bucată, ID-uri globale la final.

**Tech Stack:** supabase-py 2.31 (`create_signed_upload_url`, `download`, `create_bucket`), FastAPI, Next.js 16 (fetch PUT direct la Supabase), pytest asyncio_mode=auto.

## Global Constraints

- **NU se modifică**: fișierele minuta (`routers/minuta.py`, `pipelines/minuta_*.py`, `skills/minuta/**`), formatul Excel (12 coloane, header `1F3864`, freeze `B2`), contractul job (`status/step/filename/xlsx_b64/scenarios/ai_used/storage_path/error`).
- Bucket upload: **`uploads`**, privat, `file_size_limit` 52.428.800 (50MB). Căi obiecte: `{tool}/{uuid4hex}{ext}`.
- Constante noi exacte: `CHUNK_INPUT_TOKENS = 15_000`; buget default `LLM_DAILY_TOKEN_BUDGET` devine `2_000_000`.
- Extensii per tool: scenarii `{".docx"}`, mockup `{".docx", ".xlsx"}`.
- `on_step` scenarii emite acum `"chunk:i/n:<modul>"` (nu mai emite `module:`) + `"building"`.
- Invariant packing (testat): concatenarea, în ordine, a tuturor paragrafelor din toate bucățile == toate paragrafele extrase din document (nimic omis, nimic duplicat).
- Texte UI/erori în română cu diacritice; `getattr(user, "email", None) or "anonymous"` pentru user.
- Teste backend din `D:\ai-tools-web\backend`: `python -m pytest tests/ -q`; frontend: `npm run build` din `D:\ai-tools-web\frontend`.
- `tempfile.mktemp` interzis (mkstemp + os.close).
- Commit per task cu path-uri explicite; NU se staghează `backend/.env`, `frontend/app/(app)/repository/page.tsx`, `backend/=0.30.0`, directoare untracked.

---

### Task 1: Helpers de upload în `storage.py`

**Files:**
- Modify: `backend/storage.py` (append la final; plus o constantă lângă `BUCKET`)
- Test: `backend/tests/test_storage_uploads.py` (nou; NU atinge `tests/test_storage.py` existent)

**Interfaces:**
- Consumes: `get_supabase()` din `auth.py` (există).
- Produces: `UPLOADS_BUCKET = "uploads"`; `ensure_uploads_bucket() -> None` (idempotent, memoizat per proces); `create_upload_url(tool: str, filename: str) -> dict` cu chei `storage_path, signed_url, token` (ridică `ValueError` la tool/extensie invalide); `download_upload(storage_path: str) -> Path` (descarcă în temp local cu sufixul corect, șterge obiectul din storage best-effort, ridică `ValueError` la path în afara `{tool}/`).

- [ ] **Step 1: Scrie testele (eșuează)**

```python
# backend/tests/test_storage_uploads.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import storage


@pytest.fixture(autouse=True)
def _reset_memo():
    storage._uploads_bucket_ready = False
    yield
    storage._uploads_bucket_ready = False


def _mock_sb():
    sb = MagicMock()
    return sb


def test_create_upload_url_returns_signed_parts():
    sb = _mock_sb()
    sb.storage.from_.return_value.create_signed_upload_url.return_value = {
        "signed_url": "https://x.supabase.co/storage/v1/object/upload/sign/uploads/scenarii/abc.docx?token=T",
        "token": "T",
        "path": "scenarii/abc.docx",
    }
    with patch("storage.get_supabase", return_value=sb):
        out = storage.create_upload_url("scenarii", "Spec Vânzări.docx")
    assert out["signed_url"].startswith("https://")
    assert out["token"] == "T"
    assert out["storage_path"].startswith("scenarii/")
    assert out["storage_path"].endswith(".docx")
    sb.storage.from_.assert_called_with("uploads")


def test_create_upload_url_rejects_bad_tool_and_ext():
    with pytest.raises(ValueError):
        storage.create_upload_url("minuta", "a.docx")  # minuta nu foloseste fluxul
    with pytest.raises(ValueError):
        storage.create_upload_url("scenarii", "a.pdf")
    with pytest.raises(ValueError):
        storage.create_upload_url("scenarii", "a.xlsx")  # scenarii accepta doar .docx
    with pytest.raises(ValueError):
        storage.create_upload_url("mockup", "a.txt")


def test_ensure_uploads_bucket_creates_once():
    sb = _mock_sb()
    sb.storage.list_buckets.return_value = []
    with patch("storage.get_supabase", return_value=sb):
        storage.ensure_uploads_bucket()
        storage.ensure_uploads_bucket()  # a doua oara: memoizat, fara apel nou
    assert sb.storage.create_bucket.call_count == 1
    _, kwargs = sb.storage.create_bucket.call_args
    assert kwargs["options"]["public"] is False
    assert kwargs["options"]["file_size_limit"] == 52_428_800


def test_ensure_uploads_bucket_skips_if_exists():
    sb = _mock_sb()
    bucket = MagicMock()
    bucket.name = "uploads"
    sb.storage.list_buckets.return_value = [bucket]
    with patch("storage.get_supabase", return_value=sb):
        storage.ensure_uploads_bucket()
    sb.storage.create_bucket.assert_not_called()


def test_download_upload_writes_temp_and_removes_object():
    sb = _mock_sb()
    sb.storage.from_.return_value.download.return_value = b"PK-continut"
    with patch("storage.get_supabase", return_value=sb):
        path = storage.download_upload("scenarii/abc123.docx")
    try:
        assert path.suffix == ".docx"
        assert path.read_bytes() == b"PK-continut"
        sb.storage.from_.return_value.remove.assert_called_once_with(["scenarii/abc123.docx"])
    finally:
        path.unlink(missing_ok=True)


def test_download_upload_rejects_foreign_paths():
    with pytest.raises(ValueError):
        storage.download_upload("documents/altceva.docx")
    with pytest.raises(ValueError):
        storage.download_upload("../etc/passwd")


def test_ensure_uploads_bucket_cleans_old_orphans():
    from datetime import datetime, timedelta, timezone
    sb = _mock_sb()
    sb.storage.list_buckets.return_value = []
    old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    sb.storage.from_.return_value.list.side_effect = lambda folder: (
        [
            {"name": "vechi.docx", "created_at": old},
            {"name": "nou.docx", "created_at": fresh},
        ]
        if folder == "scenarii"
        else []
    )
    with patch("storage.get_supabase", return_value=sb):
        storage.ensure_uploads_bucket()
    sb.storage.from_.return_value.remove.assert_called_once_with(["scenarii/vechi.docx"])
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_storage_uploads.py -v`
Expected: FAIL/ERROR — `storage` nu are `_uploads_bucket_ready`/`create_upload_url` etc.

- [ ] **Step 3: Implementează în `backend/storage.py`**

Lângă `BUCKET = "documents"` adaugă:

```python
UPLOADS_BUCKET = "uploads"
UPLOAD_TOOLS_EXT = {"scenarii": {".docx"}, "mockup": {".docx", ".xlsx"}}
UPLOAD_MAX_BYTES = 52_428_800  # 50MB — maximul planului free Supabase
```

La finalul fișierului adaugă:

```python
import os
import tempfile
import uuid

_uploads_bucket_ready = False


def ensure_uploads_bucket() -> None:
    """Creează bucket-ul privat 'uploads' dacă lipsește. Idempotent, memoizat per proces.

    Curăță best-effort obiectele orfane mai vechi de 24h (upload-uri abandonate
    înainte de estimate — fluxul normal șterge obiectul la download).
    """
    global _uploads_bucket_ready
    if _uploads_bucket_ready:
        return
    sb = get_supabase()
    existing = {getattr(b, "name", None) or getattr(b, "id", "") for b in sb.storage.list_buckets()}
    if UPLOADS_BUCKET not in existing:
        sb.storage.create_bucket(
            UPLOADS_BUCKET,
            options={"public": False, "file_size_limit": UPLOAD_MAX_BYTES},
        )
    _cleanup_old_uploads(sb)
    _uploads_bucket_ready = True


def _cleanup_old_uploads(sb, max_age_hours: int = 24) -> None:
    """Șterge obiectele orfane mai vechi de max_age_hours din bucket-ul uploads. Best-effort."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    for folder in UPLOAD_TOOLS_EXT:
        try:
            items = sb.storage.from_(UPLOADS_BUCKET).list(folder)
        except Exception:
            continue
        stale = []
        for item in items:
            created = item.get("created_at", "")
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                continue
            if created_dt < cutoff:
                stale.append(f"{folder}/{item['name']}")
        if stale:
            try:
                sb.storage.from_(UPLOADS_BUCKET).remove(stale)
            except Exception:
                pass


def create_upload_url(tool: str, filename: str) -> dict:
    """URL semnat de upload pentru fișierul-sursă al unui tool. Obiect: {tool}/{uuid}{ext}."""
    allowed = UPLOAD_TOOLS_EXT.get(tool)
    if allowed is None:
        raise ValueError(f"Tool necunoscut pentru upload: {tool!r}")
    ext = Path(_safe_filename(filename)).suffix.lower()
    if ext not in allowed:
        raise ValueError(f"Extensie neacceptată pentru {tool}: {ext or '(fără extensie)'}")

    ensure_uploads_bucket()
    storage_path = f"{tool}/{uuid.uuid4().hex}{ext}"
    sb = get_supabase()
    signed = sb.storage.from_(UPLOADS_BUCKET).create_signed_upload_url(storage_path)
    return {
        "storage_path": storage_path,
        "signed_url": signed["signed_url"],
        "token": signed["token"],
    }


def download_upload(storage_path: str) -> Path:
    """Descarcă un fișier-sursă din bucket-ul 'uploads' într-un temp local și șterge obiectul.

    Storage-ul e releu, nu depozit: după descărcare obiectul dispare (best-effort).
    """
    prefix = storage_path.split("/", 1)[0]
    if prefix not in UPLOAD_TOOLS_EXT or ".." in storage_path:
        raise ValueError(f"Cale de upload invalidă: {storage_path!r}")

    sb = get_supabase()
    data = sb.storage.from_(UPLOADS_BUCKET).download(storage_path)

    fd, tmp_name = tempfile.mkstemp(suffix=Path(storage_path).suffix)
    os.close(fd)
    path = Path(tmp_name)
    path.write_bytes(data)

    try:
        sb.storage.from_(UPLOADS_BUCKET).remove([storage_path])
    except Exception:
        pass  # obiect orfan — inofensiv, bucketul e doar releu
    return path
```

(Mută `import os/tempfile/uuid` sus lângă importurile existente — fără importuri la mijloc de fișier.)

- [ ] **Step 4: Rulează testele — trebuie să treacă**

Run: `python -m pytest tests/test_storage_uploads.py tests/test_storage.py -v`
Expected: toate pass

- [ ] **Step 5: Commit**

```bash
git add backend/storage.py backend/tests/test_storage_uploads.py
git commit -m "feat: bucket uploads cu URL semnat si download-releu in storage.py"
```

---

### Task 2: Router `POST /api/uploads/sign`

**Files:**
- Create: `backend/routers/uploads.py`
- Modify: `backend/main.py:5,19-22` (import + include_router)
- Test: `backend/tests/test_uploads.py` (nou)

**Interfaces:**
- Consumes: `storage.create_upload_url(tool, filename)`, `auth.verify_token`.
- Produces (Task 5/6 depind): `POST /api/uploads/sign` body JSON `{filename: str, tool: str}` → `{storage_path, signed_url, token}`; 422 la tool/extensie invalide; 401 fără token.

- [ ] **Step 1: Scrie testele (eșuează)**

```python
# backend/tests/test_uploads.py
from unittest.mock import patch

from main import app
from auth import verify_token


async def test_sign_without_auth_returns_401(client):
    response = await client.post(
        "/api/uploads/sign", json={"filename": "spec.docx", "tool": "scenarii"}
    )
    assert response.status_code == 401


async def test_sign_returns_signed_url(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        with patch(
            "routers.uploads.create_upload_url",
            return_value={
                "storage_path": "scenarii/abc.docx",
                "signed_url": "https://x/upload?token=T",
                "token": "T",
            },
        ) as mock_sign:
            response = await client.post(
                "/api/uploads/sign",
                json={"filename": "spec.docx", "tool": "scenarii"},
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["storage_path"] == "scenarii/abc.docx"
    assert body["token"] == "T"
    mock_sign.assert_called_once_with("scenarii", "spec.docx")


async def test_sign_invalid_tool_or_ext_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        with patch("routers.uploads.create_upload_url", side_effect=ValueError("Extensie neacceptată")):
            response = await client.post(
                "/api/uploads/sign",
                json={"filename": "spec.pdf", "tool": "scenarii"},
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "neacceptat" in response.json()["detail"].lower()
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_uploads.py -v`
Expected: 404 pe rută (nu există)

- [ ] **Step 3: Creează `backend/routers/uploads.py`**

```python
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import verify_token
from storage import create_upload_url

logger = logging.getLogger(__name__)
router = APIRouter()


class SignRequest(BaseModel):
    filename: str
    tool: str


@router.post("/uploads/sign")
async def sign_upload(req: SignRequest, user=Depends(verify_token)):
    """Emite un URL semnat pentru upload direct browser → Supabase Storage.

    Ocolește limita de 4,5MB a proxy-ului Vercel: fișierul nu mai trece prin el.
    """
    try:
        return create_upload_url(req.tool, req.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("uploads/sign FAILED: %s", e)
        raise HTTPException(status_code=502, detail=f"Nu s-a putut pregăti încărcarea: {e}")
```

- [ ] **Step 4: Înregistrează routerul în `backend/main.py`**

Linia 5: `from routers import minuta, mockup, scenarii, documents` → `from routers import minuta, mockup, scenarii, documents, uploads`
După `app.include_router(documents.router, prefix="/api")` adaugă:
```python
app.include_router(uploads.router, prefix="/api")
```

- [ ] **Step 5: Rulează — pass + suita întreagă verde**

Run: `python -m pytest tests/test_uploads.py -v && python -m pytest tests/ -q`
Expected: toate pass

- [ ] **Step 6: Commit**

```bash
git add backend/routers/uploads.py backend/main.py backend/tests/test_uploads.py
git commit -m "feat: endpoint uploads/sign pentru upload direct in Supabase Storage"
```

---

### Task 3: Packing pe bucăți în `scenarii_pipeline.py`

**Files:**
- Modify: `backend/pipelines/scenarii_pipeline.py` (adaugă după `_extract_structure`)
- Test: `backend/tests/test_scenarii_pipeline.py` (append)

**Interfaces:**
- Consumes: `_extract_structure` (există), `llm_client.estimate_tokens`.
- Produces (Task 4 depinde): `CHUNK_INPUT_TOKENS = 15_000`; `_pack_chunks(structure: dict[str, list[dict]]) -> list[dict]` — fiecare chunk `{"modul": str, "capitole": list[dict]}` cu aceeași formă de capitol (`titlu/text/subcapitole`); ordinea documentului păstrată; capitol > limită → spart la subcapitole (titlu capitol păstrat, părțile următoare cu sufix `" (continuare)"`); subcapitol > limită → text spart pe paragrafe în subcapitole `" (continuare)"`.

- [ ] **Step 1: Scrie testele (eșuează)**

Append la `backend/tests/test_scenarii_pipeline.py`:

```python
from pipelines.scenarii_pipeline import CHUNK_INPUT_TOKENS, _pack_chunks


def _all_paragraphs(structure):
    out = []
    for capitole in structure.values():
        for cap in capitole:
            out.extend(cap["text"])
            for sub in cap["subcapitole"]:
                out.extend(sub["text"])
    return out


def _chunk_paragraphs(chunks):
    out = []
    for ch in chunks:
        for cap in ch["capitole"]:
            out.extend(cap["text"])
            for sub in cap["subcapitole"]:
                out.extend(sub["text"])
    return out


def test_pack_chunks_small_structure_one_chunk_per_module(spec_docx):
    from pipelines.scenarii_pipeline import _extract_structure
    structure = _extract_structure(spec_docx)
    chunks = _pack_chunks(structure)
    # fixture mica: cate un chunk per modul
    assert len(chunks) == 2
    assert chunks[0]["modul"] == "Modul Achizitii"
    assert _chunk_paragraphs(chunks) == _all_paragraphs(structure)


def test_pack_chunks_splits_on_chapter_boundaries():
    # 4 capitole a ~7k tokeni fiecare => 2 per chunk (7k+7k=14k <= limita 15k)
    big_text = "x" * int(7_000 * 2.2)
    structure = {
        "Modul Mare": [
            {"titlu": f"Cap {i}", "text": [big_text], "subcapitole": []}
            for i in range(1, 5)
        ]
    }
    chunks = _pack_chunks(structure)
    assert len(chunks) == 2
    assert [c["titlu"] for c in chunks[0]["capitole"]] == ["Cap 1", "Cap 2"]
    assert [c["titlu"] for c in chunks[1]["capitole"]] == ["Cap 3", "Cap 4"]
    assert _chunk_paragraphs(chunks) == _all_paragraphs(structure)


def test_pack_chunks_splits_huge_chapter_at_subchapters():
    big = "x" * int(9_000 * 2.2)
    structure = {
        "Modul Mare": [{
            "titlu": "Cap Urias",
            "text": [],
            "subcapitole": [
                {"titlu": f"Sub {i}", "text": [big]} for i in range(1, 4)
            ],
        }]
    }
    chunks = _pack_chunks(structure)
    assert len(chunks) >= 2
    # titlul capitolului apare in fiecare parte (prima intacta, urmatoarele "(continuare)")
    titles = [cap["titlu"] for ch in chunks for cap in ch["capitole"]]
    assert titles[0] == "Cap Urias"
    assert all(t == "Cap Urias" or t == "Cap Urias (continuare)" for t in titles)
    assert _chunk_paragraphs(chunks) == _all_paragraphs(structure)


def test_pack_chunks_splits_huge_subchapter_by_paragraphs():
    para = "x" * int(4_000 * 2.2)
    structure = {
        "Modul Mare": [{
            "titlu": "Cap",
            "text": [],
            "subcapitole": [{"titlu": "Sub Urias", "text": [para] * 10}],  # ~40k tokeni
        }]
    }
    chunks = _pack_chunks(structure)
    assert len(chunks) >= 3
    subs = [s["titlu"] for ch in chunks for cap in ch["capitole"] for s in cap["subcapitole"]]
    assert subs[0] == "Sub Urias"
    assert all(t in ("Sub Urias", "Sub Urias (continuare)") for t in subs)
    assert _chunk_paragraphs(chunks) == _all_paragraphs(structure)
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_scenarii_pipeline.py -v -k pack_chunks`
Expected: ImportError `CHUNK_INPUT_TOKENS`/`_pack_chunks`

- [ ] **Step 3: Implementează packing-ul**

În `backend/pipelines/scenarii_pipeline.py`, după `_extract_structure`, adaugă:

```python
CHUNK_INPUT_TOKENS = 15_000  # input maxim per apel AI (~33k caractere)


def _cap_tokens(cap: dict) -> int:
    chars = len(cap["titlu"]) + sum(len(t) for t in cap["text"])
    for sub in cap["subcapitole"]:
        chars += len(sub["titlu"]) + sum(len(t) for t in sub["text"])
    return llm_client.estimate_tokens(" " * chars)


def _split_huge_sub(sub: dict) -> list[dict]:
    """Sparge un subcapitol urias pe paragrafe, in parti sub limita."""
    parts: list[dict] = []
    current: list[str] = []
    current_tokens = 0
    for para in sub["text"]:
        p_tokens = llm_client.estimate_tokens(para)
        if current and current_tokens + p_tokens > CHUNK_INPUT_TOKENS:
            titlu = sub["titlu"] if not parts else f"{sub['titlu']} (continuare)"
            parts.append({"titlu": titlu, "text": current})
            current, current_tokens = [], 0
        current.append(para)
        current_tokens += p_tokens
    titlu = sub["titlu"] if not parts else f"{sub['titlu']} (continuare)"
    parts.append({"titlu": titlu, "text": current})
    return parts


def _split_huge_cap(cap: dict) -> list[dict]:
    """Sparge un capitol urias la granite de subcapitol (si mai jos, pe paragrafe)."""
    pieces: list[dict] = []
    current = {"titlu": cap["titlu"], "text": list(cap["text"]), "subcapitole": []}
    current_tokens = _cap_tokens(current)

    subs: list[dict] = []
    for sub in cap["subcapitole"]:
        sub_tokens = llm_client.estimate_tokens(
            " " * (len(sub["titlu"]) + sum(len(t) for t in sub["text"]))
        )
        if sub_tokens > CHUNK_INPUT_TOKENS:
            subs.extend(_split_huge_sub(sub))
        else:
            subs.append(sub)

    for sub in subs:
        sub_tokens = llm_client.estimate_tokens(
            " " * (len(sub["titlu"]) + sum(len(t) for t in sub["text"]))
        )
        if current["subcapitole"] and current_tokens + sub_tokens > CHUNK_INPUT_TOKENS:
            pieces.append(current)
            current = {"titlu": f"{cap['titlu']} (continuare)", "text": [], "subcapitole": []}
            current_tokens = 0
        current["subcapitole"].append(sub)
        current_tokens += sub_tokens
    pieces.append(current)
    return pieces


def _pack_chunks(structure: dict[str, list[dict]]) -> list[dict]:
    """Grupeaza capitolele fiecarui modul in bucati <= CHUNK_INPUT_TOKENS.

    Granite naturale: capitol (H2); capitol urias -> subcapitole; subcapitol
    urias -> paragrafe. Invariant: niciun paragraf pierdut sau duplicat.
    """
    chunks: list[dict] = []
    for modul, capitole in structure.items():
        pieces: list[dict] = []
        for cap in capitole:
            if _cap_tokens(cap) > CHUNK_INPUT_TOKENS:
                pieces.extend(_split_huge_cap(cap))
            else:
                pieces.append(cap)

        current: list[dict] = []
        current_tokens = 0
        for cap in pieces:
            cap_tokens = _cap_tokens(cap)
            if current and current_tokens + cap_tokens > CHUNK_INPUT_TOKENS:
                chunks.append({"modul": modul, "capitole": current})
                current, current_tokens = [], 0
            current.append(cap)
            current_tokens += cap_tokens
        if current:
            chunks.append({"modul": modul, "capitole": current})
    return chunks
```

- [ ] **Step 4: Rulează — pass**

Run: `python -m pytest tests/test_scenarii_pipeline.py -v`
Expected: toate pass (packing + cele existente)

- [ ] **Step 5: Commit**

```bash
git add backend/pipelines/scenarii_pipeline.py backend/tests/test_scenarii_pipeline.py
git commit -m "feat: packing pe bucati la granite de capitol pentru scenarii"
```

---

### Task 4: Generare pe bucăți + estimare cu apeluri + buget 2M

**Files:**
- Modify: `backend/pipelines/scenarii_pipeline.py` (`_module_prompt`→`_chunk_prompt`, `_generate_module_ai`→`_generate_chunk_ai`, `run_scenarii_pipeline`, `estimate_scenarii_job`), `backend/llm_client.py` (o linie)
- Test: `backend/tests/test_scenarii_pipeline.py` (testele AI existente se actualizează la `chunk:`), `backend/tests/test_llm_client.py` (o aserțiune)

**Interfaces:**
- Consumes: `_pack_chunks` (Task 3).
- Produces (Task 5/6 depind): `run_scenarii_pipeline` neschimbat ca semnătură, dar `on_step` primește `"chunk:i/n:<modul>"` (i/n = index global peste toate bucățile); `estimate_scenarii_job(docx_path) -> {est_tokens, calls, modules, est_minutes, fits_budget}` (cheie NOUĂ `calls`); `llm_client.daily_budget()` default 2.000.000.

- [ ] **Step 1: Actualizează testele (eșuează)**

În `backend/tests/test_scenarii_pipeline.py`:
- În `test_run_pipeline_ai_generates_from_llm`, înlocuiește `assert any(s.startswith("module:1/2:") for s in steps)` cu `assert any(s.startswith("chunk:1/2:") for s in steps)`.
- În `test_estimate_scenarii_job`, adaugă `assert est["calls"] == 2` (fixture: 2 module mici → 2 bucăți).
- Adaugă:

```python
async def test_run_pipeline_ai_fallback_per_chunk():
    # 2 chunks in acelasi modul; al doilea apel pica -> doar capitolele lui devin stub
    big_text = "x" * int(10_000 * 2.2)
    structure = {
        "Modul Mare": [
            {"titlu": "Cap A", "text": [big_text], "subcapitole": []},
            {"titlu": "Cap B", "text": [big_text], "subcapitole": []},
        ]
    }
    calls = {"n": 0}

    async def flaky(system, user, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _AI_RESPONSE
        raise RuntimeError("Eroare LLM (429)")

    from docx import Document as WordDoc
    import tempfile, os
    doc = WordDoc()
    doc.add_heading("Modul Mare", level=1)
    for titlu in ("Cap A", "Cap B"):
        doc.add_heading(titlu, level=2)
        doc.add_paragraph(big_text)
    fd, name = tempfile.mkstemp(suffix=".docx"); os.close(fd)
    doc.save(name)

    with patch("pipelines.scenarii_pipeline.llm_client.chat", side_effect=flaky):
        xlsx_path, scenarios = await run_scenarii_pipeline(Path(name), use_ai=True)
    try:
        assert calls["n"] == 2
        ai_rows = [s for s in scenarios if s["ai"]]
        stub_rows = [s for s in scenarios if not s["ai"]]
        assert len(ai_rows) == 2          # din _AI_RESPONSE la primul chunk
        assert len(stub_rows) == 1        # Cap B -> stub
        assert "fără AI" in stub_rows[0]["observatii"]
    finally:
        xlsx_path.unlink(missing_ok=True)
        Path(name).unlink(missing_ok=True)
```

În `backend/tests/test_llm_client.py`, în `test_budget_counter_and_remaining`, adaugă la început:
```python
    monkeypatch.delenv("LLM_DAILY_TOKEN_BUDGET", raising=False)
    assert llm_client.daily_budget() == 2_000_000
```
(înaintea `monkeypatch.setenv(...)` existent.)

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_scenarii_pipeline.py tests/test_llm_client.py -v`
Expected: FAIL pe `chunk:1/2`, `calls`, buget 2M, fallback per chunk

- [ ] **Step 3: Implementează**

`backend/llm_client.py`: `return int(os.environ.get("LLM_DAILY_TOKEN_BUDGET", "500000"))` → `return int(os.environ.get("LLM_DAILY_TOKEN_BUDGET", "2000000"))`.

`backend/pipelines/scenarii_pipeline.py`:

Redenumește `OUT_TOKENS_PER_MODULE` → `OUT_TOKENS_PER_CALL` (păstrează valoarea 6000; actualizează toate referințele din fișier).

Înlocuiește `_module_prompt` cu:

```python
def _chunk_prompt(modul: str, capitole: list[dict], part: int, total: int) -> str:
    header = f"MODUL: {modul}"
    if total > 1:
        header += f" (partea {part} din {total})"
    lines = [header, ""]
    for cap in capitole:
        lines.append(f"CAPITOL: {cap['titlu']}")
        lines.extend(cap["text"])
        for sub in cap["subcapitole"]:
            lines.append(f"SUBCAPITOL: {sub['titlu']}")
            lines.extend(sub["text"])
        lines.append("")
    return "\n".join(lines)
```

Înlocuiește `_generate_module_ai` cu:

```python
async def _generate_chunk_ai(modul: str, capitole: list[dict], part: int, total: int) -> list[dict]:
    content = await llm_client.chat(
        _SYSTEM_PROMPT, _chunk_prompt(modul, capitole, part, total), max_tokens=OUT_TOKENS_PER_CALL
    )
    data = llm_client.parse_json(content)
    items = data.get("scenarii", [])
    if not items:
        raise ValueError("Răspuns AI fără scenarii")
    # Mistral trimite null pentru campurile goale; Pydantic aplica default-urile
    # doar pentru chei absente, deci eliminam valorile None inainte de validare.
    return [
        _Scenariu(**{k: v for k, v in s.items() if v is not None}).model_dump()
        for s in items
    ]
```

Înlocuiește `estimate_scenarii_job` cu:

```python
def estimate_scenarii_job(docx_path: Path) -> dict:
    """Pre-check: tokeni estimați, apeluri, module și dacă încape în bugetul zilnic."""
    structure = _extract_structure(docx_path)
    chunks = _pack_chunks(structure)
    calls = max(1, len(chunks))
    input_tokens = llm_client.estimate_tokens(" " * _structure_chars(structure))
    est_tokens = input_tokens + calls * (CALL_OVERHEAD_TOKENS + OUT_TOKENS_PER_CALL)
    return {
        "est_tokens": est_tokens,
        "calls": calls,
        "modules": max(1, len(structure)),
        "est_minutes": max(1, round(calls * 30 / 60)),
        "fits_budget": est_tokens <= llm_client.remaining_budget(),
    }
```

În `run_scenarii_pipeline`, înlocuiește bucla peste `module_items` cu bucla peste bucăți (restul funcției — blocul `if not scenarios`, atribuirea ID-urilor, `building`, `_write_excel` — rămâne identic):

```python
    structure = _extract_structure(docx_path)

    scenarios: list[dict] = []
    if use_ai:
        chunks = _pack_chunks(structure)
        # numarul partii in cadrul modulului, pentru antetul promptului
        per_module_totals: dict[str, int] = {}
        for ch in chunks:
            per_module_totals[ch["modul"]] = per_module_totals.get(ch["modul"], 0) + 1
        per_module_seen: dict[str, int] = {}

        for idx, ch in enumerate(chunks, start=1):
            modul = ch["modul"]
            per_module_seen[modul] = per_module_seen.get(modul, 0) + 1
            if on_step:
                on_step(f"chunk:{idx}/{len(chunks)}:{modul}")
            try:
                generated = await _generate_chunk_ai(
                    modul, ch["capitole"],
                    part=per_module_seen[modul], total=per_module_totals[modul],
                )
                for s in generated:
                    s["ai"] = True
                scenarios.extend(generated)
            except Exception:
                fallback = _module_stubs(
                    modul, ch["capitole"],
                    nota="Generat fără AI (fallback — apelul AI a eșuat)",
                )
                for s in fallback:
                    s["ai"] = False
                scenarios.extend(fallback)
    else:
        for modul, capitole in structure.items():
            stubs = _module_stubs(modul, capitole)
            for s in stubs:
                s["ai"] = False
            scenarios.extend(stubs)
```

- [ ] **Step 4: Rulează toată suita — pass**

Run: `python -m pytest tests/ -q`
Expected: toate pass

- [ ] **Step 5: Commit**

```bash
git add backend/pipelines/scenarii_pipeline.py backend/llm_client.py backend/tests/test_scenarii_pipeline.py backend/tests/test_llm_client.py
git commit -m "feat: generare scenarii pe bucati cu fallback per bucata; buget zilnic 2M"
```

---

### Task 5: Estimate pe JSON `{storage_path, filename}` în ambele routere

**Files:**
- Modify: `backend/routers/scenarii.py:25-46` (endpoint estimate + importuri), `backend/routers/mockup.py` (analog)
- Test: `backend/tests/test_scenarii.py`, `backend/tests/test_mockup.py` (testele de estimate se rescriu)

**Interfaces:**
- Consumes: `storage.download_upload(storage_path) -> Path` (Task 1), `estimate_scenarii_job`/`estimate_mockup_job` (există).
- Produces (Task 6 depinde): `POST /api/scenarii/estimate` body JSON `{storage_path: str, filename: str}` → `{estimate_id, est_tokens, calls, modules, est_minutes, fits_budget}`; `POST /api/mockup/estimate` la fel (fără `calls`/`modules`); 422 la extensie greșită sau fișier invalid (cu temp local șters); 404-like 422 „Fișierul încărcat nu a fost găsit" dacă download-ul eșuează. Generate/job neschimbate.

- [ ] **Step 1: Rescrie testele de estimate (eșuează)**

În `backend/tests/test_scenarii.py`: șterge `_DOCX_MIME` din testele de estimate și înlocuiește cele 3 teste care ating estimate (`test_estimate_without_auth_returns_401`, `test_estimate_wrong_format_returns_422`, partea de estimate din `test_estimate_then_generate_then_job_done` și `test_generate_ai_over_budget_returns_422`) astfel:

```python
import tempfile
from pathlib import Path as _P


def _spec_tempfile() -> str:
    fd, name = tempfile.mkstemp(suffix=".docx")
    import os as _os
    _os.close(fd)
    _P(name).write_bytes(_spec_bytes())
    return name


async def test_estimate_without_auth_returns_401(client):
    response = await client.post(
        "/api/scenarii/estimate",
        json={"storage_path": "scenarii/x.docx", "filename": "spec.docx"},
    )
    assert response.status_code == 401


async def test_estimate_wrong_format_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/scenarii/estimate",
            json={"storage_path": "scenarii/x.pdf", "filename": "spec.pdf"},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


async def test_estimate_missing_upload_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        with patch("routers.scenarii.download_upload", side_effect=Exception("object not found")):
            response = await client.post(
                "/api/scenarii/estimate",
                json={"storage_path": "scenarii/lipsa.docx", "filename": "spec.docx"},
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "nu a fost găsit" in response.json()["detail"]
```

iar în `test_estimate_then_generate_then_job_done` și `test_generate_ai_over_budget_returns_422`, apelul de estimate devine:

```python
        with patch("routers.scenarii.download_upload", return_value=_P(_spec_tempfile())):
            est_res = await client.post(
                "/api/scenarii/estimate",
                json={"storage_path": "scenarii/x.docx", "filename": "spec.docx"},
                headers={"Authorization": "Bearer fake"},
            )
```

În `backend/tests/test_mockup.py` analog: estimate cu `json={"storage_path": "mockup/x.docx", "filename": SAMPLE.name}` și `patch("routers.mockup.download_upload", return_value=<temp copie a SAMPLE>)`:

```python
def _sample_tempfile() -> Path:
    import os as _os, tempfile as _tf
    fd, name = _tf.mkstemp(suffix=".docx")
    _os.close(fd)
    p = Path(name)
    p.write_bytes(SAMPLE.read_bytes())
    return p
```
(în testele care folosesc SAMPLE, păstrează skipif-ul existent).

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_scenarii.py tests/test_mockup.py -v`
Expected: FAIL — estimate încă cere multipart

- [ ] **Step 3: Rescrie estimate în `backend/routers/scenarii.py`**

Înlocuiește importul `from storage import upload_file` cu `from storage import download_upload, upload_file`, șterge `File`/`UploadFile` din importul fastapi și `import tempfile`, adaugă modelul și endpoint-ul:

```python
class EstimateRequest(BaseModel):
    storage_path: str
    filename: str


@router.post("/scenarii/estimate")
async def estimate_scenarii(
    req: EstimateRequest,
    user=Depends(verify_token),
):
    """Pas 1: fișierul e deja în Supabase Storage (upload direct din browser).

    Îl descărcăm local, estimăm, și-l păstrăm ~10 min pentru generate.
    """
    if Path(req.filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .docx")

    try:
        input_path = download_upload(req.storage_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Fișierul încărcat nu a fost găsit în storage — reîncarcă fișierul.",
        )

    try:
        est = estimate_scenarii_job(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Fișier .docx invalid: {e}")

    estimate_id = jobs.save_estimate(input_path, req.filename, est)
    return {"estimate_id": estimate_id, **est}
```

- [ ] **Step 4: Rescrie estimate în `backend/routers/mockup.py`**

Înlocuiește importul `from storage import upload_file` cu `from storage import download_upload, upload_file`, șterge `File`/`UploadFile` din importul fastapi și `import tempfile`, apoi înlocuiește endpoint-ul multipart cu:

```python
class EstimateRequest(BaseModel):
    storage_path: str
    filename: str


@router.post("/mockup/estimate")
async def estimate_mockup(
    req: EstimateRequest,
    user=Depends(verify_token),
):
    """Pas 1: fișierul e deja în Supabase Storage (upload direct din browser).

    Îl descărcăm local, estimăm, și-l păstrăm ~10 min pentru generate.
    """
    if Path(req.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .xlsx sau .docx")

    try:
        input_path = download_upload(req.storage_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Fișierul încărcat nu a fost găsit în storage — reîncarcă fișierul.",
        )

    try:
        est = estimate_mockup_job(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Fișier invalid: {e}")

    estimate_id = jobs.save_estimate(input_path, req.filename, est)
    return {"estimate_id": estimate_id, **est}
```

- [ ] **Step 5: Rulează toată suita — pass**

Run: `python -m pytest tests/ -q`
Expected: toate pass

- [ ] **Step 6: Commit**

```bash
git add backend/routers/scenarii.py backend/routers/mockup.py backend/tests/test_scenarii.py backend/tests/test_mockup.py
git commit -m "feat: estimate primeste storage_path (JSON) si descarca din bucket-ul uploads"
```

---

### Task 6: Frontend — upload direct + stare `uploading` + etichete chunk

**Files:**
- Modify: `frontend/lib/api.ts` (uploadSourceFile + estimate JSON + tip), `frontend/app/(app)/scenarii/page.tsx`, `frontend/app/(app)/mockup/page.tsx`, `frontend/components/EstimateCard.tsx` (afișează `calls`)

**Interfaces:**
- Consumes: contractele HTTP din Task 2 și 5.
- Produces: `uploadSourceFile(file: File, tool: "scenarii" | "mockup") -> Promise<{storage_path: string}>`; `postScenariiEstimate(storagePath: string, filename: string)`; `postMockupEstimate(storagePath, filename)`; `EstimateResponse` cu `calls?: number`.

- [ ] **Step 1: `frontend/lib/api.ts`**

În `EstimateResponse` adaugă `calls?: number;` după `modules?: number;`.

Înlocuiește `postScenariiEstimate` și `postMockupEstimate` cu:

```typescript
export async function uploadSourceFile(
  file: File,
  tool: "scenarii" | "mockup"
): Promise<{ storage_path: string }> {
  const sign = (await apiFetch(`${PROXY}/uploads/sign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, tool }),
  })) as { storage_path: string; signed_url: string; token: string };

  const res = await fetch(sign.signed_url, {
    method: "PUT",
    headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file,
  });
  if (!res.ok) {
    throw new Error(
      `Încărcarea fișierului în storage a eșuat (cod ${res.status}). Reîncearcă.`
    );
  }
  return { storage_path: sign.storage_path };
}

function postEstimate(path: string, storagePath: string, filename: string) {
  return apiFetch(`${PROXY}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ storage_path: storagePath, filename }),
  });
}

export async function postScenariiEstimate(
  storagePath: string,
  filename: string
): Promise<EstimateResponse> {
  return postEstimate("scenarii/estimate", storagePath, filename) as Promise<EstimateResponse>;
}

export async function postMockupEstimate(
  storagePath: string,
  filename: string
): Promise<EstimateResponse> {
  return postEstimate("mockup/estimate", storagePath, filename) as Promise<EstimateResponse>;
}
```

- [ ] **Step 2: `frontend/app/(app)/scenarii/page.tsx`**

- `type State` primește `"uploading"`: `type State = "idle" | "uploading" | "estimating" | "ready" | "processing" | "done" | "error";`
- `MAX_UPLOAD_BYTES` devine `50 * 1024 * 1024` și comentariul: `// Limita bucket-ului Supabase (plan free)`; mesajul de eroare: `` `Fișierul are ${(file.size / 1024 / 1024).toFixed(1)}MB — peste limita de 50MB a storage-ului.` ``
- `stepLabel`: înlocuiește ramura `module:` cu:
```typescript
  const m = step.match(/^chunk:(\d+)\/(\d+):(.*)$/);
  if (m) return `Generez scenarii — partea ${m[1]} din ${m[2]} (${m[3]})...`;
```
- `handleEstimate` devine (înlocuiește corpul de la guard-ul de mărime în jos, păstrând cold-start retry-ul în jurul sign-ului):

```typescript
    setState("uploading");
    setError("");
    cancelledRef.current = false;
    try {
      let uploaded: { storage_path: string };
      try {
        uploaded = await uploadSourceFile(file, "scenarii");
      } catch (initErr) {
        // Render free tier adoarme — retry automat după 5s (sign-ul trece prin proxy)
        const msg = initErr instanceof Error ? initErr.message : "";
        if (isColdStartError(msg)) {
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          uploaded = await uploadSourceFile(file, "scenarii");
        } else {
          throw initErr;
        }
      }
      if (cancelledRef.current) return;

      setState("estimating");
      const est = await postScenariiEstimate(uploaded.storage_path, file.name);
      if (cancelledRef.current) return;
      setEstimate(est);
      setState("ready");
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
```

- În JSX, după blocul `{state === "estimating" && ...}` adaugă:
```tsx
        {state === "uploading" && (
          <ProcessingSpinner label="Se încarcă fișierul... (fișierele mari pot dura ~1 minut)" />
        )}
```
- Importă `uploadSourceFile` din `@/lib/api`.

- [ ] **Step 3: `frontend/app/(app)/mockup/page.tsx`** — aceleași 5 schimbări (stare `uploading`, guard 50MB, `uploadSourceFile(file, "mockup")`, `postMockupEstimate(uploaded.storage_path, file.name)`, spinner uploading). `stepLabel` rămâne neschimbat la mockup.

- [ ] **Step 4: `frontend/components/EstimateCard.tsx`** — linia cu detaliile devine:

```tsx
        <p className="text-sm text-slate-600">
          ~{tokens} tokeni · ~{estimate.est_minutes} min
          {estimate.calls ? ` · ${estimate.calls} apeluri AI` : ""}
          {estimate.modules ? ` · ${estimate.modules} module` : ""}
        </p>
```

- [ ] **Step 5: Build — pass**

Run: `npm run build` (din `frontend/`)
Expected: zero erori

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/api.ts "frontend/app/(app)/scenarii/page.tsx" "frontend/app/(app)/mockup/page.tsx" frontend/components/EstimateCard.tsx
git commit -m "feat: upload direct in Supabase Storage din browser, stare uploading, progres pe bucati"
```

---

### Task 7: Verificare E2E live cu fișier mare

**Files:** fără fișiere noi; fixuri minore dacă apar.

**Precondiții:** `MISTRAL_API_KEY` în `backend/.env` (există); backend local pe :8000, frontend dev pe :3000 (repornite cu codul final).

- [ ] **Step 1: Suita completă backend + build frontend**

Run: `python -m pytest tests/ -q` (backend) și `npm run build` (frontend)
Expected: toate verzi

- [ ] **Step 2: Repornește serverele locale cu codul nou**

Backend: oprește procesul uvicorn și repornește `python -m uvicorn main:app --host 127.0.0.1 --port 8000` din `backend/`. Frontend: repornește `npm run dev` din `frontend/`.

- [ ] **Step 3: Flux complet cu fișier de 14MB prin storage REAL (fără AI)**

Script Python (rulat din `backend/`): construiește docx de ~14MB (paragrafe hex din `os.urandom`, ca la reproducerea bug-ului), obține token Supabase (login parola), apoi: `POST /api/proxy/uploads/sign` (prin :3000, cookie `auth-token`) → PUT fișierul la `signed_url` → `POST /api/proxy/scenarii/estimate` cu `{storage_path, filename}` → verifică `calls > 1` → `generate {use_ai: false}` → poll până `done` → verifică `len(scenarios) >= 2` și `filename` `.xlsx`.
Expected: 200 la fiecare pas; obiectul dispare din bucket după estimate.

- [ ] **Step 4: Flux cu AI real pe spec REALIST multi-chunk (mic dar >1 bucată)**

Același script cu un docx de ~2 module × ~20k tokeni text real (paragrafe descriptive repetate cu variație), `use_ai: true`: verifică pași `chunk:1/n`, `chunk:2/n` în polling (`step`), `ai_used: true`, scenarii AI în toate modulele.
Expected: done, ai_used=True, scenarii cu titluri specifice; durata proporțională cu numărul de bucăți.

- [ ] **Step 5: Verificare manuală în browser (utilizatorul)**

Utilizatorul încarcă spec-ul REAL de 20-25MB pe pagina Scenarii: vede „Se încarcă fișierul...", apoi estimarea cu numărul de apeluri, pornește cu AI, urmărește progresul „partea i din n", descarcă Excel-ul și confirmă că toate capitolele apar.

- [ ] **Step 6: Commit final (doar dacă au fost fixuri la verificare)**

```bash
git add -A backend/ frontend/ && git commit -m "fix: ajustari post-verificare e2e fisiere mari"
```
