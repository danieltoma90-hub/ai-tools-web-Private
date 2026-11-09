"""Diagnostic pentru cheia Claude — singurul furnizor AI al site-ului.

Nu e un simplu ping: cererile trec pe ACELAȘI drum ca generările reale
(`claude.py` — modelul, efortul, fallback-ul, antetul beta), deci un „funcțional"
aici înseamnă că și minuta, scenariile și restul vor merge. Proba de cache
verifică, pe lângă, că încălzirea cu `max_tokens=0` și citirea din cache merg
pe contul real. Costul: sub un cent per verificare.

NU expune cheia — doar un indiciu (primele/ultimele caractere), ca să se poată
verifica dacă pe server e cheia corectă.
"""
import os

from fastapi import APIRouter, Depends

import claude
from auth import verify_token

router = APIRouter()

# ~1.000 de tokeni: peste pragul minim de cache al modelelor curente (512).
_PREFIX_PROBA = (
    "Acest text există doar ca să verifice cache-ul de prompt al serverului. "
    "Un cache e o potrivire de prefix: dacă două cereri încep cu aceiași octeți, "
    "a doua citește partea comună din cache, la o fracțiune din preț. "
) * 24


def _hint(key: str) -> str:
    if not key:
        return ""
    # acelasi format ca in consola Anthropic (primele 16 + ultimele 4),
    # ca sa se poata compara direct cu lista de chei
    return f"{key[:16]}…{key[-4:]}"


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
    if status == 403:
        return "model_nepermis", (
            "Cheia nu are acces la modelul configurat. Verifică în consola Anthropic "
            "accesul organizației, sau pune alt model în CLAUDE_MODEL pe server."
        )
    if status == 404 and "model" in low:
        return "model_indisponibil", f"Cheia e validă, dar modelul nu e disponibil: {msg}"
    return "eroare", msg or f"Răspuns neașteptat (HTTP {status})."


def _din_exceptie(e: Exception) -> tuple[str, str]:
    if isinstance(e, claude.RefuzModel):
        return "eroare", f"Cererea de test a fost refuzată (filtru: {e.categorie})."
    if isinstance(e, RuntimeError) and "ANTHROPIC_API_KEY" in str(e):
        return "lipsa", "ANTHROPIC_API_KEY nu e setată pe server."
    status = getattr(e, "status_code", None)
    if status is not None:
        corp = getattr(e, "body", None)
        return _classify(status, corp if isinstance(corp, dict) else {"message": str(e)})
    return "eroare", f"Nu s-a putut contacta API-ul: {type(e).__name__}: {e}"


async def _check_anthropic() -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    baza = {"provider": "Claude (Anthropic)", "configured": bool(key)}
    if not key:
        return {**baza, "state": "lipsa", "message": "ANTHROPIC_API_KEY nu e setată pe server."}
    baza["key_hint"] = _hint(key)

    detalii = [
        f"Model: {claude.model()}",
        f"Fallback la refuz: {'activ' if claude.fallback_activ() else 'oprit'}",
    ]
    try:
        r = await claude.raspunde("Răspunde doar cu: OK", max_tokens=2048, efort="low")
        detalii.append(f"Răspuns de test: {r.text.strip()[:40] or '(gol)'}")
    except Exception as e:
        state, message = _din_exceptie(e)
        return {**baza, "state": state, "message": message, "detalii": detalii}

    # Cache: încălzire, apoi o cerere care ar trebui să citească prefixul.
    try:
        await claude.incalzeste_cache(_PREFIX_PROBA, efort="low")
        r = await claude.raspunde(
            "Răspunde doar cu: OK", max_tokens=2048, efort="low", prefix_cache=_PREFIX_PROBA,
        )
        citit = getattr(r.usage, "cache_read_input_tokens", 0) or 0
        detalii.append(
            f"Cache: funcționează ({citit} tokeni citiți din cache)" if citit
            else "Cache: NU a citit nimic — generările plătesc transcriptul întreg"
        )
    except Exception as e:
        detalii.append(f"Cache: proba a eșuat ({_din_exceptie(e)[1]})")

    return {**baza, "state": "ok", "message": "Cheia funcționează.", "detalii": detalii}


@router.get("/diagnostics/providers")
async def check_providers(user=Depends(verify_token)):
    """Starea reală a cheii Claude, pe drumul generărilor reale."""
    return {"providers": [await _check_anthropic()]}
