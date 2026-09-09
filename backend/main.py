from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from auth import get_supabase
from routers import minuta, mockup, scenarii, documents, uploads, diagnostics, training

load_dotenv()

app = FastAPI(title="AI Tools Web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(minuta.router, prefix="/api")
app.include_router(mockup.router, prefix="/api")
app.include_router(scenarii.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(diagnostics.router, prefix="/api")
app.include_router(training.router, prefix="/api")


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    """Keep-alive: pingul extern (cron-job.org) tine Render treaz, iar apelul
    Supabase de mai jos reseteaza timer-ul de pauza al proiectului free (7 zile).
    Esecul Supabase nu pica pingul — vrem activitate + vizibilitate, nu alarme false.

    Acceptam si HEAD (raspuns fara corp) pentru pingere; `Cache-Control: no-transform`
    cere Cloudflare-ului sa nu re-encodeze chunked (altfel cron-job.org da fals
    'output too large' pe un raspuns de 31 octeti fara Content-Length)."""
    try:
        get_supabase().storage.list_buckets()
        supabase_status = "ok"
        detail = None
    except Exception as e:
        supabase_status = f"eroare: {type(e).__name__}"
        # Fara Supabase, NICIUN utilizator nu se poate autentifica: verify_token
        # esueaza si toata lumea e data afara imediat dupa login. Cauza tipica e
        # o cheie rotita/revocata, iar mesajul brut ("StorageApiError") nu spune
        # asta — de aceea endpoint-ul public, singurul accesibil cand nu te poti
        # loga, o numeste explicit.
        text = str(e).lower()
        if "unregistered" in text or "not registered" in text or "invalid compact jws" in text:
            detail = (
                "SUPABASE_SERVICE_KEY nu este înregistrată pentru acest proiect "
                "(rotită sau dintr-un alt proiect). Înlocuiește-o pe server cu "
                "cheia secret curentă din Supabase → Settings → API Keys."
            )
        elif "jwt" in text or "unauthorized" in text or "401" in text:
            detail = (
                "SUPABASE_SERVICE_KEY este respinsă de Supabase. Verifică valoarea "
                "de pe server (Settings → API Keys în Supabase)."
            )
        else:
            detail = f"Supabase nu răspunde corect: {e}"

    body = {"status": "ok", "supabase": supabase_status}
    if detail:
        body["detail"] = detail
    return JSONResponse(body, headers={"Cache-Control": "no-transform"})
