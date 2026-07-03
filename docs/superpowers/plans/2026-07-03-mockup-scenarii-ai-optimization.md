# Optimizare Mockup + Scenarii cu AI gratuit (Mistral) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scenariile de testare se generează din textul complet al specificației cu Mistral (gratuit), mockup-ul primește secțiune „Prezentare generală" + descrieri îmbogățite, ambele cu flux estimate → alegere utilizator → job async cu progres, plus refactoring (mktemp, sys.path, job store partajat).

**Architecture:** Un client LLM provider-agnostic (`llm_client.py`, Mistral implicit) e folosit de pipeline-urile scenarii și mockup. Routerele trec pe contract async în 3 pași (estimate/generate/job) cu un job store partajat (`jobs.py`). Frontend-ul primește mașină de stări nouă cu EstimateCard, progres pas-cu-pas și preview tabel. Varianta fără AI produce exact outputul de azi (fallback garantat).

**Tech Stack:** FastAPI + httpx (backend, Python 3.14), Mistral API (`mistral-large-latest`, free tier), Next.js 16 App Router + React 19 + Tailwind (frontend), pytest + pytest-asyncio (asyncio_mode=auto), openpyxl, python-docx.

## Global Constraints

- **NU se modifică**: `routers/minuta.py`, `pipelines/minuta_pipeline.py`, `pipelines/minuta_free_pipeline.py`, `skills/minuta/**`. Groq rămâne exclusiv pentru minuta.
- Env vars noi (exact aceste nume): `LLM_PROVIDER` (default `mistral`), `MISTRAL_API_KEY`, `MISTRAL_MODEL` (default `mistral-large-latest`), `LLM_DAILY_TOKEN_BUDGET` (default `500000`).
- Formatul Excel scenarii rămâne identic: 12 coloane `ID, Capitol, Subcapitol, Titlu Scenariu, Obiectiv, Precondiții, Pași de Execuție, Rezultat Așteptat, Tip Test, Prioritate, Dependente, Observații`, header fill `1F3864`, freeze `B2`.
- Textele UI în română, diacritice corecte.
- Backend-ul folosește `getattr(user, "email", None) or "anonymous"` (verify_token returnează obiect Supabase User, NU dict — `.get()` e bug latent în routerele vechi).
- Teste backend: rulate din `D:\ai-tools-web\backend` cu `python -m pytest tests/ -v` (asyncio_mode=auto — nu e nevoie de `@pytest.mark.asyncio`).
- Frontend verificat cu `npm run build` din `D:\ai-tools-web\frontend`.
- `tempfile.mktemp` interzis — folosește `tempfile.mkstemp` + `os.close(fd)`.
- Commit după fiecare task, mesaje în stilul repo-ului (`feat:`, `fix:`, `refactor:`, `test:`).

---

### Task 1: Client LLM provider-agnostic (`llm_client.py`)

**Files:**
- Create: `backend/llm_client.py`
- Test: `backend/tests/test_llm_client.py`

**Interfaces:**
- Produces: `async chat(system: str, user: str, max_tokens: int = 4000, json_mode: bool = True) -> str`; `estimate_tokens(text: str) -> int`; `remaining_budget() -> int`; `add_usage(tokens: int) -> None`; `parse_json(content: str) -> dict`; constante `ROMANIAN_CHARS_PER_TOKEN = 2.2`, `RETRY_DELAYS`, `MIN_CALL_INTERVAL_S`; variabilă de test `TRANSPORT` (httpx transport injectabil).

- [ ] **Step 1: Scrie testele (eșuează)**

```python
# backend/tests/test_llm_client.py
import json

import httpx
import pytest

import llm_client


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "MIN_CALL_INTERVAL_S", 0)
    monkeypatch.setattr(llm_client, "RETRY_DELAYS", [0, 0, 0])
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0
    yield
    llm_client.TRANSPORT = None


def test_estimate_tokens_romanian_heuristic():
    assert llm_client.estimate_tokens("a" * 220) == 100


def test_budget_counter_and_remaining(monkeypatch):
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "1000")
    assert llm_client.remaining_budget() == 1000
    llm_client.add_usage(300)
    assert llm_client.remaining_budget() == 700


def _mock_response(content: str, total_tokens: int = 50):
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"total_tokens": total_tokens},
    }


async def test_chat_success_returns_content_and_counts_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "mistral-large-latest"
        assert body["response_format"] == {"type": "json_object"}
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json=_mock_response('{"ok": true}', 42))

    llm_client.TRANSPORT = httpx.MockTransport(handler)
    result = await llm_client.chat("sistem", "utilizator")
    assert result == '{"ok": true}'
    assert llm_client._usage["tokens"] == 42


async def test_chat_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"message": "rate limited"})
        return httpx.Response(200, json=_mock_response("ok", 10))

    llm_client.TRANSPORT = httpx.MockTransport(handler)
    result = await llm_client.chat("s", "u", json_mode=False)
    assert result == "ok"
    assert calls["n"] == 2


async def test_chat_raises_after_retry_exhaustion():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "rate limited"})

    llm_client.TRANSPORT = httpx.MockTransport(handler)
    with pytest.raises(RuntimeError, match="429"):
        await llm_client.chat("s", "u")


async def test_chat_without_key_raises(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        await llm_client.chat("s", "u")


def test_parse_json_strips_markdown_fences():
    assert llm_client.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm_client.parse_json('{"a": 1}') == {"a": 1}
```

- [ ] **Step 2: Rulează testele — trebuie să eșueze**

Run: `python -m pytest tests/test_llm_client.py -v` (din `backend/`)
Expected: FAIL / ERROR cu `ModuleNotFoundError: No module named 'llm_client'`

- [ ] **Step 3: Implementează `backend/llm_client.py`**

```python
"""Client LLM provider-agnostic pentru mockup si scenarii.

Provider implicit: Mistral La Plateforme (tier gratuit "Experiment").
Providerul se schimba din env LLM_PROVIDER fara a atinge pipeline-urile.
NU se foloseste pentru minuta (aceea ramane pe Groq).
"""
import asyncio
import json
import os
import time
from datetime import date

import httpx

ROMANIAN_CHARS_PER_TOKEN = 2.2
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MIN_CALL_INTERVAL_S = 1.5  # free tier ~1 req/sec
RETRY_DELAYS = [2, 8, 20]

# Transport injectabil pentru teste (httpx.MockTransport)
TRANSPORT: httpx.AsyncBaseTransport | None = None

_throttle_lock = asyncio.Lock()
_last_call = 0.0

# Contor zilnic in-memory — protectie soft, se reseteaza la restart Render
_usage: dict = {"day": "", "tokens": 0}


def _model() -> str:
    return os.environ.get("MISTRAL_MODEL", "mistral-large-latest")


def _api_key() -> str:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY lipsă pe server")
    return key


def daily_budget() -> int:
    return int(os.environ.get("LLM_DAILY_TOKEN_BUDGET", "500000"))


def _usage_today() -> int:
    today = date.today().isoformat()
    if _usage["day"] != today:
        _usage["day"] = today
        _usage["tokens"] = 0
    return _usage["tokens"]


def add_usage(tokens: int) -> None:
    _usage_today()
    _usage["tokens"] += tokens


def remaining_budget() -> int:
    return max(0, daily_budget() - _usage_today())


def estimate_tokens(text: str) -> int:
    return int(len(text) / ROMANIAN_CHARS_PER_TOKEN)


def parse_json(content: str) -> dict:
    """JSON robust: accepta si continut impachetat in ```json ... ```."""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


async def chat(
    system: str,
    user: str,
    max_tokens: int = 4000,
    json_mode: bool = True,
) -> str:
    """Un apel chat spre providerul curent, cu throttle si retry pe 429/5xx."""
    global _last_call
    api_key = _api_key()
    payload: dict = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {api_key}"}

    async with _throttle_lock:
        wait = MIN_CALL_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()

    async with httpx.AsyncClient(timeout=180, transport=TRANSPORT) as client:
        last_status = 0
        for attempt in range(len(RETRY_DELAYS) + 1):
            resp = await client.post(MISTRAL_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                add_usage(int(usage.get("total_tokens", max_tokens)))
                return data["choices"][0]["message"]["content"]
            last_status = resp.status_code
            if resp.status_code in (429, 500, 502, 503) and attempt < len(RETRY_DELAYS):
                await asyncio.sleep(RETRY_DELAYS[attempt])
                continue
            break
    raise RuntimeError(f"Eroare LLM ({last_status}) — reîncercările au fost epuizate")
```

- [ ] **Step 4: Rulează testele — trebuie să treacă**

Run: `python -m pytest tests/test_llm_client.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat: client LLM provider-agnostic (Mistral free tier) cu buget zilnic si retry"
```

---

### Task 2: Job store + estimate store partajat (`jobs.py`)

**Files:**
- Create: `backend/jobs.py`
- Test: `backend/tests/test_jobs.py`

**Interfaces:**
- Produces: `create_job(user_email: str) -> str`; `set_step(job_id: str, step: str) -> None`; `finish(job_id: str, **payload) -> None`; `fail(job_id: str, error: str) -> None`; `get_job(job_id: str) -> dict | None`; `save_estimate(file_path: Path, filename: str, data: dict) -> str`; `pop_estimate(estimate_id: str) -> dict | None` (dict conține `file_path: str`, `filename: str` + cheile din `data`); `ESTIMATE_TTL_S = 600`.
- Notă: minuta NU se migrează pe acest store — își păstrează `_jobs` propriu.

- [ ] **Step 1: Scrie testele (eșuează)**

```python
# backend/tests/test_jobs.py
import time
from pathlib import Path

import jobs


def test_job_lifecycle():
    job_id = jobs.create_job("ana@totalsoft.ro")
    job = jobs.get_job(job_id)
    assert job == {"status": "processing", "user_email": "ana@totalsoft.ro"}

    jobs.set_step(job_id, "module:1/3:Nomenclatoare")
    assert jobs.get_job(job_id)["step"] == "module:1/3:Nomenclatoare"

    jobs.finish(job_id, filename="a.xlsx", xlsx_b64="abc", ai_used=True)
    job = jobs.get_job(job_id)
    assert job["status"] == "done"
    assert job["filename"] == "a.xlsx"
    assert job["ai_used"] is True


def test_fail_sets_error():
    job_id = jobs.create_job("x@y.z")
    jobs.fail(job_id, "ceva a mers prost")
    assert jobs.get_job(job_id) == {"status": "error", "error": "ceva a mers prost"}


def test_get_unknown_job_returns_none():
    assert jobs.get_job("nu-exista") is None


def test_estimate_save_and_pop(tmp_path):
    f = tmp_path / "spec.docx"
    f.write_bytes(b"PK")
    eid = jobs.save_estimate(f, "spec.docx", {"est_tokens": 123, "fits_budget": True})
    est = jobs.pop_estimate(eid)
    assert est["filename"] == "spec.docx"
    assert est["est_tokens"] == 123
    assert est["file_path"] == str(f)
    # pop e destructiv
    assert jobs.pop_estimate(eid) is None


def test_estimate_expires_and_deletes_file(tmp_path, monkeypatch):
    f = tmp_path / "spec.docx"
    f.write_bytes(b"PK")
    eid = jobs.save_estimate(f, "spec.docx", {})
    # fortam expirarea
    jobs._estimates[eid]["created"] = time.monotonic() - jobs.ESTIMATE_TTL_S - 1
    assert jobs.pop_estimate(eid) is None
    assert not f.exists()
```

