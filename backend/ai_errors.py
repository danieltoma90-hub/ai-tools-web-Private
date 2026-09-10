# -*- coding: utf-8 -*-
"""Traduce eșecurile providerilor AI în ceva ce poate citi un consultant.

„Error code: 401 - {'type': 'error', ...}" nu spune nimănui ce are de făcut.
Mesajele de aici spun exact asta, iar diagnosticul complet (care cheie, ce stare)
rămâne la /diagnostics/providers.
"""
from __future__ import annotations


def mesaj_eroare_ai(exc: Exception, provider: str = "Claude") -> str:
    status = getattr(exc, "status_code", None)
    text = str(exc).lower()

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
    if status == 404 and "model" in text:
        return f"modelul {provider} configurat pe server nu este disponibil."
    if status == 413 or "too large" in text:
        return "specificația este prea mare pentru o singură cerere."
    return f"{provider} nu a răspuns corect ({type(exc).__name__}: {exc})."
