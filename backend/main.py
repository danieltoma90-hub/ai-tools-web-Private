from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from routers import minuta, mockup, scenarii, documents

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


@app.get("/health")
def health():
    return {"status": "ok"}