- [ ] **Step 2: Rulează testele — trebuie să eșueze**

Run: `python -m pytest tests/test_jobs.py -v`
Expected: ERROR cu `ModuleNotFoundError: No module named 'jobs'`

- [ ] **Step 3: Implementează `backend/jobs.py`**

```python
"""Job store + estimate store in-memory, partajate de mockup si scenarii.

Se golesc la fiecare restart/redeploy Render (acceptat — frontend-ul trateaza
job/estimate expirat cu mesaj "reincarca fisierul").
Minuta NU foloseste acest modul (are propriul _jobs, neatins).
"""
import time
import uuid
from pathlib import Path
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}
_estimates: dict[str, dict[str, Any]] = {}

ESTIMATE_TTL_S = 600  # fisierul temporar traieste 10 minute


def create_job(user_email: str) -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "user_email": user_email}
    return job_id


def set_step(job_id: str, step: str) -> None:
    if job_id in _jobs:
        _jobs[job_id]["step"] = step


def finish(job_id: str, **payload: Any) -> None:
    _jobs[job_id] = {"status": "done", **payload}


def fail(job_id: str, error: str) -> None:
    _jobs[job_id] = {"status": "error", "error": error}


def get_job(job_id: str) -> dict[str, Any] | None:
    return _jobs.get(job_id)


def save_estimate(file_path: Path, filename: str, data: dict[str, Any]) -> str:
    _cleanup_expired()
    estimate_id = str(uuid.uuid4())
    _estimates[estimate_id] = {
        "file_path": str(file_path),
        "filename": filename,
        "created": time.monotonic(),
        **data,
    }
    return estimate_id


def pop_estimate(estimate_id: str) -> dict[str, Any] | None:
    _cleanup_expired()
    return _estimates.pop(estimate_id, None)


def _cleanup_expired() -> None:
    now = time.monotonic()
    for eid in list(_estimates):
        entry = _estimates[eid]
        if now - entry["created"] > ESTIMATE_TTL_S:
            Path(entry["file_path"]).unlink(missing_ok=True)
            _estimates.pop(eid, None)
```

- [ ] **Step 4: Rulează testele — trebuie să treacă**

Run: `python -m pytest tests/test_jobs.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/jobs.py backend/tests/test_jobs.py
git commit -m "feat: job store si estimate store partajate pentru mockup/scenarii"
```

---

### Task 3: Pachetizare `skills/mockup` + eliminare sys.path hack + fix mktemp

**Files:**
- Create: `backend/skills/__init__.py` (gol), `backend/skills/mockup/__init__.py` (gol)
- Modify: `backend/skills/mockup/parser.py:49`, `backend/skills/mockup/word_parser.py:4`, `backend/skills/mockup/word_writer.py:7-8`, `backend/skills/mockup/html_writer.py:2`, `backend/skills/mockup/image_writer.py:4`, `backend/skills/mockup/descriptions_builder.py:1`, `backend/pipelines/mockup_pipeline.py` (întreg)
- Test: `backend/tests/test_mockup_pipeline.py`

**Interfaces:**
- Consumes: nimic nou.
- Produces: importuri stabile `from skills.mockup.parser import parse_excel, ScreenSpec` etc.; `run_mockup_pipeline(input_path: Path) -> tuple[Path, str]` (semnătură neschimbată în acest task — devine async cu `use_ai` în Task 7).

- [ ] **Step 1: Scrie testul smoke (eșuează la import după refactor — îl scriem întâi pe starea țintă)**

```python
# backend/tests/test_mockup_pipeline.py
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
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_mockup_pipeline.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'skills.mockup'` (sau import error pe `parser`)

- [ ] **Step 3: Creează `__init__.py`-urile și schimbă importurile interne pe relative**

```bash
touch backend/skills/__init__.py backend/skills/mockup/__init__.py
```

Editări exacte (un import pe fișier):
- `parser.py` linia 49: `from config import MANDATORY_FILTERS` → `from .config import MANDATORY_FILTERS`
- `word_parser.py` linia 4: `from parser import ScreenSpec, Section, FilterField, ButtonDef, ColumnDef` → `from .parser import ScreenSpec, Section, FilterField, ButtonDef, ColumnDef`
- `word_writer.py` liniile 7-8: `from parser import ScreenSpec` → `from .parser import ScreenSpec`; `from image_writer import write_mockup_image` → `from .image_writer import write_mockup_image`
- `html_writer.py` linia 2: `from parser import ScreenSpec, Section` → `from .parser import ScreenSpec, Section`
- `image_writer.py` linia 4: `from parser import ScreenSpec, Section` → `from .parser import ScreenSpec, Section`
- `descriptions_builder.py` linia 1: `from parser import ScreenSpec` → `from .parser import ScreenSpec`

- [ ] **Step 4: Rescrie `backend/pipelines/mockup_pipeline.py` (fără sys.path, fără mktemp)**

```python
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
```

- [ ] **Step 5: Rulează toate testele backend — refactorul nu strică nimic**

Run: `python -m pytest tests/ -v`
Expected: toate testele pass (inclusiv cele 2 noi; `test_mockup_pipeline_smoke_docx` poate fi skipped dacă fișierul exemplu lipsește)

- [ ] **Step 6: Fix mktemp în scenarii (aceeași schemă)**

În `backend/pipelines/scenarii_pipeline.py`, adaugă `import os` la importuri și înlocuiește (linia 128):
```python
    output_path = Path(tempfile.mktemp(suffix=".xlsx"))
```
cu:
```python
    fd, tmp_name = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    output_path = Path(tmp_name)
```

- [ ] **Step 7: Rulează din nou testele + commit**

Run: `python -m pytest tests/ -v` — Expected: toate pass

```bash
git add backend/skills/__init__.py backend/skills/mockup/ backend/pipelines/mockup_pipeline.py backend/pipelines/scenarii_pipeline.py backend/tests/test_mockup_pipeline.py
git commit -m "refactor: pachetizare skills.mockup, eliminare sys.path hack si tempfile.mktemp"
```

---

### Task 4: Extracție v2 scenarii (headings + corp text) + estimare

**Files:**
- Modify: `backend/pipelines/scenarii_pipeline.py`
- Test: `backend/tests/test_scenarii_pipeline.py` (nou)

**Interfaces:**
- Consumes: `llm_client.estimate_tokens`, `llm_client.remaining_budget`.
- Produces: `_extract_structure(docx_path) -> dict[str, list[dict]]` unde fiecare capitol e `{"titlu": str, "text": list[str], "subcapitole": [{"titlu": str, "text": list[str]}]}`; `estimate_scenarii_job(docx_path: Path) -> dict` cu chei `est_tokens: int, modules: int, est_minutes: int, fits_budget: bool`; constante `CALL_OVERHEAD_TOKENS = 1200`, `OUT_TOKENS_PER_MODULE = 6000`.

- [ ] **Step 1: Scrie testele (eșuează)**

```python
# backend/tests/test_scenarii_pipeline.py
from pathlib import Path

import pytest
from docx import Document

import llm_client
from pipelines.scenarii_pipeline import (
    _extract_structure,
    estimate_scenarii_job,
)


@pytest.fixture
def spec_docx(tmp_path) -> Path:
    doc = Document()
    doc.add_heading("Modul Achizitii", level=1)
    doc.add_heading("Facturi furnizor", level=2)
    doc.add_paragraph("Utilizatorul introduce factura cu numar si data.")
    doc.add_paragraph("Sistemul valideaza duplicatele dupa numar si furnizor.")
    doc.add_heading("Receptie marfa", level=3)
    doc.add_paragraph("Receptia se face pe baza comenzii aprobate.")
    doc.add_heading("Modul Vanzari", level=1)
    doc.add_heading("Oferte", level=2)
    doc.add_paragraph("Oferta se transforma in comanda cu un click.")
    path = tmp_path / "spec.docx"
    doc.save(str(path))
    return path


def test_extract_structure_captures_body_text(spec_docx):
    structure = _extract_structure(spec_docx)
    assert set(structure) == {"Modul Achizitii", "Modul Vanzari"}

    cap = structure["Modul Achizitii"][0]
    assert cap["titlu"] == "Facturi furnizor"
    assert "Utilizatorul introduce factura cu numar si data." in cap["text"]
    assert "Sistemul valideaza duplicatele dupa numar si furnizor." in cap["text"]

    sub = cap["subcapitole"][0]
    assert sub["titlu"] == "Receptie marfa"
    assert sub["text"] == ["Receptia se face pe baza comenzii aprobate."]

    vanzari = structure["Modul Vanzari"][0]
    assert vanzari["text"] == ["Oferta se transforma in comanda cu un click."]


def test_estimate_scenarii_job(spec_docx, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "500000")
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0

    est = estimate_scenarii_job(spec_docx)
    assert est["modules"] == 2
    assert est["est_tokens"] > 2 * 7200  # overhead + output per modul
    assert est["est_minutes"] >= 1
    assert est["fits_budget"] is True


def test_estimate_scenarii_job_over_budget(spec_docx, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "100")
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0

    est = estimate_scenarii_job(spec_docx)
    assert est["fits_budget"] is False
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_scenarii_pipeline.py -v`
Expected: FAIL — `_extract_structure` nu reține `text` (KeyError/AssertionError) și `estimate_scenarii_job` nu există (ImportError)

- [ ] **Step 3: Extinde `_extract_structure` și adaugă `estimate_scenarii_job`**

În `backend/pipelines/scenarii_pipeline.py`, adaugă la importuri:

```python
import llm_client
```

Înlocuiește integral `_extract_structure` cu:

```python
def _extract_structure(docx_path: Path) -> dict[str, list[dict]]:
    """Extrage ierarhia de heading-uri + textul de corp, grupate pe secțiunea H1."""
    doc = Document(str(docx_path))
    modules: dict[str, list[dict]] = defaultdict(list)
    current_h1 = "General"
    current_cap: dict | None = None
    current_sub: dict | None = None

    for p in doc.paragraphs:
        style = p.style.name if p.style else ""
        text = p.text.strip()
        if not text:
            continue

        if re.match(r"Heading 1", style, re.I):
            current_h1 = text
            current_cap = None
            current_sub = None
        elif re.match(r"Heading 2", style, re.I):
            current_cap = {"titlu": text, "text": [], "subcapitole": []}
            current_sub = None
            modules[current_h1].append(current_cap)
        elif re.match(r"Heading [3-9]", style, re.I):
            current_sub = {"titlu": text, "text": []}
            if current_cap is not None:
                current_cap["subcapitole"].append(current_sub)
            else:
                current_cap = {"titlu": text, "text": [], "subcapitole": []}
                current_sub = None
                modules[current_h1].append(current_cap)
        else:
            # Paragraf de corp — se ataseaza celui mai specific heading curent
            if current_sub is not None:
                current_sub["text"].append(text)
            elif current_cap is not None:
                current_cap["text"].append(text)

    return dict(modules)
```

