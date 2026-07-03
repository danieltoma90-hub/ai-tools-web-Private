# Optimizare Mockup + Scenarii cu AI gratuit (Mistral) — Design

**Data:** 2026-07-03
**Status:** aprobat de utilizator (sesiune brainstorming)
**Nu se atinge:** pipeline-ul Minuta (optimizat recent pe Groq — Groq rămâne exclusiv pentru minuta).

## Problemă

- **Scenarii** (`pipelines/scenarii_pipeline.py`): generează stub-uri identice doar din titlurile de headings — conținutul nu reflectă textul specificației. Zero AI.
- **Mockup** (`pipelines/mockup_pipeline.py` + `skills/mockup/`): determinist (Excel/Word → Word + HTML), fără context de business și fără overview.
- **UX**: ambele pagini au doar upload → spinner generic → download; fără estimare, progres sau preview (scenarii).
- **Cod**: `tempfile.mktemp` (deprecat/nesigur), hack `sys.path.insert` în mockup_pipeline, routere sincrone care țin conexiunea deschisă.

## Decizii (cu utilizatorul)

1. **Provider LLM**: Mistral La Plateforme, tier gratuit „Experiment", model `mistral-large-latest` (cea mai bună română dintre opțiunile gratuite, context 128k). **Nu Groq** (rezervat minutei). **Nu Gemini** (contul are limită 0 pe free tier — verificat 2026-07-01). **Nu abonamentul Claude Code** (nepermis ca API de backend multi-user).
2. **Arhitectură**: strat subțire provider-agnostic (`llm_client.py`) — providerul se schimbă din env fără a atinge pipeline-urile.
3. **Scenarii**: generare din **textul complet** al spec-ului (headings + corp), nu doar titluri.
4. **Mockup**: AI adaugă secțiune „Prezentare generală" + descrieri de câmpuri îmbogățite.
5. **Cotă insuficientă**: frontend-ul **întreabă utilizatorul** (continuă fără AI / anulează) pe baza unui pre-check de tokeni.
6. **UX**: progres pas-cu-pas, preview tabel scenarii în pagină, mesaje de eroare specifice.

## Arhitectură backend

### 1. `backend/llm_client.py` (nou, ~120 linii)

- Env: `LLM_PROVIDER` (default `mistral`), `MISTRAL_API_KEY`, `MISTRAL_MODEL` (default `mistral-large-latest`), `LLM_DAILY_TOKEN_BUDGET` (default 500.000).
- `async chat(system: str, user: str, max_tokens: int, json_mode: bool = True) -> str` — httpx direct către `https://api.mistral.ai/v1/chat/completions`; retry cu backoff exponențial la 429/5xx (max 3); throttling minim 1,5 s între apeluri (free tier ~1 RPS).
- `estimate_tokens(text: str) -> int` — euristică ~2,2 caractere/token pentru română (validată la minuta).
- Contor zilnic in-memory al tokenilor consumați + `remaining_budget()` — protecție soft (se resetează la restart Render; acceptat).
- Interfața e generică (mesaje → text); un provider nou = o funcție de transport nouă, pipeline-urile nu se ating.

### 2. Scenarii v2 — `pipelines/scenarii_pipeline.py`

