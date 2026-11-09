# -*- coding: utf-8 -*-
"""Traduce eșecurile în ceva ce poate citi un consultant.

„Error code: 401 - {'type': 'error', ...}" nu spune nimănui ce are de făcut.
Mesajele de aici spun exact asta, iar diagnosticul complet (care cheie, ce stare)
rămâne la /diagnostics/providers.

Două feluri de eșec, tratate diferit: cele ale lui Claude (cheie, credit, refuz,
rețea) se traduc aici; cele ale documentului (un .docx stricat, o specificație
fără text) au deja mesaje scrise pentru utilizator și trec neschimbate — altfel
ar ieși „Claude nu a răspuns corect" pentru un fișier greșit.
"""
from __future__ import annotations


def e_eroare_ai(exc: Exception) -> bool:
    """Eșecul vine de la Claude (sau de la configurarea lui), nu de la document."""
    from claude import RefuzModel

    if isinstance(exc, RefuzModel):
        return True
    if isinstance(exc, RuntimeError) and "anthropic_api_key" in str(exc).lower():
        return True
    try:
        import anthropic

        return isinstance(exc, anthropic.APIError)
    except ImportError:
        return False


def mesaj_eroare_ai(exc: Exception, provider: str = "Claude") -> str:
    from claude import RefuzModel

    if isinstance(exc, RefuzModel):
        return (
            f"{provider} a refuzat cererea (filtru de siguranță: "
            f"{exc.categorie or 'fără categorie'}), inclusiv pe modelul de rezervă. "
            "Verifică dacă documentul conține ceva ce poate fi luat drept conținut sensibil."
        )
    status = getattr(exc, "status_code", None)
    text = str(exc).lower()
    if isinstance(exc, RuntimeError) and "anthropic_api_key" in text:
        return "cheia API Claude lipsește pe server. Adaug-o în setările Render (ANTHROPIC_API_KEY)."

    if status == 401 or "authentication" in text or "api key is invalid" in text:
        return (
            f"cheia API {provider} este invalidă sau a fost revocată. "
            "Generează una nouă în consola providerului și înlocuiește-o pe server."
        )
    if status == 402 or "credit balance is too low" in text or "billing" in text:
        return (
            f"cheia API {provider} nu are credite disponibile. "
            "Adaugă credite exact în organizația care deține cheia."
        )
    if status == 429 or "rate limit" in text:
        return f"limita de utilizare {provider} a fost atinsă. Reia peste câteva minute."
    if status == 529 or "overloaded" in text:
        return f"{provider} e suprasolicitat în acest moment. Reia peste câteva minute."
    if status == 404 and "model" in text:
        return f"modelul {provider} configurat pe server nu este disponibil."
    if status == 413 or "too large" in text:
        return "documentul este prea mare pentru o singură cerere."
    if status is not None and status >= 500:
        return f"{provider} a avut o eroare temporară (HTTP {status}). Reia peste câteva minute."
    if status is None and ("connection" in text or "timeout" in text or "timed out" in text):
        return f"nu s-a putut contacta {provider} (rețea sau timp depășit). Reia generarea."
    return f"{provider} nu a răspuns corect ({type(exc).__name__}: {exc})."


def mesaj_pentru_utilizator(exc: Exception) -> str:
    """Mesajul de arătat pentru orice eșec al unei generări."""
    if e_eroare_ai(exc):
        mesaj = mesaj_eroare_ai(exc)
        return mesaj[:1].upper() + mesaj[1:]
    return str(exc) or type(exc).__name__