Adaugă după `_extract_structure`:

```python
CALL_OVERHEAD_TOKENS = 1200   # system prompt + structura JSON ceruta
OUT_TOKENS_PER_MODULE = 6000  # buget de raspuns per modul H1


def _structure_chars(structure: dict[str, list[dict]]) -> int:
    total = 0
    for modul, capitole in structure.items():
        total += len(modul)
        for cap in capitole:
            total += len(cap["titlu"]) + sum(len(t) for t in cap["text"])
            for sub in cap["subcapitole"]:
                total += len(sub["titlu"]) + sum(len(t) for t in sub["text"])
    return total


def estimate_scenarii_job(docx_path: Path) -> dict:
    """Pre-check: tokeni estimați, module și dacă încape în bugetul zilnic gratuit."""
    structure = _extract_structure(docx_path)
    modules = max(1, len(structure))
    input_tokens = llm_client.estimate_tokens(" " * _structure_chars(structure))
    est_tokens = input_tokens + modules * (CALL_OVERHEAD_TOKENS + OUT_TOKENS_PER_MODULE)
    return {
        "est_tokens": est_tokens,
        "modules": modules,
        "est_minutes": max(1, round(modules * 25 / 60)),
        "fits_budget": est_tokens <= llm_client.remaining_budget(),
    }
```

Actualizează și `run_scenarii_pipeline` pentru noul dict de capitol (cheia `subcapitole` există în ambele versiuni; nimic altceva nu se schimbă în acest task — bucla `for sub in subs: ... _stub(modul, cap["titlu"], sub["titlu"])` funcționează neschimbată).

- [ ] **Step 4: Rulează testele — trebuie să treacă**

Run: `python -m pytest tests/test_scenarii_pipeline.py tests/test_scenarii.py -v`
Expected: toate pass (stub-urile existente funcționează cu structura nouă)

- [ ] **Step 5: Commit**

```bash
git add backend/pipelines/scenarii_pipeline.py backend/tests/test_scenarii_pipeline.py
git commit -m "feat: extractie spec cu text de corp + estimare tokeni pentru scenarii"
```

---

### Task 5: Generare AI scenarii cu fallback per modul

**Files:**
- Modify: `backend/pipelines/scenarii_pipeline.py`
- Test: `backend/tests/test_scenarii_pipeline.py` (extins)

**Interfaces:**
- Consumes: `llm_client.chat`, `llm_client.parse_json`.
- Produces: `async run_scenarii_pipeline(docx_path: Path, use_ai: bool = False, on_step=None) -> tuple[Path, list[dict]]` — scenariile returnate au cele 11 câmpuri + `id: str` (TC-001...) + `ai: bool`; `on_step` e callable sincron primind `"module:i/n:<nume>"` sau `"building"`. Excel identic (12 coloane).

- [ ] **Step 1: Adaugă testele AI (eșuează)**

Adaugă în `backend/tests/test_scenarii_pipeline.py`:

```python
import json
from unittest.mock import AsyncMock, patch

import openpyxl

from pipelines.scenarii_pipeline import run_scenarii_pipeline

_AI_RESPONSE = json.dumps({
    "scenarii": [
        {
            "capitol": "Facturi furnizor",
            "subcapitol": "",
            "titlu_scenariu": "Introducere factura valida",
            "obiectiv": "Verifica introducerea unei facturi cu date complete.",
            "preconditii": "• Furnizor activ in nomenclator",
            "pasi": "1. Deschide ecranul Facturi\n2. Completeaza numar si data\n3. Salveaza",
            "rezultat_asteptat": "Factura este salvata si apare in lista.",
            "tip_test": "Funcțional - Pozitiv",
            "prioritate": "High",
            "dependente": "—",
            "observatii": "",
        },
        {
            "capitol": "Facturi furnizor",
            "subcapitol": "",
            "titlu_scenariu": "Factura duplicata este respinsa",
            "obiectiv": "Verifica validarea duplicatelor.",
            "preconditii": "• O factura cu acelasi numar exista deja",
            "pasi": "1. Introdu factura cu numar existent\n2. Salveaza",
            "rezultat_asteptat": "Sistemul respinge salvarea cu mesaj de duplicat.",
            "tip_test": "Funcțional - Negativ",
            "prioritate": "High",
            "dependente": "—",
            "observatii": "",
        },
    ]
})


async def test_run_pipeline_ai_generates_from_llm(spec_docx):
    steps: list[str] = []
    with patch("pipelines.scenarii_pipeline.llm_client.chat", new=AsyncMock(return_value=_AI_RESPONSE)) as mock_chat:
        xlsx_path, scenarios = await run_scenarii_pipeline(spec_docx, use_ai=True, on_step=steps.append)
    try:
        assert mock_chat.await_count == 2  # un apel per modul H1
        # 2 module x 2 scenarii din mock
        assert len(scenarios) == 4
        assert scenarios[0]["id"] == "TC-001"
        assert scenarios[0]["ai"] is True
        assert scenarios[0]["titlu_scenariu"] == "Introducere factura valida"
        assert any(s.startswith("module:1/2:") for s in steps)
        assert "building" in steps

        wb = openpyxl.load_workbook(str(xlsx_path))
        ws = wb["Scenarii"]
        assert ws.cell(row=1, column=1).value == "ID"
        assert ws.cell(row=2, column=1).value == "TC-001"
        assert ws.cell(row=2, column=4).value == "Introducere factura valida"
        assert ws.max_column == 12
    finally:
        xlsx_path.unlink(missing_ok=True)


async def test_run_pipeline_ai_falls_back_per_module(spec_docx):
    async def flaky(system, user, **kwargs):
        # primul modul reuseste, al doilea pica
        if "Achizitii" in user:
            return _AI_RESPONSE
        raise RuntimeError("Eroare LLM (429)")

    with patch("pipelines.scenarii_pipeline.llm_client.chat", side_effect=flaky):
        xlsx_path, scenarios = await run_scenarii_pipeline(spec_docx, use_ai=True)
    try:
        ai_rows = [s for s in scenarios if s["ai"]]
        stub_rows = [s for s in scenarios if not s["ai"]]
        assert len(ai_rows) == 2
        assert len(stub_rows) >= 1
        assert all("fără AI" in s["observatii"] for s in stub_rows)
    finally:
        xlsx_path.unlink(missing_ok=True)


async def test_run_pipeline_without_ai_keeps_stub_behavior(spec_docx):
    xlsx_path, scenarios = await run_scenarii_pipeline(spec_docx, use_ai=False)
    try:
        assert all(s["ai"] is False for s in scenarios)
        assert scenarios[0]["id"] == "TC-001"
        assert scenarios[0]["titlu_scenariu"].startswith("Verificare:")
    finally:
        xlsx_path.unlink(missing_ok=True)
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_scenarii_pipeline.py -v`
Expected: FAIL — `run_scenarii_pipeline` nu e async și nu acceptă `use_ai`/`on_step` (TypeError)

- [ ] **Step 3: Implementează generarea AI + fallback**

În `backend/pipelines/scenarii_pipeline.py`, adaugă la importuri:

```python
from pydantic import BaseModel
```

Adaugă după `estimate_scenarii_job`:

```python
class _Scenariu(BaseModel):
    capitol: str = ""
    subcapitol: str = ""
    titlu_scenariu: str
    obiectiv: str = ""
    preconditii: str = ""
    pasi: str = ""
    rezultat_asteptat: str = ""
    tip_test: str = "Funcțional - Pozitiv"
    prioritate: str = "High"
    dependente: str = "—"
    observatii: str = ""


_SYSTEM_PROMPT = """Ești inginer QA senior pentru aplicații ERP (Charisma). Primești un fragment \
de specificație funcțională în limba română, structurat pe capitole și subcapitole.
Generează scenarii de testare concrete, STRICT pe baza textului primit — nu inventa funcționalități.
Pentru fiecare capitol/subcapitol: cazul pozitiv principal și, unde textul menționează validări, \
restricții sau reguli, câte un caz negativ.
Scrie în română, cu diacritice. Pașii sunt numerotați, precondițiile cu bullet •.
Răspunde DOAR cu JSON valid, fără alt text:
{"scenarii": [{"capitol": "...", "subcapitol": "...", "titlu_scenariu": "...", "obiectiv": "...", \
"preconditii": "• ...", "pasi": "1. ...\\n2. ...", "rezultat_asteptat": "...", \
"tip_test": "Funcțional - Pozitiv" sau "Funcțional - Negativ", \
"prioritate": "Critical"|"High"|"Medium"|"Low", "dependente": "...", "observatii": "..."}]}"""


def _module_prompt(modul: str, capitole: list[dict]) -> str:
    lines = [f"MODUL: {modul}", ""]
    for cap in capitole:
        lines.append(f"CAPITOL: {cap['titlu']}")
        lines.extend(cap["text"])
        for sub in cap["subcapitole"]:
            lines.append(f"SUBCAPITOL: {sub['titlu']}")
            lines.extend(sub["text"])
        lines.append("")
    return "\n".join(lines)


def _module_stubs(modul: str, capitole: list[dict], nota: str = "") -> list[dict]:
    stubs: list[dict] = []
    for cap in capitole:
        subs = cap.get("subcapitole", [])
        if subs:
            for sub in subs:
                stubs.append(_stub(modul, cap["titlu"], sub["titlu"]))
        else:
            stubs.append(_stub(modul, cap["titlu"], ""))
    if nota:
        for s in stubs:
            s["observatii"] = nota
    return stubs


async def _generate_module_ai(modul: str, capitole: list[dict]) -> list[dict]:
    content = await llm_client.chat(
        _SYSTEM_PROMPT, _module_prompt(modul, capitole), max_tokens=OUT_TOKENS_PER_MODULE
    )
    data = llm_client.parse_json(content)
    items = data.get("scenarii", [])
    if not items:
        raise ValueError("Răspuns AI fără scenarii")
    return [_Scenariu(**s).model_dump() for s in items]
```

Înlocuiește integral `run_scenarii_pipeline` cu:

