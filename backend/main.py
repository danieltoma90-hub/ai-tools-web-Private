from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


@app.get("/health")
def health():
    """Keep-alive: pingul extern (cron-job.org) tine Render treaz, iar apelul
    Supabase de mai jos reseteaza timer-ul de pauza al proiectului free (7 zile).
    Esecul Supabase nu pica pingul — vrem activitate + vizibilitate, nu alarme false."""
    try:
        get_supabase().storage.list_buckets()
        supabase_status = "ok"
    except Exception as e:
        supabase_status = f"eroare: {type(e).__name__}"
    return {"status": "ok", "supabase": supabase_status}
