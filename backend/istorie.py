# -*- coding: utf-8 -*-
"""Evenimentele zilei pentru ecranul de asteptare.

Istoria nu se schimba: ce s-a intamplat pe 10 septembrie va fi la fel si la
anul. De aceea fiecare zi din calendar se calculeaza O SINGURA DATA, vreodata,
iar rezultatul sta in Supabase. Peste un an, costul e zero.

Selectia o face Claude — „care dintre astea au schimbat lumea, bune sau rele" —
cu un ecou de siguranta pe cuvinte-cheie daca modelul nu raspunde: mai bine o
lista aproximativa decat un ecran gol.
"""
from __future__ import annotations

import asyncio
import json
import os
import re

import httpx

from storage import cache_citeste, cache_scrie

WIKIPEDIA = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected"
# Wikipedia respinge cererile fara user-agent identificabil.
UA = "AI-Tools-Web/1.0 (training si minute pentru consultanti ERP)"

MODEL = os.environ.get("ISTORIE_CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_EVENIMENTE = 6
CACHE_VERSIUNE = "v1"

_lacate: dict[str, asyncio.Lock] = {}


def _cale_cache(luna: int, zi: int) -> str:
    return f"onthisday/{CACHE_VERSIUNE}/{luna:02d}-{zi:02d}.json"


async def _din_wikipedia(luna: int, zi: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{WIKIPEDIA}/{luna:02d}/{zi:02d}",
            headers={"Accept": "application/json", "User-Agent": UA},
        )
        r.raise_for_status()
        brute = r.json().get("selected", [])

    return [
        {"an": e["year"], "text": e["text"].strip()}
        for e in brute
        if isinstance(e.get("year"), int) and isinstance(e.get("text"), str) and e["text"].strip()
    ]


PROMPT = """Primești evenimentele pe care Wikipedia le-a selectat pentru o zi din calendar.

Alege-le pe cele care au influențat cu adevărat omenirea — la scara lumii, nu a
unei localități sau a unei bresle. Bune și rele deopotrivă: și primul zbor uman
în spațiu, și bomba de la Hiroshima.

Nu alege: nașteri, decese, sport, filme, muzică, televiziune, fapte diverse,
accidente aviatice sau feroviare, bătălii locale fără urmări, aniversări.

Alege cel mult {maxim}, în ordinea importanței. Dacă ziua nu are decât
evenimente mărunte, alege mai puține sau niciunul — o listă scurtă și bună e
mai valoroasă decât una lungă și diluată.

Răspunde DOAR cu JSON: {{"alese": [indici, în ordinea importanței]}}

Evenimentele:
{lista}"""


async def _selectie_claude(evenimente: list[dict], api_key: str) -> list[dict]:
    from anthropic import AsyncAnthropic

    lista = "\n".join(
        f"[{i}] {e['an']}: {e['text']}" for i, e in enumerate(evenimente)
    )
    client = AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": PROMPT.format(maxim=MAX_EVENIMENTE, lista=lista),
        }],
    )

    text = resp.content[0].text
    bloc = re.search(r"\{[\s\S]*\}", text)
    date = json.loads(bloc.group(0) if bloc else text)

    alese = []
    for i in date.get("alese", [])[:MAX_EVENIMENTE]:
        if isinstance(i, int) and 0 <= i < len(evenimente):
            alese.append(evenimente[i])
    return alese


# Plasa de siguranta: aceleasi cuvinte-cheie ponderate folosite inainte de a
# aduce Claude in poveste. Nu judeca contextul, dar nu lasa ecranul gol.
_EXCLUSE = re.compile(
    r"\b(was born|were born|\bb\.\s*\d{4}|died|death of|football|soccer|olympic|"
    r"championship|album|film|television|episode|video game|robbery|asteroid|"
    r"flight \d|airliner|airlines|aircraft crashed|plane crashed|derailed)",
    re.I,
)
_PUTERNICE = re.compile(
    r"\b(world war|treaty of|armistice|declared independence|constitution|"
    r"revolution|abolish|apartheid|holocaust|genocide|first human|first successful|"
    r"moon|spacecraft|vaccine|pandemic|atomic bomb|nuclear weapon|united nations|"
    r"world wide web|the internet|fall of|collapse of)",
    re.I,
)
_MEDII = re.compile(
    r"\b(treaty|surrender|liberated|annexed|coup|overthrew|founded|established|"
    r"ratified|proclaimed|discovered|invented|launched|satellite|earthquake|"
    r"tsunami|eruption|famine|epidemic|massacre|civil war|republic of)",
    re.I,
)


def _selectie_pe_cuvinte(evenimente: list[dict]) -> list[dict]:
    def scor(text: str) -> int:
        if _EXCLUSE.search(text):
            return -1
        tari = len({m.group(0).lower() for m in _PUTERNICE.finditer(text)})
        medii = len({m.group(0).lower() for m in _MEDII.finditer(text)})
        return tari * 2 + medii

    cotate = sorted(
        ((scor(e["text"]), e) for e in evenimente), key=lambda x: -x[0]
    )
    alese = [e for s, e in cotate if s >= 2]
    if len(alese) < 3:
        alese = [e for s, e in cotate if s >= 1]
    return alese[:MAX_EVENIMENTE]


async def evenimentele_zilei(luna: int, zi: int, api_key: str = "") -> list[dict]:
    """Evenimentele importante ale zilei. Nu ridica exceptii: la orice esec,
    intoarce lista goala si ecranul de asteptare ramane fara sectiunea asta."""
    cale = _cale_cache(luna, zi)

    din_cache = cache_citeste(cale)
    if din_cache:
        try:
            return json.loads(din_cache)
        except (ValueError, TypeError):
            pass  # cache stricat — il recalculam

    # Doua cereri simultane pentru aceeasi zi nu au voie sa plateasca doua apeluri.
    lacat = _lacate.setdefault(cale, asyncio.Lock())
    async with lacat:
        din_cache = cache_citeste(cale)
        if din_cache:
            try:
                return json.loads(din_cache)
            except (ValueError, TypeError):
                pass

        try:
            toate = await _din_wikipedia(luna, zi)
        except Exception:
            return []
        if not toate:
            return []

        alese: list[dict] = []
        if api_key:
            try:
                alese = await _selectie_claude(toate, api_key)
            except Exception:
                alese = []
        if not alese:
            alese = _selectie_pe_cuvinte(toate)

        cache_scrie(cale, json.dumps(alese, ensure_ascii=False).encode("utf-8"))
        return alese