```python
def _write_excel(scenarios: list[dict]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Scenarii"

    headers = [
        "ID", "Capitol", "Subcapitol", "Titlu Scenariu",
        "Obiectiv", "Precondiții", "Pași de Execuție", "Rezultat Așteptat",
        "Tip Test", "Prioritate", "Dependente", "Observații",
    ]
    header_fill = PatternFill(fill_type="solid", fgColor="1F3864")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    wrap = Alignment(wrap_text=True, vertical="top")
    for i, s in enumerate(scenarios, start=1):
        ws.append([
            s["id"],
            s["capitol"],
            s["subcapitol"],
            s["titlu_scenariu"],
            s["obiectiv"],
            s["preconditii"],
            s["pasi"],
            s["rezultat_asteptat"],
            s["tip_test"],
            s["prioritate"],
            s["dependente"],
            s["observatii"],
        ])
        for col_idx in range(1, 13):
            ws.cell(row=i + 1, column=col_idx).alignment = wrap

    col_widths = [10, 25, 25, 35, 35, 30, 40, 35, 20, 12, 15, 20]
    for col_idx, width in enumerate(col_widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

    ws.freeze_panes = "B2"

    fd, tmp_name = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    output_path = Path(tmp_name)
    wb.save(str(output_path))
    return output_path


async def run_scenarii_pipeline(
    docx_path: Path,
    use_ai: bool = False,
    on_step=None,
) -> tuple[Path, list[dict]]:
    """DOCX spec → Excel cu scenarii de testare. Returns (xlsx_path, scenarios).

    use_ai=True: un apel Mistral per modul H1, cu fallback la stub-uri per modul.
    use_ai=False: stub-urile deterministe de azi (plan B garantat).
    """
    structure = _extract_structure(docx_path)

    scenarios: list[dict] = []
    module_items = list(structure.items())
    for idx, (modul, capitole) in enumerate(module_items, start=1):
        if on_step:
            on_step(f"module:{idx}/{len(module_items)}:{modul}")
        if use_ai:
            try:
                generated = await _generate_module_ai(modul, capitole)
                for s in generated:
                    s["ai"] = True
                scenarios.extend(generated)
                continue
            except Exception:
                fallback = _module_stubs(modul, capitole, nota="Generat fără AI (fallback — apelul AI a eșuat)")
                for s in fallback:
                    s["ai"] = False
                scenarios.extend(fallback)
                continue
        stubs = _module_stubs(modul, capitole)
        for s in stubs:
            s["ai"] = False
        scenarios.extend(stubs)

    if not scenarios:
        empty = {
            "capitol": "General",
            "subcapitol": "",
            "titlu_scenariu": "Verificare generală",
            "obiectiv": "Verifică funcționalitățile generale din specificație.",
            "preconditii": "• Utilizator autentificat",
            "pasi": "1. Navigare la funcționalitate\n2. Execuție flux\n3. Validare",
            "rezultat_asteptat": "Funcționare conform specificației.",
            "tip_test": "Funcțional - Pozitiv",
            "prioritate": "High",
            "dependente": "—",
            "observatii": "Nicio structură de headings detectată în document.",
            "ai": False,
        }
        scenarios.append(empty)

    for i, s in enumerate(scenarios, start=1):
        s["id"] = f"TC-{i:03d}"

    if on_step:
        on_step("building")
    return _write_excel(scenarios), scenarios
```

(Bucla veche de stub-uri și blocul `if not scenarios` vechi se șterg — sunt înlocuite de cele de mai sus. `_stub` rămâne neschimbat.)

- [ ] **Step 4: Rulează testele — trebuie să treacă**

Run: `python -m pytest tests/test_scenarii_pipeline.py -v`
Expected: toate pass (inclusiv cele 3 noi)

- [ ] **Step 5: Commit**

```bash
git add backend/pipelines/scenarii_pipeline.py backend/tests/test_scenarii_pipeline.py
git commit -m "feat: generare scenarii cu Mistral din textul spec-ului, fallback per modul"
```

---

### Task 6: Router scenarii v2 (estimate/generate/job)

**Files:**
- Modify: `backend/routers/scenarii.py` (rescriere completă)
- Test: `backend/tests/test_scenarii.py` (rescriere completă)

**Interfaces:**
- Consumes: `jobs.create_job/set_step/finish/fail/get_job/save_estimate/pop_estimate`, `estimate_scenarii_job`, `run_scenarii_pipeline`, `upload_file`.
- Produces (contract HTTP):
  - `POST /api/scenarii/estimate` (multipart file) → `{estimate_id, est_tokens, modules, est_minutes, fits_budget}`
  - `POST /api/scenarii/generate` (JSON `{estimate_id: str, use_ai: bool}`) → `{job_id}`; 404 dacă estimarea a expirat; 422 dacă `use_ai=true` și `fits_budget=false`
  - `GET /api/scenarii/job/{job_id}` → `{status, step?, filename?, xlsx_b64?, scenarios?, ai_used?, storage_path?, error?}`
  - Endpoint-ul vechi `POST /api/scenarii` se elimină (frontend-ul e rescris în Task 10).

- [ ] **Step 1: Rescrie testele (eșuează)**

```python
# backend/tests/test_scenarii.py
import io
from unittest.mock import AsyncMock, patch

from docx import Document

from main import app
from auth import verify_token


def _spec_bytes() -> bytes:
    doc = Document()
    doc.add_heading("Modul Test", level=1)
    doc.add_heading("Capitol Unu", level=2)
    doc.add_paragraph("Descriere functionalitate.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def test_estimate_without_auth_returns_401(client):
    response = await client.post(
        "/api/scenarii/estimate",
        files={"file": ("spec.docx", _spec_bytes(), _DOCX_MIME)},
    )
    assert response.status_code == 401


async def test_estimate_wrong_format_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/scenarii/estimate",
            files={"file": ("spec.pdf", b"pdf", "application/pdf")},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


async def test_estimate_then_generate_then_job_done(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        est_res = await client.post(
            "/api/scenarii/estimate",
            files={"file": ("spec.docx", _spec_bytes(), _DOCX_MIME)},
            headers={"Authorization": "Bearer fake"},
        )
        assert est_res.status_code == 200
        est = est_res.json()
        assert est["modules"] == 1
        assert "estimate_id" in est

        with patch("routers.scenarii.upload_file", return_value="scenarii/x.xlsx"):
            gen_res = await client.post(
                "/api/scenarii/generate",
                json={"estimate_id": est["estimate_id"], "use_ai": False},
                headers={"Authorization": "Bearer fake"},
            )
        assert gen_res.status_code == 200
        job_id = gen_res.json()["job_id"]

        job_res = await client.get(
            f"/api/scenarii/job/{job_id}",
            headers={"Authorization": "Bearer fake"},
        )
        assert job_res.status_code == 200
        job = job_res.json()
        assert job["status"] == "done"
        assert job["ai_used"] is False
        assert job["filename"].endswith(".xlsx")
        assert len(job["scenarios"]) >= 1
        assert job["xlsx_b64"]
    finally:
        app.dependency_overrides.clear()


async def test_generate_with_expired_estimate_returns_404(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/scenarii/generate",
            json={"estimate_id": "inexistent", "use_ai": False},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


async def test_generate_ai_over_budget_returns_422(client, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "10")
    import llm_client
    llm_client._usage["day"] = ""
    llm_client._usage["tokens"] = 0

    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        est_res = await client.post(
            "/api/scenarii/estimate",
            files={"file": ("spec.docx", _spec_bytes(), _DOCX_MIME)},
            headers={"Authorization": "Bearer fake"},
        )
        est = est_res.json()
        assert est["fits_budget"] is False

        response = await client.post(
            "/api/scenarii/generate",
            json={"estimate_id": est["estimate_id"], "use_ai": True},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "buget" in response.json()["detail"].lower() or "cota" in response.json()["detail"].lower()


async def test_job_not_found_returns_404(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.get(
            "/api/scenarii/job/nu-exista",
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_scenarii.py -v`
Expected: FAIL cu 404 pe rutele noi (nu există încă)

- [ ] **Step 3: Rescrie `backend/routers/scenarii.py`**

```python
import base64
import logging
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

import jobs
from auth import verify_token
from pipelines.scenarii_pipeline import estimate_scenarii_job, run_scenarii_pipeline
from storage import upload_file

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateRequest(BaseModel):
    estimate_id: str
    use_ai: bool = True


@router.post("/scenarii/estimate")
async def estimate_scenarii(
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    """Pas 1: încarcă spec-ul, întoarce estimarea de tokeni. Fișierul se păstrează ~10 min."""
    filename_raw = file.filename or ""
    if Path(filename_raw).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .docx")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(await file.read())
        input_path = Path(tmp.name)

    try:
        est = estimate_scenarii_job(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Fișier .docx invalid: {e}")

    estimate_id = jobs.save_estimate(input_path, filename_raw, est)
    return {"estimate_id": estimate_id, **est}


async def _run_job(job_id: str, input_path: Path, orig_filename: str, use_ai: bool) -> None:
    def _on_step(step: str) -> None:
        jobs.set_step(job_id, step)

    try:
        xlsx_path, scenarios = await run_scenarii_pipeline(input_path, use_ai=use_ai, on_step=_on_step)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Scenarii_{Path(orig_filename).stem}_{timestamp}.xlsx"
        job = jobs.get_job(job_id) or {}
        storage_path = upload_file(
            xlsx_path, tool="scenarii", filename=filename,
            user_email=job.get("user_email", "anonymous"),
        )
        with open(xlsx_path, "rb") as f:
            xlsx_b64 = base64.b64encode(f.read()).decode()
        ai_used = use_ai and any(s.get("ai") for s in scenarios)
        jobs.finish(
            job_id,
            filename=filename,
            xlsx_b64=xlsx_b64,
            scenarios=scenarios,
            ai_used=ai_used,
            storage_path=storage_path,
        )
        xlsx_path.unlink(missing_ok=True)
    except Exception as e:
        logger.error("scenarii job %s FAILED: %s\n%s", job_id, e, traceback.format_exc())
        jobs.fail(job_id, str(e) or type(e).__name__)
    finally:
        input_path.unlink(missing_ok=True)


@router.post("/scenarii/generate")
async def generate_scenarii(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    user=Depends(verify_token),
):
    """Pas 2: pornește generarea (cu sau fără AI) pe fișierul din estimare."""
    est = jobs.pop_estimate(req.estimate_id)
    if est is None:
        raise HTTPException(
            status_code=404,
            detail="Estimarea a expirat sau serverul a fost repornit — reîncarcă fișierul.",
        )
    if req.use_ai and not est.get("fits_budget", False):
        Path(est["file_path"]).unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail="Bugetul zilnic gratuit de tokeni nu ajunge pentru acest fișier. "
                   "Continuă fără AI sau revino mâine.",
        )

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email)
    background_tasks.add_task(_run_job, job_id, Path(est["file_path"]), est["filename"], req.use_ai)
    return {"job_id": job_id}


@router.get("/scenarii/job/{job_id}")
async def get_scenarii_job(job_id: str, user=Depends(verify_token)):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
```

- [ ] **Step 4: Rulează testele — trebuie să treacă**

