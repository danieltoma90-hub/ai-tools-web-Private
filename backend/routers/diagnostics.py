"""Diagnostic pentru cheia Claude — singurul furnizor AI al site-ului.

Nu e un simplu ping: cererile trec pe ACELAȘI drum ca generările reale
(`claude.py` — modelul, efortul, fallback-ul, antetul beta), deci un „funcțional"
aici înseamnă că și minuta, scenariile și restul vor merge. Proba de cache
verifică, pe lângă, că încălzirea cu `max_tokens=0` și citirea din cache merg
pe contul real. Costul: câțiva cenți per verificare (proba de cache scrie ~6.000 de tokeni).

NU expune cheia — doar un indiciu (primele/ultimele caractere), ca să se poată
verifica dacă pe server e cheia corectă.
"""
import os

from fastapi import APIRouter, Depends

import claude
from auth import verify_token

router = APIRouter()

# ~6.000 de tokeni. Documentația dă 512 tokeni ca prag minim de cache pentru Opus 5.5,
# dar avertizează să nu te bazezi pe valoare, iar modele apropiate au 4.096. O probă
# sub prag ar spune „nu" chiar dacă la minută (transcrieri de 44–86 mii de tokeni)
# cache-ul merge — exact ce a făcut prima variantă, de ~2.000 de tokeni.
_PREFIX_PROBA = (
    "Acest text există doar ca să verifice cache-ul de prompt al serverului. "
    "Un cache e o potrivire de prefix: dacă două cereri încep cu aceiași octeți, "
    "a doua citește partea comună din cache, la o fracțiune din preț. "
) * 80


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

    # Cache: încălzire, apoi o cerere care ar trebui să citească prefixul. Fiecare pas
    # își spune rezultatul — un „nu" fără motiv nu poate fi reparat.
    try:
        inc = await claude.incalzeste_cache(_PREFIX_PROBA, efort="low")
        if inc.eroare and not inc.usage:
            detalii.append(f"Încălzire: refuzată — {inc.eroare[:300]}")
        else:
            detalii.append(
                f"Încălzire: {inc.scris} tokeni scriși în cache "
                f"({'cu' if inc.cu_fallback else 'fără'} fallback)"
                + (f"; varianta cu fallback refuzată: {inc.eroare[:200]}" if inc.eroare else "")
            )

        r = await claude.raspunde(
            "Răspunde doar cu: OK", max_tokens=2048, efort="low", prefix_cache=_PREFIX_PROBA,
        )
        u = r.usage
        citit = getattr(u, "cache_read_input_tokens", 0) or 0
        scris = getattr(u, "cache_creation_input_tokens", 0) or 0
        necache = getattr(u, "input_tokens", 0) or 0
        detalii.append(f"Cererea reală: {citit} citiți din cache · {scris} scriși · {necache} fără cache")
        if citit:
            detalii.append(f"Cache: funcționează ({citit} tokeni citiți din cache)")
        elif scris:
            # Cererea reală a scris ea însăși cache-ul: încălzirea nu a pus nimic
            # unde o caută cererile reale (prefix diferit sau încălzire refuzată).
            detalii.append("Cache: NU a citit nimic — cererea reală a rescris cache-ul, "
                           "deci încălzirea nu se potrivește cu cererile reale")
        else:
            detalii.append("Cache: NU a citit nimic — nici n-a scris; prefixul e probabil sub pragul minim")
    except Exception as e:
        detalii.append(f"Cache: proba a eșuat ({_din_exceptie(e)[1]})")

    return {**baza, "state": "ok", "message": "Cheia funcționează.", "detalii": detalii}


@router.get("/diagnostics/providers")
async def check_providers(user=Depends(verify_token)):
    """Starea reală a cheii Claude, pe drumul generărilor reale. Costă câțiva cenți,
    care apar în consumul administratorului ca modulul „diagnostic"."""
    import consum
    from acces import email_din

    with consum.masoara("diagnostic", email_din(user)):
        return {"providers": [await _check_anthropic()]}
