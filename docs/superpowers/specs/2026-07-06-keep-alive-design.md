# Keep-alive permanent pentru ai-tools-web — Design

**Data:** 2026-07-06
**Status:** aprobat de utilizator
**Problemă:** după zile de neutilizare aplicația „moare": Render free adoarme după 15 min inactivitate (cold start 30-60s, uneori timeout), iar Supabase free se PAUZEAZĂ după 7 zile fără activitate în baza de date (login/storage complet picate, reactivare doar manuală din dashboard). Utilizatorii vor cele 3 tool-uri funcționale oricând.

## Decizii (cu utilizatorul)

- Soluție 100% gratuită cu ping-uri externe (nu Render Starter $7/lună).
- Pinger: **cron-job.org** (cont gratuit al utilizatorului) cu program de lucru — NU 24/7 (ținerea trează non-stop ar consuma 744 din cele 750 ore/lună Render și orice depășire SUSPENDĂ serviciul; programul de lucru consumă ~300h/lună, fără risc).
- Respins: UptimeRobot 24/7 (riscul celor 750h), GitHub Actions pentru Render (cota de 2.000 min/lună a repo-ului privat nu acoperă ping-uri la 10 min).

## Componente

### 1. `GET /health` extins (backend/main.py)

- Face `get_supabase().storage.list_buckets()` (apel ieftin; metadata storage = activitate de bază de date → resetează timer-ul de pauză Supabase).
- Răspuns mereu 200: `{"status": "ok", "supabase": "ok"}` sau `{"status": "ok", "supabase": "eroare: <mesaj scurt>"}` — eșecul Supabase nu pică ping-ul (vrem activitate + vizibilitate, nu alarme false pe Render).
- Fără autentificare; nu expune date.
- Test unit: cu mock Supabase ok și cu excepție.

### 2. Joburi cron-job.org (configurate de utilizator, cu pașii documentați)

| Job | URL | Program | Scop |
|---|---|---|---|
| „Render treaz în program" | `https://ai-tools-backend-3vvz.onrender.com/health` | L-V, 6:30–20:30, la 10 min; timeout 90s | Render nu adoarme în orele de lucru |
| „Supabase activ non-stop" | același | zilnic, la 6 ore | Supabase nu se pauzează niciodată |

- Notificări email la eșec: activate (monitorizare gratuită).
- Consum Render: ~14h/zi × 22 zile ≈ 300h/lună << 750.

### 3. Documentare

- Secțiune „Fiabilitate / Keep-alive" în `D:\ai-tools-web\CLAUDE.md`: mecanismul, joburile, consecințele dispariției lor (Render redoarme în 15 min; Supabase se pauzează în 7 zile → reactivare manuală din dashboard Supabase), cum se verifică (`curl /health`, istoricul cron-job.org).

### 4. Verificare

- Deploy → `curl https://ai-tools-backend-3vvz.onrender.com/health` întoarce `supabase: ok`.
- După configurarea joburilor: istoricul cron-job.org arată ping-uri reușite; backend-ul răspunde instant după >15 min fără trafic real.

## În afara scope-ului (menționat, respins ca YAGNI)

- Persistarea joburilor în DB (restarturile devin rare cu keep-alive; UX-ul actual de „estimare expirată" acoperă cazul).
- Supabase Pro / Render Starter (plătite).