Run: `python -m pytest tests/test_scenarii.py tests/test_scenarii_pipeline.py -v`
Expected: toate pass. Notă: cu `ASGITransport`, BackgroundTasks rulează înainte ca răspunsul să revină în test — jobul e `done` la primul GET.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/scenarii.py backend/tests/test_scenarii.py
git commit -m "feat: contract async estimate/generate/job pentru scenarii"
```

---

### Task 7: Îmbogățire AI mockup (`ai_enricher.py`) + overview în Word/HTML + pipeline async

**Files:**
- Create: `backend/skills/mockup/ai_enricher.py`
- Modify: `backend/skills/mockup/word_writer.py` (secțiune overview), `backend/skills/mockup/html_writer.py` (parametru `overview`), `backend/pipelines/mockup_pipeline.py` (async + `use_ai`)
- Test: `backend/tests/test_mockup_pipeline.py` (extins)

**Interfaces:**
- Consumes: `llm_client.chat`, `llm_client.parse_json`, `llm_client.estimate_tokens`.
- Produces: `ai_enricher.estimate_enrich_tokens(spec, descriptions) -> int`; `async ai_enricher.enrich(spec, descriptions) -> dict` (descriptions + cheia `prezentare_generala: {"scop": str, "flux": list[str], "legaturi": str}`); `estimate_mockup_job(input_path: Path) -> dict` cu `est_tokens, est_minutes, fits_budget`; `async run_mockup_pipeline(input_path: Path, use_ai: bool = False, on_step=None) -> tuple[Path, str, bool]` (al 3-lea element = `ai_used`); `write_html(spec, output_path, overview: dict | None = None)`.

- [ ] **Step 1: Extinde testele (eșuează)**

Adaugă în `backend/tests/test_mockup_pipeline.py`:

```python
import json
from unittest.mock import AsyncMock, patch

from docx import Document as WordDocument

from pipelines.mockup_pipeline import estimate_mockup_job
from skills.mockup import ai_enricher
from skills.mockup.parser import ScreenSpec, Section, FilterField

_ENRICH_RESPONSE = json.dumps({
    "prezentare_generala": {
        "scop": "Ecranul permite generarea consumului de motorină.",
        "flux": ["Selectează gestiunea", "Filtrează alimentările", "Generează bonul"],
        "legaturi": "Câmpul Data controlează intrările vizibile.",
    },
    "descrieri_filtre": {"Data": "Data de referință pentru calculul stocului FIFO."},
    "descrieri_butoane": {},
    "descrieri_coloane": {},
})


def _mini_spec() -> tuple[ScreenSpec, dict]:
    sec = Section(title="Test", filter_fields=[FilterField(label="Data", mandatory=True)])
    spec = ScreenSpec(screen_title="Ecran Test", source_file="t.xlsx", sections=[sec])
    descriptions = {
        "descriere_generala": "Ecran de test.",
        "reguli_business": [],
        "descrieri_filtre": {"Data": "Data raport."},
        "descrieri_butoane": {},
        "descrieri_coloane": {},
        "mod_de_lucru": [],
    }
    return spec, descriptions


async def test_enrich_merges_overview_and_descriptions():
    spec, descriptions = _mini_spec()
    with patch("skills.mockup.ai_enricher.llm_client.chat", new=AsyncMock(return_value=_ENRICH_RESPONSE)):
        merged = await ai_enricher.enrich(spec, descriptions)
    assert merged["prezentare_generala"]["scop"].startswith("Ecranul permite")
    assert merged["descrieri_filtre"]["Data"] == "Data de referință pentru calculul stocului FIFO."
    # cheile existente raman
    assert merged["descriere_generala"] == "Ecran de test."


async def test_enrich_ignores_unknown_fields():
    spec, descriptions = _mini_spec()
    response = json.dumps({
        "prezentare_generala": {"scop": "x", "flux": [], "legaturi": ""},
        "descrieri_filtre": {"CampInexistent": "nu trebuie sa apara"},
    })
    with patch("skills.mockup.ai_enricher.llm_client.chat", new=AsyncMock(return_value=response)):
        merged = await ai_enricher.enrich(spec, descriptions)
    assert "CampInexistent" not in merged["descrieri_filtre"]


@pytest.mark.skipif(not SAMPLE.exists(), reason="fișierul exemplu lipsește local")
async def test_pipeline_with_ai_failure_falls_back_deterministic():
    with patch(
        "pipelines.mockup_pipeline.ai_enricher.enrich",
        new=AsyncMock(side_effect=RuntimeError("LLM down")),
    ):
        docx_path, html, ai_used = await run_mockup_pipeline(SAMPLE, use_ai=True)
    try:
        assert ai_used is False
        assert docx_path.exists()
    finally:
        docx_path.unlink(missing_ok=True)


@pytest.mark.skipif(not SAMPLE.exists(), reason="fișierul exemplu lipsește local")
def test_estimate_mockup_job_returns_budget_info():
    est = estimate_mockup_job(SAMPLE)
    assert est["est_tokens"] > 0
    assert est["est_minutes"] == 1
    assert isinstance(est["fits_budget"], bool)
```

Și actualizează testul smoke existent la noua semnătură async cu 3 elemente:

```python
@pytest.mark.skipif(not SAMPLE.exists(), reason="fișierul exemplu lipsește local")
async def test_mockup_pipeline_smoke_docx():
    docx_path, html, ai_used = await run_mockup_pipeline(SAMPLE)
    try:
        assert docx_path.exists()
        assert docx_path.suffix == ".docx"
        assert "<html" in html.lower()
        assert ai_used is False
    finally:
        docx_path.unlink(missing_ok=True)
```

Și testul de extensie greșită devine async:

```python
async def test_unsupported_extension_raises(tmp_path):
    bad = tmp_path / "spec.pdf"
    bad.write_bytes(b"%PDF")
    with pytest.raises(ValueError, match="Format nesuportat"):
        await run_mockup_pipeline(bad)
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_mockup_pipeline.py -v`
Expected: ImportError pe `ai_enricher` / `estimate_mockup_job`, TypeError pe semnătura async

- [ ] **Step 3: Creează `backend/skills/mockup/ai_enricher.py`**

```python
"""Imbogatire AI a documentatiei de ecran: overview + descrieri mai bune.

Un singur apel LLM per mockup. Orice esec => se pastreaza descrierile
deterministe (apelantul decide fallback-ul).
"""
import llm_client
from .parser import ScreenSpec

OUT_TOKENS = 3000
CALL_OVERHEAD_TOKENS = 900

_SYSTEM = """Ești analist de business senior pentru Charisma ERP. Primești structura unui ecran \
(filtre, butoane, coloane, observații) și descrierile existente ale câmpurilor.
1. Scrie secțiunea "Prezentare generală": scopul ecranului (2-3 fraze), fluxul de utilizare \
(3-6 pași scurți) și legăturile dintre câmpuri (dacă există).
2. Îmbunătățește descrierile câmpurilor: mai clare, cu context business și tehnic, în română cu diacritice. \
Păstrează faptele din descrierile existente — NU inventa reguli noi.
Răspunde DOAR cu JSON valid:
{"prezentare_generala": {"scop": "...", "flux": ["...", "..."], "legaturi": "..."}, \
"descrieri_filtre": {"<câmp>": "..."}, "descrieri_butoane": {"<buton>": "..."}, \
"descrieri_coloane": {"<coloană>": "..."}}"""


def _spec_digest(spec: ScreenSpec, descriptions: dict) -> str:
    lines = [f"ECRAN: {spec.screen_title}", ""]
    for sec in spec.sections:
        lines.append(f"SECȚIUNE: {sec.title}")
        if sec.filter_fields:
            lines.append("FILTRE:")
            for f in sec.filter_fields:
                desc = descriptions.get("descrieri_filtre", {}).get(f.label, "")
                oblig = " (obligatoriu)" if f.mandatory else ""
                lines.append(f"- {f.label}{oblig}: {desc}")
        if sec.buttons:
            lines.append("BUTOANE:")
            for b in sec.buttons:
                desc = descriptions.get("descrieri_butoane", {}).get(b.label, "")
                lines.append(f"- {b.label} [{b.group}]: {desc}")
        if sec.columns:
            lines.append("COLOANE GRID:")
            for c in sec.columns:
                desc = descriptions.get("descrieri_coloane", {}).get(c.name, "")
                lines.append(f"- {c.name}: {desc}")
        lines.append("")
    if spec.observatii:
        lines.append("OBSERVAȚII DIN SPEC:")
        lines.extend(f"- {o}" for o in spec.observatii[:30])
    if descriptions.get("descriere_generala"):
        lines.append(f"DESCRIERE EXISTENTĂ: {descriptions['descriere_generala']}")
    return "\n".join(lines)


def estimate_enrich_tokens(spec: ScreenSpec, descriptions: dict) -> int:
    return (
        llm_client.estimate_tokens(_spec_digest(spec, descriptions))
        + CALL_OVERHEAD_TOKENS
        + OUT_TOKENS
    )


async def enrich(spec: ScreenSpec, descriptions: dict) -> dict:
    """Returneaza un dict descriptions nou, cu prezentare_generala + descrieri imbunatatite."""
    content = await llm_client.chat(_SYSTEM, _spec_digest(spec, descriptions), max_tokens=OUT_TOKENS)
    data = llm_client.parse_json(content)

    merged = dict(descriptions)
    pg = data.get("prezentare_generala")
    if isinstance(pg, dict):
        merged["prezentare_generala"] = {
            "scop": str(pg.get("scop", "")),
            "flux": [str(x) for x in pg.get("flux", []) if str(x).strip()],
            "legaturi": str(pg.get("legaturi", "")),
        }
    for key in ("descrieri_filtre", "descrieri_butoane", "descrieri_coloane"):
        overrides = data.get(key)
        if isinstance(overrides, dict):
            base = dict(merged.get(key, {}))
            for label, text in overrides.items():
                # doar campuri care exista deja (AI nu poate adauga campuri noi)
                if label in base and isinstance(text, str) and text.strip():
                    base[label] = text.strip()
            merged[key] = base
    return merged
```

- [ ] **Step 4: Adaugă secțiunea overview în `word_writer.py`**

În `write_word`, imediat după blocul cu imaginea (după linia `doc.add_paragraph()` de la linia 49), inserează:

```python
    overview = descriptions.get("prezentare_generala")
    if overview:
        doc.add_heading("Prezentare Generală", 2)
        if overview.get("scop"):
            doc.add_paragraph(overview["scop"])
        for step in overview.get("flux", []):
            doc.add_paragraph(step, style="List Number")
        if overview.get("legaturi"):
            doc.add_paragraph(overview["legaturi"])
```

- [ ] **Step 5: Adaugă parametrul `overview` în `html_writer.write_html`**

Înlocuiește funcția `write_html` cu:

```python
def _render_overview(overview: dict) -> str:
    flux = "".join(f"<li>{s}</li>" for s in overview.get("flux", []))
    legaturi = overview.get("legaturi", "")
    return (
        '<div style="max-width:1100px;background:#eef4fb;border:1px solid #b8cfe4;'
        'border-radius:4px;padding:10px 14px;margin-bottom:10px;font-size:12px">'
        f'<div style="font-weight:bold;color:#1a3a5c;margin-bottom:6px">Prezentare generală</div>'
        f'<p style="margin:0 0 6px 0">{overview.get("scop", "")}</p>'
        + (f"<ol style='margin:0 0 6px 18px;padding:0'>{flux}</ol>" if flux else "")
        + (f'<p style="margin:0;font-style:italic">{legaturi}</p>' if legaturi else "")
        + "</div>"
    )