- `_extract_structure` se extinde: reține și **paragrafele de corp** sub fiecare heading (`text` per capitol/subcapitol).
- `estimate_scenarii_job(docx_path) -> {est_tokens, fits_budget, est_minutes, modules}`.
- `run_scenarii_pipeline(docx_path, use_ai: bool, on_step) -> (xlsx_path, scenarios: list[dict])`:
  - `use_ai=False` → fluxul stub actual, neschimbat.
  - `use_ai=True` → un apel per modul H1: system prompt QA + textul modulului → JSON listă de scenarii cu câmpurile celor 12 coloane (fără ID — TC-nnn se atribuie local, secvențial). Validare Pydantic; la JSON invalid → un retry, apoi fallback.
  - **Fallback per modul**: apel eșuat → doar modulul respectiv primește stub-uri, marcate în coloana Observații („generat fără AI").
  - `on_step("module:2/5:<nume>")` pentru progres.
- Excel: format identic (12 coloane, stiluri, freeze panes). Returnează și lista de scenarii pentru preview-ul din frontend.

### 3. Mockup v2 — `pipelines/mockup_pipeline.py` + `skills/mockup/`

- Parsarea deterministă rămâne baza și plan-B-ul complet.
- `estimate_mockup_job(input_path) -> {est_tokens, fits_budget, est_minutes}`.
- `run_mockup_pipeline(input_path, use_ai: bool, on_step) -> (docx_path, html, ai_used: bool)`:
  - `use_ai=True` → **un apel**: spec-ul parsat + descrierile existente → JSON `{overview: {scop, flux, legaturi}, descrieri: {camp: text}}`.
  - Merge: secțiune „Prezentare generală" la începutul Word + HTML; descrierile îmbogățite le înlocuiesc pe cele deterministe doar unde AI a răspuns.
  - Orice eșec AI → output determinist actual, fără eroare pentru utilizator (marcat în răspuns `ai_used: false`).

### 4. Routere + `backend/jobs.py`

- `backend/jobs.py` (nou): job store in-memory partajat de mockup + scenarii (`create_job`, `set_step`, `finish`, `fail`, `get`; TTL cleanup simplu). **Minuta nu se migrează** — își păstrează `_jobs` propriu.
- Contract nou per tool (mockup și scenarii, simetric):
  - `POST /api/{tool}/estimate` — primește fișierul, îl validează, îl salvează temporar (~10 min TTL), returnează `{estimate_id, est_tokens, fits_budget, est_minutes, modules?}`. Evită dublu-upload.
  - `POST /api/{tool}/generate` — body `{estimate_id, use_ai}` → `{job_id}`; rulează în `BackgroundTasks`.
  - `GET /api/{tool}/job/{job_id}` — `{status, step?, filename?, docx_b64|xlsx_b64?, html?|scenarios?, ai_used, error?}`.
- Refactoring: `tempfile.mktemp` → `tempfile.mkstemp`/`NamedTemporaryFile` peste tot în mockup/scenarii; `sys.path.insert` eliminat → `skills/mockup/__init__.py` + importuri absolute (`from skills.mockup.parser import parse_excel`), cu ajustarea importurilor interne din skill.

## Frontend

### Flux nou (ambele pagini)

`idle → estimating → estimate-ready → processing → done | error`

1. Upload → `POST /estimate` → **EstimateCard**: „~28.000 tokeni · ~2 min · 5 module" cu butoane **Generează cu AI** (primar) / **Continuă fără AI** / **Anulează**. `fits_budget=false` → butonul AI dezactivat + explicație („Cota gratuită zilnică e aproape epuizată — revino mâine sau continuă fără AI").
2. Processing → polling job cu etichete de progres: „Analizez modulul 2/5: Fluxuri de business...", „Generez documentul Excel...".
3. Done:
   - **Scenarii**: `ScenariiPreviewTable` — tabel în pagină (ID, Capitol, Titlu, Pași, Prioritate), rândurile fallback-stub marcate vizual; buton „Descarcă .xlsx".
   - **Mockup**: preview HTML existent + secțiunea „Prezentare generală".
4. Erori specifice: cotă epuizată (cu acțiune „continuă fără AI"), 504/backend adormit (auto-retry ca la minuta), fișier invalid, job/estimate expirat („reîncarcă fișierul" — restart Render).

### Fișiere

- `lib/api.ts`: `postMockupEstimate`, `postMockupGenerate`, `getMockupJob` + echivalentele scenarii.
- `app/(app)/mockup/page.tsx`, `app/(app)/scenarii/page.tsx` — mașina de stări nouă.
- `components/EstimateCard.tsx`, `components/ScenariiPreviewTable.tsx` (noi).
- UploadZone, ResultPanel, HistoryPanel — neschimbate.

## Testare

- Unit backend: `llm_client` (httpx mock: retry, throttle, buget), extracție heading+corp, validare/fallback scenarii, merge mockup, flux estimate→generate→job.
- `test_mockup.py`, `test_scenarii.py` rescrise pe contractul async.
- Verificare locală cu fișiere reale (`skills/mockup/input/`, spec DOCX real) pe serverele locale.

## Rollout

1. Local: implementare + teste + verificare manuală.
2. Utilizatorul creează cont [console.mistral.ai](https://console.mistral.ai) → `MISTRAL_API_KEY` în `backend/.env`.
3. Render: `MISTRAL_API_KEY`, opțional `LLM_DAILY_TOKEN_BUDGET`; Vercel: nimic nou (proxy existent).
4. Deploy după validare locală (push master → Render; `vercel --prod`).

## Compatibilitate

- Formatul Excel scenarii și structura Word mockup rămân compatibile cu Repository.
- Varianta „fără AI" produce exact outputul de azi.
- Niciun fișier din fluxul minuta nu se modifică.
