# AI Tools Web — Context Complet

## Descriere proiect
Aplicație web internă TotalSoft cu 3 tool-uri AI (Minută, Mockup, Scenarii), autentificare cu Supabase și backend Python/FastAPI.

## Stack tehnic
- **Frontend**: Next.js 16.2.9 (App Router), React 19, Tailwind CSS — deploy pe **Vercel**
- **Backend**: FastAPI (Python) — deploy pe **Render** (free tier)
- **Auth**: Supabase Auth (email/password, JWT ES256)
- **Storage**: Supabase Storage (pentru documente generate)

## URL-uri producție
- **Frontend**: https://ai-tools-web-three.vercel.app
- **Backend**: https://ai-tools-backend-3vvz.onrender.com
- **Supabase project**: `zjmtqitymnrmmmsfoolp`

## Structură repo
```
ai-tools-web/
├── frontend/               # Next.js App Router
│   ├── app/
│   │   ├── (app)/          # Pagini autentificate (cu Sidebar)
│   │   │   ├── minuta/
│   │   │   ├── mockup/
│   │   │   ├── scenarii/
│   │   │   ├── repository/
│   │   │   └── invite/     # Invită useri noi
│   │   ├── api/
│   │   │   ├── auth/
│   │   │   │   ├── login/route.ts      # Form POST handler → Supabase → cookie
│   │   │   │   └── clear-session/      # Logout
│   │   │   └── proxy/[...path]/route.ts # Server-side proxy → FastAPI
│   │   ├── auth/callback/  # Link invitație Supabase
│   │   ├── login/          # Form HTML nativ, fără React Server Action
│   │   └── actions/
│   │       ├── auth.ts     # loginAction (nefolosit pt login, dar păstrat)
│   │       └── invite.ts   # inviteUserAction
│   ├── middleware.ts        # JWT expiry check (fără network calls)
│   ├── lib/
│   │   ├── api.ts          # Client calls → /api/proxy/*
│   │   └── auth.ts         # logout()
│   └── components/
│       └── Sidebar.tsx
└── backend/                # FastAPI
    ├── main.py
    ├── auth.py             # JWT verification cu Supabase JWKS
    ├── storage.py          # Supabase Storage helper
    ├── routers/
    │   ├── minuta.py       # POST /api/minuta
    │   ├── mockup.py       # POST /api/mockup
    │   ├── scenarii.py     # POST /api/scenarii
    │   └── documents.py    # GET /api/documents
    ├── pipelines/
    │   ├── minuta_pipeline.py
    │   ├── mockup_pipeline.py
    │   └── scenarii_pipeline.py
    └── skills/
        └── mockup/         # Skill Excel→Word+HTML
```

## Arhitectură auth (IMPORTANT)

### De ce form nativ (nu React Server Action)
Next.js 16 + React 19's Server Actions folosesc `window.fetch` intern cu headerul `Next-Router-State-Tree` care conține caractere non-ASCII → eroare browser. Soluție: `<form method="POST" action="/api/auth/login">` → Route Handler server-side, zero JavaScript în browser.

### De ce middleware fără JWKS
`createRemoteJWKSet` din `jose` face network call la init în Edge Runtime → `MIDDLEWARE_INVOCATION_FAILED`. Soluție: middleware decode JWT payload local (doar verifică expiry), fără verificare semnătură. Securitatea reală e pe FastAPI care verifică semnătura ES256.

### De ce Supabase emite ES256 (nu HS256)
Supabase a schimbat algoritmul JWT la ES256 (asimetric). Cheia `SUPABASE_JWT_SECRET` nu mai e folosită pentru verificare în middleware.

## Flux auth complet
1. `POST /api/auth/login` (Route Handler) → `supabase.co/auth/v1/token` → cookie `auth-token` HttpOnly
2. **middleware.ts** → decode JWT → check expiry → allow/redirect
3. **Pagini** → client fetch → `/api/proxy/*` → Route Handler adaugă `Authorization: Bearer <token>` → FastAPI
4. **FastAPI** → verifică JWT ES256 cu Supabase JWKS → procesează

## Variabile de mediu Vercel (CRITICAL: setate cu `printf`, NU cu PowerShell echo)

```
NEXT_PUBLIC_SUPABASE_URL=https://zjmtqitymnrmmmsfoolp.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_zGrZT3emlDbPD7L5dEs2YA_pdOMLAyp
NEXT_PUBLIC_API_URL=https://ai-tools-backend-3vvz.onrender.com
SUPABASE_SERVICE_ROLE_KEY=<encrypted in Vercel>
SUPABASE_JWT_SECRET=<encrypted in Vercel - unused dar setat>
```

