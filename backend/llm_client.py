"""Client LLM provider-agnostic pentru mockup si scenarii.

Provider implicit: Mistral La Plateforme (tier gratuit "Experiment").
Implementare curenta: doar Mistral. Clientul e izolat aici ca un provider nou sa nu atinga pipeline-urile.
NU se foloseste pentru minuta (aceea ramane pe Groq).
"""
import asyncio
import json
import os
import time
from datetime import date

import httpx

ROMANIAN_CHARS_PER_TOKEN = 2.2
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MIN_CALL_INTERVAL_S = 1.5  # free tier ~1 req/sec
RETRY_DELAYS = [2, 8, 20]

# Transport injectabil pentru teste (httpx.MockTransport)
TRANSPORT: httpx.AsyncBaseTransport | None = None

_throttle_lock = asyncio.Lock()
_last_call = 0.0

# Contor zilnic in-memory — protectie soft, se reseteaza la restart Render
_usage: dict = {"day": "", "tokens": 0}


def _model() -> str:
    return os.environ.get("MISTRAL_MODEL", "mistral-large-latest")


def _api_key() -> str:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY lipsă pe server")
    return key


def daily_budget() -> int:
    return int(os.environ.get("LLM_DAILY_TOKEN_BUDGET", "500000"))


def _usage_today() -> int:
    today = date.today().isoformat()
    if _usage["day"] != today:
        _usage["day"] = today
        _usage["tokens"] = 0
    return _usage["tokens"]


def add_usage(tokens: int) -> None:
    _usage_today()
    _usage["tokens"] += tokens


def remaining_budget() -> int:
    return max(0, daily_budget() - _usage_today())


def estimate_tokens(text: str) -> int:
    return round(len(text) / ROMANIAN_CHARS_PER_TOKEN)


def parse_json(content: str) -> dict:
    """JSON robust: accepta si continut impachetat in ```json ... ```."""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


async def chat(
    system: str,
    user: str,
    max_tokens: int = 4000,
    json_mode: bool = True,
) -> str:
    """Un apel chat spre providerul curent, cu throttle si retry pe 429/5xx."""
    global _last_call
    api_key = _api_key()
    payload: dict = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {api_key}"}

    async with _throttle_lock:
        wait = MIN_CALL_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()

    async with httpx.AsyncClient(timeout=180, transport=TRANSPORT) as client:
        last_status = 0
        for attempt in range(len(RETRY_DELAYS) + 1):
            resp = await client.post(MISTRAL_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                add_usage(int(usage.get("total_tokens", max_tokens)))
                return data["choices"][0]["message"]["content"]
            last_status = resp.status_code
            if resp.status_code in (429, 500, 502, 503) and attempt < len(RETRY_DELAYS):
                await asyncio.sleep(RETRY_DELAYS[attempt])
                continue
            break
    raise RuntimeError(f"Eroare LLM ({last_status}) — reîncercările au fost epuizate")
