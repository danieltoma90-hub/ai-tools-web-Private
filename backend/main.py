from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from auth import get_supabase
from routers import minuta, mockup, scenarii, documents, uploads

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
    except Exception as e:
        supabase_status = f"eroare: {type(e).__name__}"
    return JSONResponse(
        {"status": "ok", "supabase": supabase_status},
        headers={"Cache-Control": "no-transform"},
    )