**ATENȚIE BOM**: Dacă env vars sunt setate prin PowerShell `echo "val" | vercel env add`, primesc BOM (U+FEFF = 65279) la poziția 0. Mereu folosiți `printf "val" | vercel env add` din Bash sau setați manual din Vercel Dashboard. Diagnosticul: `charCodeAt(0) === 65279` → BOM prezent.

## Variabile de mediu Render (backend)
```
SUPABASE_URL=https://zjmtqitymnrmmmsfoolp.supabase.co
SUPABASE_SERVICE_KEY=<service role key>
ANTHROPIC_API_KEY=<cheia Anthropic>
FRONTEND_URL=https://ai-tools-web-three.vercel.app
```

## Deploy

### Frontend (Vercel)
```bash
cd frontend
printf "valoare" | vercel env add NUME_VAR production   # fără BOM!
vercel --prod
```

### Backend (Render)
- Se deploy-ează automat din `backend/` folder când se face push pe `master`
- Service name: `ai-tools-backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Fiabilitate / Keep-alive (IMPORTANT — nu dezactivați)

Free tier-urile „mor" fără trafic: **Render adoarme după 15 min** (cold start 30-60s), iar **Supabase se PAUZEAZĂ după 7 zile fără activitate în DB** (login/storage picate; reactivare doar manuală din dashboard-ul Supabase).

Soluția activă (revizuită 2026-07-09):
- **Keep-alive Supabase (CRITIC) — ping DIRECT în Supabase, nu prin Render.** Un job cron-job.org (contul lui Daniel), la 6 ore, face `GET https://zjmtqitymnrmmmsfoolp.supabase.co/rest/v1/keepalive?select=id&limit=1` cu headerul `apikey: <cheia publishable>`. Interogarea pe tabelul `public.keepalive` (RLS: anon poate `select`) e activitate de DB → resetează timer-ul de pauză de 7 zile. Răspunde <1s cu `Content-Length` corect (fără cold start, fără „output too large"). Acesta e singurul mecanism care contează — Supabase pauzat = aplicație moartă.
- **Warm-up Render: DEZACTIVAT intenționat.** Pe Render free, cold start-ul (~44s) depășește timeout-ul de 30s al cron-job.org → orice ping pe Render rece eșuează (503/timeout) și, după 15 eșecuri consecutive, cron-job.org dezactivează jobul. NU reactivați jobul care pinguie `/health` pe Render — se va dezactiva iar. Consecința acceptată: utilizatorii prind un cold start de ~40s la prima folosire din zi (aplicația reîncearcă automat — UX lent, NU eroare). Singurul fix pentru zero cold start: Render Starter $7/lună.
- `/health` (GET+HEAD, cu ping Supabase intern) rămâne pentru verificări manuale, dar NU mai e ținta keep-alive-ului.
- Notificările email de la cron-job.org = monitorizare gratuită.

Verificare rapidă: `curl -H "apikey: <cheia>" "https://zjmtqitymnrmmmsfoolp.supabase.co/rest/v1/keepalive?select=id&limit=1"` (așteptat 200 + `[{"id":1}]`) și istoricul jobului din cron-job.org (trebuie verde).

## Useri Supabase
- **Admin**: `daniel.toma@totalsoft.ro` / `claudiu`
- Adăugare useri noi: pagina `/invite` din app (trimite email cu link, doar `@totalsoft.ro`)
- Sau manual din Supabase Dashboard → Authentication → Users → Add user

## Funcționalități implementate
- [x] Login/logout cu cookie HttpOnly
- [x] Middleware auth (JWT expiry check)
- [x] Proxy server-side pentru backend calls
- [x] Pagina Minută (upload Excel → Word + preview HTML)
- [x] Pagina Mockup (upload Excel → Word + HTML)
- [x] Pagina Scenarii (upload Excel → Excel output)
- [x] Pagina Repository (istoricul documentelor)
- [x] Invite useri (email link, doar @totalsoft.ro)
- [x] Auth callback pentru link-uri invite

## Probleme rezolvate (să nu se repete)

### 1. Non-ISO-8859-1 fetch header (browser)
React 19 Server Actions → `window.fetch` cu header non-ASCII. **Fix**: form HTML nativ + Route Handler.

### 2. JWT ES256 vs HS256 în middleware
Supabase emite ES256, middleware verifica HS256 → mereu redirect la login. **Fix**: decode local fără verificare semnătură.

### 3. BOM în env vars Vercel
PowerShell `echo` adaugă UTF-16 BOM → fetch header ByteString error. **Fix**: `printf` din Bash.

### 4. `createRemoteJWKSet` în Edge Runtime
Face network call la init → crash middleware. **Fix**: eliminat, folosit decode local.

### 5. Proxy fără try/catch
Backend down → exception neprinsă → 500 cu body gol → frontend `res.json()` fails. **Fix**: try/catch în proxy, returnează `{ detail: msg }` cu 502.
