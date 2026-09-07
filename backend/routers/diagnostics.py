"""Diagnostic pentru cheile de API ale providerilor.

Face cate un apel minimal (max_tokens=1, cost neglijabil) si raporteaza starea
reala a fiecarei chei. NU expune cheia — doar un indiciu (primele/ultimele
caractere), ca sa se poata verifica daca pe server e cheia corecta.
"""
import os

import httpx
from fastapi import APIRouter, Depends

from auth import verify_token

router = APIRouter()

TIMEOUT = 30.0


def _hint(key: str) -> str:
    if not key:
        return ""
    return f"{key[:12]}…{key[-4:]} ({len(key)} caractere)"


def _classify(status: int, body: dict) -> tuple[str, str]:
    """(stare, mesaj prietenos) pe baza raspunsului providerului."""
    err = (body.get("error") or {})
    msg = err.get("message") or body.get("message") or ""
    low = msg.lower()

    if status == 200:
        return "ok", "Cheia funcționează."
    if status == 401 or "authentication" in low or "invalid api key" in low or "api key is invalid" in low:
        return "cheie_invalida", (
            "Cheia este invalidă sau a fost ștearsă/revocată. "
            "Generează o cheie nouă în consola providerului și actualizeaz-o pe server."
        )
    if "credit balance is too low" in low or "billing" in low or status == 402:
        return "fara_credit", (
            "Cheia e validă, dar organizația din care face parte nu are credite. "
            "Adaugă credite EXACT în organizația care deține cheia."
        )
    if status == 429:
        return "limita_atinsa", "Limita de utilizare a fost atinsă (rate limit / cotă zilnică)."
    if status == 404 and "model" in low:
        return "model_indisponibil", f"Cheia e validă, dar modelul nu e disponibil: {msg}"
    return "eroare", msg or f"Răspuns neașteptat (HTTP {status})."


async def _check_anthropic(client: httpx.AsyncClient) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return {"provider": "Claude (Anthropic)", "configured": False,
                "state": "lipsa", "message": "ANTHROPIC_API_KEY nu e setată pe server."}
    try:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 1,
                  "messages": [{"role": "user", "content": "hi"}]},
        )
        state, message = _classify(r.status_code, r.json() if r.content else {})
    except Exception as e:
        state, message = "eroare", f"Nu s-a putut contacta API-ul: {type(e).__name__}"
    return {"provider": "Claude (Anthropic)", "configured": True,
            "key_hint": _hint(key), "state": state, "message": message}


async def _check_groq(client: httpx.AsyncClient) -> dict:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return {"provider": "Groq (gratuit)", "configured": False,
                "state": "lipsa", "message": "GROQ_API_KEY nu e setată pe server."}
    try:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "openai/gpt-oss-120b", "max_tokens": 1,
                  "messages": [{"role": "user", "content": "hi"}]},
        )
        state, message = _classify(r.status_code, r.json() if r.content else {})
    except Exception as e:
        state, message = "eroare", f"Nu s-a putut contacta API-ul: {type(e).__name__}"
    return {"provider": "Groq (gratuit)", "configured": True,
            "key_hint": _hint(key), "state": state, "message": message}


async def _check_mistral(client: httpx.AsyncClient) -> dict:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        return {"provider": "Mistral (mockup)", "configured": False,
                "state": "lipsa", "message": "MISTRAL_API_KEY nu e setată pe server."}
    try:
        r = await client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": os.environ.get("MISTRAL_MODEL", "mistral-large-latest"),
                  "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
        )
        state, message = _classify(r.status_code, r.json() if r.content else {})
    except Exception as e:
        state, message = "eroare", f"Nu s-a putut contacta API-ul: {type(e).__name__}"
    return {"provider": "Mistral (mockup)", "configured": True,
            "key_hint": _hint(key), "state": state, "message": message}


@router.get("/diagnostics/providers")
async def check_providers(user=Depends(verify_token)):
    """Starea reală a cheilor de API — un apel minimal per provider."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        return {
            "providers": [
                await _check_anthropic(client),
                await _check_groq(client),
                await _check_mistral(client),
            ]
        }