def write_html(spec: ScreenSpec, output_path: Path, overview: dict | None = None):
    if not spec.sections:
        return
    overview_html = _render_overview(overview) if overview else ""
    html = (
        f'<!DOCTYPE html>\n<html lang="ro">\n<head>\n'
        f'<meta charset="UTF-8"/>\n'
        f"<title>{spec.screen_title} — Charisma ERP Mockup</title>\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n"
        + overview_html
        + _render_body(spec, compact=False)
        + "\n</body>\n</html>"
    )
    output_path.write_text(html, encoding="utf-8")
```

- [ ] **Step 6: Fă pipeline-ul async cu `use_ai` și `estimate_mockup_job`**

Rescrie `backend/pipelines/mockup_pipeline.py` (păstrând `_mktemp_path` și `_load_spec` din Task 3):

```python
import os
import tempfile
from pathlib import Path

import llm_client
from skills.mockup import ai_enricher
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


def estimate_mockup_job(input_path: Path) -> dict:
    """Pre-check: tokeni necesari pentru imbogatirea AI a acestui ecran."""
    spec, descriptions = _load_spec(input_path)
    est_tokens = ai_enricher.estimate_enrich_tokens(spec, descriptions)
    return {
        "est_tokens": est_tokens,
        "est_minutes": 1,
        "fits_budget": est_tokens <= llm_client.remaining_budget(),
    }


async def run_mockup_pipeline(
    input_path: Path,
    use_ai: bool = False,
    on_step=None,
) -> tuple[Path, str, bool]:
    """Returns (docx_path, html_content, ai_used). Accepts .xlsx or .docx."""
    if on_step:
        on_step("parsing")
    spec, descriptions = _load_spec(input_path)

    ai_used = False
    if use_ai:
        if on_step:
            on_step("ai")
        try:
            descriptions = await ai_enricher.enrich(spec, descriptions)
            ai_used = True
        except Exception:
            ai_used = False  # fallback silentios la varianta determinista

    if on_step:
        on_step("building")
    overview = descriptions.get("prezentare_generala")

    html_path = _mktemp_path(".html")
    write_html(spec, html_path, overview=overview)
    html = html_path.read_text(encoding="utf-8") if html_path.stat().st_size else ""
    html_path.unlink()

    docx_path = _mktemp_path(".docx")
    write_word(spec, descriptions, docx_path)
    return docx_path, html, ai_used
```

- [ ] **Step 7: Rulează testele — trebuie să treacă**

Run: `python -m pytest tests/test_mockup_pipeline.py -v`
Expected: toate pass (2 pot fi skipped fără fișierul exemplu). Notă: `tests/test_mockup.py` (routerul vechi) încă trece — routerul se rescrie în Task 8.

Atenție: routerul vechi `routers/mockup.py` apelează acum o funcție async fără await — NU rula aplicația între Task 7 și Task 8; testele de router vechi verifică doar 401/422 (nu ating pipeline-ul), deci rămân verzi.

- [ ] **Step 8: Commit**

```bash
git add backend/skills/mockup/ai_enricher.py backend/skills/mockup/word_writer.py backend/skills/mockup/html_writer.py backend/pipelines/mockup_pipeline.py backend/tests/test_mockup_pipeline.py
git commit -m "feat: imbogatire AI mockup (prezentare generala + descrieri) cu fallback determinist"
```

---

### Task 8: Router mockup v2 (estimate/generate/job)

**Files:**
- Modify: `backend/routers/mockup.py` (rescriere completă)
- Test: `backend/tests/test_mockup.py` (rescriere completă)

**Interfaces:**
- Consumes: `jobs.*`, `estimate_mockup_job`, `run_mockup_pipeline`, `upload_file`.
- Produces (contract HTTP):
  - `POST /api/mockup/estimate` (multipart, `.xlsx`/`.docx`) → `{estimate_id, est_tokens, est_minutes, fits_budget}`
  - `POST /api/mockup/generate` (JSON `{estimate_id, use_ai}`) → `{job_id}`; 404 estimare expirată; 422 peste buget cu `use_ai=true`
  - `GET /api/mockup/job/{job_id}` → `{status, step?, filename?, docx_b64?, html?, ai_used?, storage_path?, error?}`

- [ ] **Step 1: Rescrie testele (eșuează)**

```python
# backend/tests/test_mockup.py
from pathlib import Path
from unittest.mock import AsyncMock, patch

from main import app
from auth import verify_token

SAMPLE = (
    Path(__file__).parent.parent
    / "skills" / "mockup" / "input"
    / "Ecran generare consum de motorina pe baza de alimentari.docx"
)
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def test_estimate_without_auth_returns_401(client):
    response = await client.post(
        "/api/mockup/estimate",
        files={"file": ("t.xlsx", b"PK...", "application/octet-stream")},
    )
    assert response.status_code == 401


async def test_estimate_wrong_format_returns_422(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/mockup/estimate",
            files={"file": ("t.pdf", b"pdf", "application/pdf")},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


async def test_generate_with_expired_estimate_returns_404(client):
    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        response = await client.post(
            "/api/mockup/generate",
            json={"estimate_id": "inexistent", "use_ai": False},
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


async def test_estimate_then_generate_then_job_done(client):
    import pytest
    if not SAMPLE.exists():
        pytest.skip("fișierul exemplu lipsește local")

    app.dependency_overrides[verify_token] = lambda: {"id": "u1"}
    try:
        est_res = await client.post(
            "/api/mockup/estimate",
            files={"file": (SAMPLE.name, SAMPLE.read_bytes(), _DOCX_MIME)},
            headers={"Authorization": "Bearer fake"},
        )
        assert est_res.status_code == 200
        est = est_res.json()
        assert est["est_tokens"] > 0

        with patch("routers.mockup.upload_file", return_value="mockup/x.docx"):
            gen_res = await client.post(
                "/api/mockup/generate",
                json={"estimate_id": est["estimate_id"], "use_ai": False},
                headers={"Authorization": "Bearer fake"},
            )
        assert gen_res.status_code == 200
        job_id = gen_res.json()["job_id"]

        job_res = await client.get(
            f"/api/mockup/job/{job_id}",
            headers={"Authorization": "Bearer fake"},
        )
        job = job_res.json()
        assert job["status"] == "done"
        assert job["ai_used"] is False
        assert job["filename"].endswith(".docx")
        assert job["docx_b64"]
        assert "<html" in job["html"].lower()
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `python -m pytest tests/test_mockup.py -v`
Expected: FAIL cu 404 pe rutele noi

- [ ] **Step 3: Rescrie `backend/routers/mockup.py`**

```python
import base64
import logging
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

import jobs
from auth import verify_token
from pipelines.mockup_pipeline import estimate_mockup_job, run_mockup_pipeline
from storage import upload_file

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".docx"}


class GenerateRequest(BaseModel):
    estimate_id: str
    use_ai: bool = True


@router.post("/mockup/estimate")
async def estimate_mockup(
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    """Pas 1: încarcă fișierul, întoarce estimarea de tokeni. Fișierul se păstrează ~10 min."""
    filename_raw = file.filename or ""
    ext = Path(filename_raw).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Fișierul trebuie să fie .xlsx sau .docx")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(await file.read())
        input_path = Path(tmp.name)

    try:
        est = estimate_mockup_job(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Fișier invalid: {e}")

    estimate_id = jobs.save_estimate(input_path, filename_raw, est)
    return {"estimate_id": estimate_id, **est}


async def _run_job(job_id: str, input_path: Path, orig_filename: str, use_ai: bool) -> None:
    def _on_step(step: str) -> None:
        jobs.set_step(job_id, step)

    try:
        docx_path, html, ai_used = await run_mockup_pipeline(input_path, use_ai=use_ai, on_step=_on_step)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{Path(orig_filename).stem}_{timestamp}.docx"
        job = jobs.get_job(job_id) or {}
        storage_path = upload_file(
            docx_path, tool="mockup", filename=filename,
            user_email=job.get("user_email", "anonymous"),
        )
        with open(docx_path, "rb") as f:
            docx_b64 = base64.b64encode(f.read()).decode()
        jobs.finish(
            job_id,
            filename=filename,
            docx_b64=docx_b64,
            html=html,
            ai_used=ai_used,
            storage_path=storage_path,
        )
        docx_path.unlink(missing_ok=True)
    except Exception as e:
        logger.error("mockup job %s FAILED: %s\n%s", job_id, e, traceback.format_exc())
        jobs.fail(job_id, str(e) or type(e).__name__)
    finally:
        input_path.unlink(missing_ok=True)


@router.post("/mockup/generate")
async def generate_mockup(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    user=Depends(verify_token),
):
    """Pas 2: pornește generarea (cu sau fără AI) pe fișierul din estimare."""
    est = jobs.pop_estimate(req.estimate_id)
    if est is None:
        raise HTTPException(
            status_code=404,
            detail="Estimarea a expirat sau serverul a fost repornit — reîncarcă fișierul.",
        )
    if req.use_ai and not est.get("fits_budget", False):
        Path(est["file_path"]).unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail="Bugetul zilnic gratuit de tokeni nu ajunge pentru acest fișier. "
                   "Continuă fără AI sau revino mâine.",
        )

    user_email = getattr(user, "email", None) or "anonymous"
    job_id = jobs.create_job(user_email)
    background_tasks.add_task(_run_job, job_id, Path(est["file_path"]), est["filename"], req.use_ai)
    return {"job_id": job_id}


@router.get("/mockup/job/{job_id}")
async def get_mockup_job(job_id: str, user=Depends(verify_token)):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job negăsit sau expirat")
    return job
```

- [ ] **Step 4: Rulează TOATE testele backend**

Run: `python -m pytest tests/ -v`
Expected: toate pass (minuta, auth, documents, storage neatinse și verzi)

- [ ] **Step 5: Commit**

```bash
git add backend/routers/mockup.py backend/tests/test_mockup.py
git commit -m "feat: contract async estimate/generate/job pentru mockup"
```

---

### Task 9: Frontend — API client + EstimateCard + ScenariiPreviewTable

**Files:**
- Modify: `frontend/lib/api.ts` (înlocuiește `postMockup`/`postScenarii` cu funcțiile noi)
- Create: `frontend/components/EstimateCard.tsx`, `frontend/components/ScenariiPreviewTable.tsx`

**Interfaces:**
- Produces (folosite de Task 10/11):
  - `postScenariiEstimate(file) / postMockupEstimate(file) -> Promise<EstimateResponse>`
  - `postScenariiGenerate(estimateId, useAi) / postMockupGenerate(estimateId, useAi) -> Promise<{job_id}>`
  - `getScenariiJob(jobId) -> Promise<ScenariiJob>`, `getMockupJob(jobId) -> Promise<MockupJob>`
  - `<EstimateCard estimate={EstimateResponse} toolLabel="scenarii" onAi={} onNoAi={} onCancel={} />`
  - `<ScenariiPreviewTable scenarios={Scenariu[]} />`

- [ ] **Step 1: Înlocuiește în `frontend/lib/api.ts` funcțiile `postMockup` și `postScenarii` (liniile 69-82) cu:**

```typescript
export type EstimateResponse = {
  estimate_id: string;
  est_tokens: number;
  est_minutes: number;
  fits_budget: boolean;
  modules?: number;
};

export type Scenariu = {
  id: string;
  capitol: string;
  subcapitol: string;
  titlu_scenariu: string;
  obiectiv: string;
  preconditii: string;
  pasi: string;
  rezultat_asteptat: string;
  tip_test: string;
  prioritate: string;
  dependente: string;
  observatii: string;
  ai: boolean;
};

export type ScenariiJob = {
  status: "processing" | "done" | "error";
  step?: string; // "module:2/5:Nume" | "building"
  filename?: string;
  xlsx_b64?: string;
  scenarios?: Scenariu[];
  ai_used?: boolean;
  storage_path?: string;
  error?: string;
};

export type MockupJob = {
  status: "processing" | "done" | "error";
  step?: string; // "parsing" | "ai" | "building"
  filename?: string;
  docx_b64?: string;
  html?: string;
  ai_used?: boolean;
  storage_path?: string;
  error?: string;
};

function postGenerate(path: string, estimateId: string, useAi: boolean) {
  return apiFetch(`${PROXY}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ estimate_id: estimateId, use_ai: useAi }),
  });
}

