# -*- coding: utf-8 -*-
"""Un singur drum spre Claude pentru tot site-ul.

Toate modulele — Minută, Scenarii, Mockup, Scop CORE, Training, „On this day" —
trec pe aici. Motivul e mai mult decât ordinea: pe Claude Opus 5.5 gândirea e
mereu pornită, iar răspunsul poate începe cu un bloc de gândire. Codul care
citea `resp.content[0].text` ar fi primit text gol. Regulile modelului (efort,
refuzuri, fallback, cache) stau aici o singură dată, nu în șapte locuri.

Comutatoare din setările serverului (Render → Environment), fără deploy:
  CLAUDE_MODEL      implicit claude-opus-5-5
  CLAUDE_FALLBACKS  „default" (implicit): un refuz al filtrelor de siguranță
                    se reia automat pe alt model, pe server; „off" îl oprește.
                    Pune „off" dacă CLAUDE_MODEL e un model care nu acceptă
                    fallback (de exemplu claude-sonnet-4-6).
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MODEL_IMPLICIT = "claude-opus-5-5"
BETA_FALLBACK = "server-side-fallback-2026-07-01"

_client = None


def model() -> str:
    return (os.environ.get("CLAUDE_MODEL") or "").strip() or MODEL_IMPLICIT


def fallback_activ() -> bool:
    return (os.environ.get("CLAUDE_FALLBACKS") or "default").strip().lower() != "off"


def client():
    """Un singur client per proces, ca la Supabase."""
    global _client
    if _client is None:
        cheie = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not cheie:
            raise RuntimeError("ANTHROPIC_API_KEY lipsă pe server")
        from anthropic import AsyncAnthropic

        _client = AsyncAnthropic(api_key=cheie)
    return _client


def reset_client() -> None:
    global _client
    _client = None


class RefuzModel(Exception):
    """Filtrele de siguranță au refuzat cererea — și pe modelul de rezervă, dacă e activ."""

    def __init__(self, categorie: str | None):
        self.categorie = categorie
        super().__init__(f"refuz ({categorie or 'fără categorie'})")


@dataclass
class Raspuns:
    text: str
    stop_reason: str | None
    usage: Any = None

    @property
    def trunchiat(self) -> bool:
        """Răspunsul s-a oprit la `max_tokens` — probabil incomplet."""
        return self.stop_reason == "max_tokens"


def _continut(intrebare: str, prefix_cache: str | None) -> str | list[dict]:
    """Mesajul utilizatorului. Cu `prefix_cache`, partea comună mai multor cereri
    stă prima și poartă marcajul de cache, iar întrebarea propriu-zisă vine după —
    un cache e o potrivire de prefix, deci ce diferă trebuie să stea la coadă."""
    if prefix_cache is None:
        return intrebare
    blocuri: list[dict] = [
        {"type": "text", "text": prefix_cache, "cache_control": {"type": "ephemeral"}},
    ]
    if intrebare:
        blocuri.append({"type": "text", "text": intrebare})
    return blocuri


def _parametri(
    *, continut, system: str | None, max_tokens: int, efort: str, cu_fallback: bool
) -> dict:
    p: dict = {
        "model": model(),
        "max_tokens": max_tokens,
        # Efortul e singurul control al gândirii pe Opus 5.5 și implicit e „medium";
        # îl spunem mereu explicit, ca o schimbare de implicit să nu ne schimbe costul.
        "output_config": {"effort": efort},
        "messages": [{"role": "user", "content": continut}],
    }
    if system:
        p["system"] = system
    if cu_fallback and fallback_activ():
        p["betas"] = [BETA_FALLBACK]
        p["fallbacks"] = "default"
    return p


def text_din(mesaj: Any) -> str:
    """Textul răspunsului, citit după tipul blocului, nu după poziție."""
    return "".join(
        getattr(b, "text", "") for b in (mesaj.content or []) if getattr(b, "type", None) == "text"
    )


def _jurnalizeaza(mesaj: Any) -> None:
    u = getattr(mesaj, "usage", None)
    if u is None:
        return
    logger.info(
        "claude %s: intrare=%s iesire=%s cache_citit=%s cache_scris=%s stop=%s",
        getattr(mesaj, "model", model()),
        getattr(u, "input_tokens", None),
        getattr(u, "output_tokens", None),
        getattr(u, "cache_read_input_tokens", None),
        getattr(u, "cache_creation_input_tokens", None),
        getattr(mesaj, "stop_reason", None),
    )


async def raspunde(
    intrebare: str,
    *,
    max_tokens: int,
    efort: str = "medium",
    system: str | None = None,
    prefix_cache: str | None = None,
) -> Raspuns:
    """Un apel Claude, prin streaming.

    Streaming-ul nu e pentru afișare: cu gândirea pornită, un răspuns lung poate
    depăși limita de 10 minute a unui apel obișnuit, pe care SDK-ul o refuză din
    start pentru valori mari de `max_tokens`.
    """
    params = _parametri(
        continut=_continut(intrebare, prefix_cache),
        system=system, max_tokens=max_tokens, efort=efort, cu_fallback=True,
    )
    async with client().beta.messages.stream(**params) as stream:
        mesaj = await stream.get_final_message()

    _jurnalizeaza(mesaj)
    if mesaj.stop_reason == "refusal":
        detalii = getattr(mesaj, "stop_details", None)
        raise RefuzModel(getattr(detalii, "category", None))
    if mesaj.stop_reason == "max_tokens":
        logger.warning("claude: răspuns oprit la max_tokens=%s", max_tokens)
    return Raspuns(text_din(mesaj), mesaj.stop_reason, getattr(mesaj, "usage", None))


async def incalzeste_cache(
    prefix: str, *, efort: str = "medium", system: str | None = None
) -> Any:
    """Scrie în cache prefixul comun, înaintea cererilor paralele care îl folosesc.

    Un cache devine citibil abia după ce primul răspuns începe să curgă, așa că N
    cereri pornite deodată plătesc toate prețul întreg. O cerere cu `max_tokens=0`
    scrie cache-ul fără să genereze nimic; cererile de după îl citesc.

    Efortul și sistemul trebuie să fie identice cu ale cererilor reale — fac parte
    din ce se pune în cache. Totul e „best effort": dacă încălzirea eșuează,
    cererile merg mai departe fără cache, adică exact ca înainte. Întoarce
    `usage`, ca proba din Diagnostic să poată arăta ce s-a scris.
    """
    from anthropic import BadRequestError

    for cu_fallback in (True, False):
        params = _parametri(
            continut=_continut("", prefix), system=system,
            max_tokens=0, efort=efort, cu_fallback=cu_fallback,
        )
        try:
            mesaj = await client().beta.messages.create(**params)
            return getattr(mesaj, "usage", None)
        except BadRequestError as e:
            # Dacă API-ul nu acceptă fallback la o cerere fără răspuns, reîncercăm fără.
            if cu_fallback and "fallback" in str(e).lower():
                continue
            logger.warning("claude: încălzirea cache-ului refuzată: %s", e)
            return None
        except Exception as e:
            logger.warning("claude: încălzirea cache-ului a eșuat: %s", e)
            return None
    return None


def parse_json(text: str) -> Any:
    """JSON-ul din răspuns, chiar dacă vine în bloc ```json, cu text în jur sau ciobit."""
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    candidat = m.group(1) if m else text
    try:
        return json.loads(candidat)
    except json.JSONDecodeError:
        pass

    bloc = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", candidat)
    if bloc:
        try:
            return json.loads(bloc.group(1))
        except json.JSONDecodeError:
            pass

    from json_repair import repair_json

    reparat = repair_json(bloc.group(1) if bloc else candidat)
    if reparat and reparat.strip() not in ("", "null", '""'):
        return json.loads(reparat)
    raise ValueError(f"Răspuns care nu conține JSON: {text[:200]}")
