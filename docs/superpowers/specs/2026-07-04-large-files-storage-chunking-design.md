# Fișiere mari (20-25MB+) fără pierderi: upload prin Supabase Storage + chunking AI — Design

**Data:** 2026-07-04
**Status:** aprobat de utilizator (sesiune brainstorming)
**Context:** utilizatorii încarcă specificații .docx de minim 20-25MB (screenshot-uri multe, text moderat: 50-300 pagini). Cerință primordială: documentul generat înglobează TOATE datele din sursă — fără trunchieri, fără pierderi silențioase. Durata procesării nu contează.

## Probleme rezolvate

1. **Transport**: Vercel are limită hard de 4,5MB pe body-ul funcțiilor serverless (proxy-ul), neconfigurabilă; Render free are limite nedocumentate (rapoarte de 413 la ~5MB). Fix-ul anterior (`proxyClientMaxBodySize: 25mb`) ajută doar local.
2. **Generare**: contextul Mistral e 128k tokeni; un modul mare nu încape într-un singur apel → azi ar cădea pe stub-uri (pierdere de calitate pe exact fișierele importante).

## Decizii (cu utilizatorul)

- Transport: **upload direct browser → Supabase Storage** cu URL semnat (opțiunea A; B=chunked-upload prin proxy respinsă ca fragilă; C=direct la Render respinsă — limite nedocumentate).
- Generare: **chunking pe granițe naturale + acumulare într-un singur Excel** (principiul minuta, fără fază de reduce — scenariile sunt aditive).
- Mockup: primește doar transportul nou; rămâne pe un singur apel AI (digestul provine din câmpurile parsate, nu din imagini).

## Arhitectură

### 1. Transport — Supabase Storage ca releu

- **Bucket privat `uploads`**, creat idempotent de backend la pornire (`storage.py`: `ensure_uploads_bucket()`, `file_size_limit` 50MB — maximul planului free).
- **`POST /api/uploads/sign`** (router nou `routers/uploads.py`, autentificat): body `{filename: str, tool: "scenarii"|"mockup"}` → generează `create_signed_upload_url` pe calea `{tool}/{uuid4}{ext}` → răspuns `{storage_path, signed_url, token}`. Validare extensie per tool (.docx pentru scenarii; .docx/.xlsx pentru mockup).
- **Browserul** face PUT direct la `signed_url` (fetch nativ, fără librărie nouă; `NEXT_PUBLIC_SUPABASE_URL` există).
- **`POST /api/{tool}/estimate` devine JSON** `{storage_path: str, filename: str}` (nu mai e multipart): backend descarcă obiectul cu service key într-un fișier temp local, **șterge imediat obiectul din storage** (storage = releu, nu depozit), apoi fluxul existent (estimare → estimate store cu TTL 10 min → generate → job) rămâne neschimbat.
- Obiecte orfane (upload făcut, estimate niciodată chemat): curățate best-effort la `ensure_uploads_bucket` (listare + ștergere obiecte mai vechi de 24h).
- Guard client: fișier >50MB respins înainte de upload, cu mesaj în română.

### 2. Generare integrală — chunking scenarii

- Constante: `CHUNK_INPUT_TOKENS = 15_000` (input per apel; ~33k caractere), `OUT_TOKENS_PER_CALL = 6_000` (existent, redenumit conceptual per apel).
- **Packing** (`_pack_chunks(structure) -> list[Chunk]`), unde `Chunk = {modul, capitole: list[dict]}`; indexul `i/n` per modul se calculează după packing (n = numărul de bucăți ale modulului):
  - capitolele (H2) unui modul se grupează în ordinea documentului în bucăți cu `estimate_tokens(text) ≤ CHUNK_INPUT_TOKENS`;
  - un capitol care singur depășește limita se sparge la subcapitole (H3), păstrând titlul capitolului în fiecare parte;
  - un subcapitol care singur depășește limita se sparge pe paragrafe (părți etichetate „(continuare)");
  - **invariant testat**: concatenarea textelor din toate bucățile == textul integral extras (nimic omis, nimic duplicat).
- **Un apel AI per bucată**, promptul existent + antet `MODUL: X (partea i din n)`. Scenariile din toate bucățile se acumulează; ID-urile `TC-nnn` se atribuie global la final; **un singur Excel** (formatul actual, 12 coloane).
- **Fallback per bucată**: apel eșuat (după retry-urile din llm_client) → stub-uri doar pentru capitolele/subcapitolele din bucata respectivă, marcate în Observații („Generat fără AI (fallback — apelul AI a eșuat)"). Nicio pierdere silențioasă.
- **Estimare reală**: `estimate_scenarii_job` rulează același packing → `{est_tokens, calls, modules, est_minutes, fits_budget}`; `est_minutes = max(1, round(calls * 30 / 60))`.
- **Buget**: `LLM_DAILY_TOKEN_BUDGET` default crește 500.000 → **2.000.000** (Mistral free ≈ 1B/lună; un spec de 300 pagini ≈ 100-250k tokeni).
- **Progres**: `on_step("chunk:i/n:<modul>")` + `"building"`.

### 3. Frontend

- `lib/api.ts`: `uploadSourceFile(file, tool) -> Promise<{storage_path}>` (sign prin proxy → PUT direct la Supabase; aruncă eroare clară la eșec); `postScenariiEstimate`/`postMockupEstimate` primesc `{storage_path, filename}` (JSON).
- Pagini: stare nouă `uploading` (`idle → uploading → estimating → ready → processing → done/error`), etichetă „Se încarcă fișierul... (fișierele mari pot dura ~1 minut)".
- `stepLabel`: `chunk:i/n:<modul>` → „Generez scenarii — partea i din n (modul)...". (La mockup rămân parsing/ai/building.)
- Erori: upload Supabase eșuat (mesaj + reîncearcă), >50MB blocat pre-upload, restul mesajelor existente neschimbate.
- Guard-ul de 25MB din fix-ul anterior se înlocuiește cu cel de 50MB (upload-ul nu mai trece prin proxy; `proxyClientMaxBodySize` rămâne ca plasă de siguranță pentru restul rutelor).

### 4. Testare

- Unit: packing (granițe H2, capitol uriaș → subcapitole, subcapitol uriaș → paragrafe, invariantul de completitudine), estimare cu `calls` corect, pipeline cu mock `llm_client.chat` per bucată + fallback per bucată, `routers/uploads.py` (validare extensie, 401), estimate JSON cu download storage mock-uit.
- Testele existente de router se adaptează la contractul JSON al estimate.
- Live local: fișierul de 14MB (reproducerea bug-ului inițial) prin fluxul complet — storage real, chunking real, AI real — verificând că toate capitolele apar în Excel.

### 5. Rollout & compatibilitate

- Nimic nou în env (service key există pe Render; `NEXT_PUBLIC_SUPABASE_URL` există pe Vercel). Bucket-ul se creează singur.
- Formatul Excel, contractul job (`status/step/filename/xlsx_b64/scenarios/ai_used`), minuta — neschimbate.
- Producția nu e afectată până la push (commit-urile rămân locale).