export async function postScenariiEstimate(file: File): Promise<EstimateResponse> {
  return postFile("scenarii/estimate", file) as Promise<EstimateResponse>;
}

export async function postScenariiGenerate(
  estimateId: string,
  useAi: boolean
): Promise<{ job_id: string }> {
  return postGenerate("scenarii/generate", estimateId, useAi) as Promise<{ job_id: string }>;
}

export async function getScenariiJob(jobId: string): Promise<ScenariiJob> {
  return apiFetch(`${PROXY}/scenarii/job/${jobId}`) as Promise<ScenariiJob>;
}

export async function postMockupEstimate(file: File): Promise<EstimateResponse> {
  return postFile("mockup/estimate", file) as Promise<EstimateResponse>;
}

export async function postMockupGenerate(
  estimateId: string,
  useAi: boolean
): Promise<{ job_id: string }> {
  return postGenerate("mockup/generate", estimateId, useAi) as Promise<{ job_id: string }>;
}

export async function getMockupJob(jobId: string): Promise<MockupJob> {
  return apiFetch(`${PROXY}/mockup/job/${jobId}`) as Promise<MockupJob>;
}
```

- [ ] **Step 2: Creează `frontend/components/EstimateCard.tsx`**

```tsx
"use client";
import type { EstimateResponse } from "@/lib/api";

type Props = {
  estimate: EstimateResponse;
  toolLabel: string; // "scenariile" | "documentația"
  onAi: () => void;
  onNoAi: () => void;
  onCancel: () => void;
};

export default function EstimateCard({ estimate, toolLabel, onAi, onNoAi, onCancel }: Props) {
  const tokens = estimate.est_tokens.toLocaleString("ro-RO");
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col gap-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-800 mb-1">
          Estimare procesare cu AI
        </h3>
        <p className="text-sm text-slate-600">
          ~{tokens} tokeni · ~{estimate.est_minutes} min
          {estimate.modules ? ` · ${estimate.modules} module` : ""}
        </p>
      </div>

      {!estimate.fits_budget && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Cota gratuită zilnică de AI e aproape epuizată pentru acest fișier.
          Poți continua fără AI acum sau poți reveni mâine pentru varianta AI.
        </p>
      )}

      <div className="flex flex-col gap-2">
        <button
          onClick={onAi}
          disabled={!estimate.fits_budget}
          className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ✨ Generează cu AI
        </button>
        <button
          onClick={onNoAi}
          className="w-full bg-slate-100 text-slate-700 py-2.5 rounded-lg text-sm font-semibold hover:bg-slate-200"
        >
          Continuă fără AI (instant, {toolLabel} standard)
        </button>
        <button onClick={onCancel} className="text-sm text-slate-500 underline">
          Anulează
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Creează `frontend/components/ScenariiPreviewTable.tsx`**

```tsx
"use client";
import type { Scenariu } from "@/lib/api";

const PRIORITY_STYLES: Record<string, string> = {
  Critical: "bg-red-100 text-red-700",
  High: "bg-orange-100 text-orange-700",
  Medium: "bg-yellow-100 text-yellow-700",
  Low: "bg-slate-100 text-slate-600",
};

export default function ScenariiPreviewTable({ scenarios }: { scenarios: Scenariu[] }) {
  const stubCount = scenarios.filter((s) => !s.ai).length;
  return (
    <div className="flex flex-col gap-2">
      {stubCount > 0 && stubCount < scenarios.length && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {stubCount} scenarii marcate cu galben au fost generate fără AI
          (apelul AI a eșuat pentru modulul respectiv) — conțin pași generici.
        </p>
      )}
      <div className="overflow-auto max-h-96 border border-slate-200 rounded-lg">
        <table className="w-full text-xs">
          <thead className="bg-slate-800 text-white sticky top-0">
            <tr>
              <th className="px-2 py-2 text-left font-semibold">ID</th>
              <th className="px-2 py-2 text-left font-semibold">Capitol</th>
              <th className="px-2 py-2 text-left font-semibold">Titlu Scenariu</th>
              <th className="px-2 py-2 text-left font-semibold">Tip</th>
              <th className="px-2 py-2 text-left font-semibold">Prioritate</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr
                key={s.id}
                className={`border-t border-slate-100 ${s.ai ? "" : "bg-amber-50"}`}
                title={`${s.obiectiv}\n\nPași:\n${s.pasi}`}
              >
                <td className="px-2 py-1.5 font-mono whitespace-nowrap">{s.id}</td>
                <td className="px-2 py-1.5">{s.capitol}</td>
                <td className="px-2 py-1.5">{s.titlu_scenariu}</td>
                <td className="px-2 py-1.5 whitespace-nowrap">{s.tip_test}</td>
                <td className="px-2 py-1.5">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      PRIORITY_STYLES[s.prioritate] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {s.prioritate}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-400">
        {scenarios.length} scenarii · treci cu mouse-ul peste un rând pentru obiectiv și pași.
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Verifică build-ul (paginile încă folosesc funcțiile vechi șterse — build-ul VA eșua; e OK doar dacă erorile sunt exclusiv `postMockup`/`postScenarii` lipsă în cele două pagini)**

Run: `npm run build` (din `frontend/`)
Expected: FAIL doar cu `'postScenarii'`/`'postMockup'` not exported — se rezolvă în Task 10/11. Dacă apar alte erori, repară-le acum.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/components/EstimateCard.tsx frontend/components/ScenariiPreviewTable.tsx
git commit -m "feat: API client si componente pentru fluxul estimate/generate (frontend)"
```

---

### Task 10: Pagina Scenarii — mașina de stări nouă

**Files:**
- Modify: `frontend/app/(app)/scenarii/page.tsx` (rescriere completă)

**Interfaces:**
- Consumes: `postScenariiEstimate`, `postScenariiGenerate`, `getScenariiJob`, `EstimateCard`, `ScenariiPreviewTable`, componente existente.

- [ ] **Step 1: Rescrie `frontend/app/(app)/scenarii/page.tsx`**

```tsx
"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import EstimateCard from "@/components/EstimateCard";
import ScenariiPreviewTable from "@/components/ScenariiPreviewTable";
import {
  postScenariiEstimate,
  postScenariiGenerate,
  getScenariiJob,
  type EstimateResponse,
  type Scenariu,
} from "@/lib/api";

type State = "idle" | "estimating" | "ready" | "processing" | "done" | "error";

function stepLabel(step: string): string {
  const m = step.match(/^module:(\d+)\/(\d+):(.*)$/);
  if (m) return `Analizez modulul ${m[1]} din ${m[2]}: ${m[3]}...`;
  if (step === "building") return "Generez documentul Excel...";
  return "Se procesează...";
}

function isColdStartError(msg: string): boolean {
  return (
    msg.includes("timp util") ||
    msg.includes("unreachable") ||
    msg.includes("502") ||
    msg.includes("504")
  );
}

export default function ScenariPage() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null);
  const [progressLabel, setProgressLabel] = useState("Se inițializează...");
  const [result, setResult] = useState<{
    filename: string;
    xlsxB64: string;
    scenarios: Scenariu[];
    aiUsed: boolean;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const cancelledRef = useRef(false);

  async function handleEstimate() {
    if (!file) return;
    setState("estimating");
    setError("");
    cancelledRef.current = false;
    try {
      let est: EstimateResponse;
      try {
        est = await postScenariiEstimate(file);
      } catch (initErr) {
        // Render free tier adoarme — retry automat dupa 5s
        const msg = initErr instanceof Error ? initErr.message : "";
        if (isColdStartError(msg)) {
          setProgressLabel("Server pornit, se retransmite automat...");
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          est = await postScenariiEstimate(file);
        } else {
          throw initErr;
        }
      }
      if (cancelledRef.current) return;
      setEstimate(est);
      setState("ready");
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  async function handleGenerate(useAi: boolean) {
    if (!estimate) return;
    setState("processing");
    setProgressLabel(useAi ? "Pornesc generarea cu AI..." : "Generez scenariile...");
    setError("");
    cancelledRef.current = false;
    try {
      const { job_id } = await postScenariiGenerate(estimate.estimate_id, useAi);

      while (true) {
        await new Promise((r) => setTimeout(r, 2000));
        if (cancelledRef.current) return;

        const job = await getScenariiJob(job_id);
        if (cancelledRef.current) return;

        if (job.step) setProgressLabel(stepLabel(job.step));

        if (job.status === "done") {
          setResult({
            filename: job.filename!,
            xlsxB64: job.xlsx_b64!,
            scenarios: job.scenarios ?? [],
            aiUsed: job.ai_used ?? false,
          });
          setState("done");
          setHistoryKey((k) => k + 1);
          return;
        }
        if (job.status === "error") {
          throw new Error(job.error || "Eroare în generarea scenariilor");
        }
      }
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  function reset() {
    cancelledRef.current = true;
    setFile(null);
    setEstimate(null);
    setResult(null);
    setState("idle");
    setError("");
  }

  return (
    <div className="flex h-screen">
      <div className="flex-1 p-6 overflow-auto">
        <ToolCard
          icon="🧪"
          title="Scenarii Testare"
          description="Specificație (.docx) → Excel cu scenarii QA generate cu AI"
        />

        {state === "idle" && (
          <div className="flex flex-col gap-4">
            <UploadZone accept=".docx" label=".docx" onFile={setFile} />
            <button
              onClick={handleEstimate}
              disabled={!file}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Continuă → Estimare
            </button>
          </div>
        )}

        {state === "estimating" && <ProcessingSpinner label="Analizez specificația..." />}

        {state === "ready" && estimate && (
          <EstimateCard
            estimate={estimate}
            toolLabel="scenariile"
            onAi={() => handleGenerate(true)}
            onNoAi={() => handleGenerate(false)}
            onCancel={reset}
          />
        )}

        {state === "processing" && <ProcessingSpinner label={progressLabel} />}

        {state === "done" && result && (
          <div className="flex flex-col gap-4">
            {!result.aiUsed && (
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Scenariile au fost generate fără AI — conțin structura capitolelor
                cu pași generici.
              </p>
            )}
            <ScenariiPreviewTable scenarios={result.scenarios} />
            <ResultPanel
              filename={result.filename}
              docxB64={result.xlsxB64}
              previewHtml=""
              onReset={reset}
              downloadLabel="↓ Descarcă .xlsx"
              resetLabel="+ Generează alte scenarii"
            />
          </div>
        )}

        {state === "error" && (
          <div className="flex flex-col gap-3">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
              {error}
              {error.includes("expirat") && (
                <p className="mt-2 text-xs">
                  Serverul a fost repornit între timp — reîncarcă fișierul și reia.
                </p>
              )}
            </div>
            <button onClick={reset} className="text-sm text-blue-600 underline">
              Încearcă din nou
            </button>
          </div>
        )}
      </div>

      <HistoryPanel refreshKey={historyKey} />
    </div>
  );
}
```

- [ ] **Step 2: Verifică build-ul**

Run: `npm run build`
Expected: FAIL rămas doar pe `postMockup` în `mockup/page.tsx` (se rezolvă în Task 11); pagina scenarii compilează.

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(app)/scenarii/page.tsx"
git commit -m "feat: pagina scenarii cu estimare, alegere AI/fara AI, progres si preview"
```

---

### Task 11: Pagina Mockup — mașina de stări nouă

**Files:**
- Modify: `frontend/app/(app)/mockup/page.tsx` (rescriere completă)

**Interfaces:**
- Consumes: `postMockupEstimate`, `postMockupGenerate`, `getMockupJob`, `EstimateCard`.

- [ ] **Step 1: Rescrie `frontend/app/(app)/mockup/page.tsx`**

```tsx
"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import EstimateCard from "@/components/EstimateCard";
import {
  postMockupEstimate,
  postMockupGenerate,
  getMockupJob,
  type EstimateResponse,
} from "@/lib/api";

type State = "idle" | "estimating" | "ready" | "processing" | "done" | "error";

function stepLabel(step: string): string {
  if (step === "parsing") return "Analizez fișierul...";
  if (step === "ai") return "Îmbogățesc descrierile cu AI...";
  if (step === "building") return "Generez documentul Word...";
  return "Se procesează...";
}

function isColdStartError(msg: string): boolean {
  return (
    msg.includes("timp util") ||
    msg.includes("unreachable") ||
    msg.includes("502") ||
    msg.includes("504")
  );
}

export default function MockupPage() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null);
  const [progressLabel, setProgressLabel] = useState("Se inițializează...");
  const [result, setResult] = useState<{
    filename: string;
    docxB64: string;
    html: string;
    aiUsed: boolean;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const cancelledRef = useRef(false);

  async function handleEstimate() {
    if (!file) return;
    setState("estimating");
    setError("");
    cancelledRef.current = false;
    try {
      let est: EstimateResponse;
      try {
        est = await postMockupEstimate(file);
      } catch (initErr) {
        const msg = initErr instanceof Error ? initErr.message : "";
        if (isColdStartError(msg)) {
          setProgressLabel("Server pornit, se retransmite automat...");
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          est = await postMockupEstimate(file);
        } else {
          throw initErr;
        }
      }
      if (cancelledRef.current) return;
      setEstimate(est);
      setState("ready");
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  async function handleGenerate(useAi: boolean) {
    if (!estimate) return;
    setState("processing");
    setProgressLabel(useAi ? "Pornesc generarea cu AI..." : "Generez documentația...");
    setError("");
    cancelledRef.current = false;
    try {
      const { job_id } = await postMockupGenerate(estimate.estimate_id, useAi);

      while (true) {
        await new Promise((r) => setTimeout(r, 2000));
        if (cancelledRef.current) return;

        const job = await getMockupJob(job_id);
        if (cancelledRef.current) return;

        if (job.step) setProgressLabel(stepLabel(job.step));

        if (job.status === "done") {
          setResult({
            filename: job.filename!,
            docxB64: job.docx_b64!,
            html: job.html ?? "",
            aiUsed: job.ai_used ?? false,
          });
          setState("done");
          setHistoryKey((k) => k + 1);
          return;
        }
        if (job.status === "error") {
          throw new Error(job.error || "Eroare în generarea mockup-ului");
        }
      }
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  function reset() {
    cancelledRef.current = true;
    setFile(null);
    setEstimate(null);
    setResult(null);
    setState("idle");
    setError("");
  }

  return (
    <div className="flex h-screen">
      <div className="flex-1 p-6 overflow-auto">
        <ToolCard
          icon="🖥️"
          title="Mockup Ecran"
          description="Specificație (.xlsx sau .docx) → Documentație Word + preview HTML"
        />

        {state === "idle" && (
          <div className="flex flex-col gap-4">
            <UploadZone accept=".xlsx,.docx" label=".xlsx sau .docx" onFile={setFile} />
            <button
              onClick={handleEstimate}
              disabled={!file}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Continuă → Estimare
            </button>
          </div>
        )}

        {state === "estimating" && <ProcessingSpinner label="Analizez fișierul..." />}

        {state === "ready" && estimate && (
          <EstimateCard
            estimate={estimate}
            toolLabel="documentația"
            onAi={() => handleGenerate(true)}
            onNoAi={() => handleGenerate(false)}
            onCancel={reset}
          />
        )}

        {state === "processing" && <ProcessingSpinner label={progressLabel} />}

        {state === "done" && result && (
          <div className="flex flex-col gap-4">
            {!result.aiUsed && (
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Documentația a fost generată fără AI — descrierile provin direct
                din fișierul sursă.
              </p>
            )}
            <ResultPanel
              filename={result.filename}
              docxB64={result.docxB64}
              previewHtml={result.html}
              onReset={reset}
              resetLabel="+ Generează alt mockup"
            />
          </div>
        )}

        {state === "error" && (
          <div className="flex flex-col gap-3">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
              {error}
              {error.includes("expirat") && (
                <p className="mt-2 text-xs">
                  Serverul a fost repornit între timp — reîncarcă fișierul și reia.
                </p>
              )}
            </div>
            <button onClick={reset} className="text-sm text-blue-600 underline">
              Încearcă din nou
            </button>
          </div>
        )}
      </div>

      <HistoryPanel refreshKey={historyKey} />
    </div>
  );
}
```

Notă: păstrează `icon` și `description` existente din pagina veche dacă diferă (verifică înainte de rescriere) — doar fluxul se schimbă.

- [ ] **Step 2: Build complet — trebuie să treacă**

Run: `npm run build`
Expected: build reușit, fără erori TypeScript

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(app)/mockup/page.tsx"
git commit -m "feat: pagina mockup cu estimare, alegere AI/fara AI si progres"
```

---

### Task 12: Verificare E2E locală (cu Mistral real)

**Files:**
- Fără fișiere noi (doar verificare); eventual fixuri minore descoperite acum.

**Precondiție:** `MISTRAL_API_KEY` trebuie să existe în `backend/.env`. Verifică cu:
```bash
grep -c "^MISTRAL_API_KEY=" backend/.env
```
Expected: `1`. Dacă lipsește → oprește-te și cere utilizatorului cheia (cont pe console.mistral.ai).

- [ ] **Step 1: Toate testele backend**

Run (din `backend/`): `python -m pytest tests/ -v`
Expected: toate pass, zero failures

- [ ] **Step 2: Smoke test live Mistral (1 apel mic, real)**

Run (din `backend/`):
```bash
python -c "
import asyncio, llm_client
async def main():
    out = await llm_client.chat('Răspunde doar cu JSON.', 'Returnează {\"status\": \"ok\"}', max_tokens=50)
    print('MISTRAL OK:', out)
asyncio.run(main())
"
```
Expected: `MISTRAL OK: {"status": "ok"}` (sau JSON echivalent). La 401 → cheia e greșită; oprește-te și raportează.

- [ ] **Step 3: Pipeline scenarii cu AI real pe un spec mic**

Run (din `backend/`):
```bash
python -c "
import asyncio
from pathlib import Path
from docx import Document
from pipelines.scenarii_pipeline import run_scenarii_pipeline

doc = Document()
doc.add_heading('Modul Facturare', level=1)
doc.add_heading('Emitere factura', level=2)
doc.add_paragraph('Utilizatorul emite factura pe baza comenzii. Sistemul valideaza TVA-ul si respinge facturile fara client.')
doc.save('_test_spec.docx')

async def main():
    xlsx, scenarios = await run_scenarii_pipeline(Path('_test_spec.docx'), use_ai=True, on_step=print)
    print(f'{len(scenarios)} scenarii, AI: {sum(1 for s in scenarios if s[\"ai\"])}')
    for s in scenarios[:3]:
        print(s['id'], '|', s['titlu_scenariu'], '|', s['tip_test'])
    xlsx.unlink()
    Path('_test_spec.docx').unlink()
asyncio.run(main())
"
```
Expected: pași `module:1/1:...`, `building`, apoi 2+ scenarii cu AI: > 0, titluri specifice despre facturare (nu „Verificare: ..."), cel puțin un test negativ despre validare TVA/client.

- [ ] **Step 4: Repornește serverele locale și verifică fluxul complet în browser**

```bash
# backend (din backend/): python -m uvicorn main:app --host 127.0.0.1 --port 8000
# frontend (din frontend/): npm run dev
```
Manual în browser (`http://localhost:3000`):
1. Login → pagina Scenarii → upload spec .docx real → vezi EstimateCard cu tokeni/module → „Generează cu AI" → progres pe module → preview tabel + descarcă .xlsx și deschide-l.
2. Aceeași pagină → „Continuă fără AI" → rezultat instant cu stub-uri + avertisment galben.
3. Pagina Mockup → upload `.docx`/`.xlsx` exemplu → „Generează cu AI" → verifică secțiunea „Prezentare generală" în preview HTML și în Word-ul descărcat.
4. Verifică pagina Repository — documentele noi apar.

- [ ] **Step 5: Commit final (fixuri descoperite la verificare, dacă există)**

```bash
git add -A backend/ frontend/
git commit -m "fix: ajustari post-verificare e2e mockup/scenarii"
```

---

## Post-implementare (deploy — separat, după acceptarea utilizatorului)

Nu face parte din plan; de discutat la final: `MISTRAL_API_KEY` pe Render, push pe `master` (Render se deploy-ează automat), `vercel --prod` pentru frontend.
