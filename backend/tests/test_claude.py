# -*- coding: utf-8 -*-
"""Drumul unic spre Claude, verificat la nivel HTTP, cu SDK-ul real.

Nu există o cheie API validă pe mașina de dezvoltare, deci API-ul nu poate fi
chemat de aici. Testele de mai jos interceptează cererea înainte să plece și
verifică două lucruri pe care altfel le-am afla abia în producție:
  - că SDK-ul acceptă parametrii noi și îi pune pe fir în forma documentată
    (model, efort, fallback, antetul beta, marcajul de cache, max_tokens=0);
  - că un răspuns care începe cu un bloc de gândire e citit corect — exact
    cazul în care vechiul `resp.content[0].text` întorcea text gol.
"""
import json

import httpx2 as httpx  # SDK 2.x foloseste httpx2, nu httpx
import pytest

import claude

# funcțiile reale, înainte ca bariera din conftest să le înlocuiască
RASPUNDE_REAL, INCALZESTE_REAL = claude.raspunde, claude.incalzeste_cache


@pytest.fixture(autouse=True)
def _drumul_real(monkeypatch):
    monkeypatch.setattr(claude, "raspunde", RASPUNDE_REAL)
    monkeypatch.setattr(claude, "incalzeste_cache", INCALZESTE_REAL)


def _sse(evenimente: list[dict]) -> bytes:
    return "".join(
        f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in evenimente
    ).encode()


def _flux_raspuns(text: str, stop: str = "end_turn", categorie: str | None = None) -> bytes:
    usage = {"input_tokens": 1200, "output_tokens": 1,
             "cache_read_input_tokens": 900, "cache_creation_input_tokens": 0}
    ev = [
        {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [], "stop_reason": None, "stop_sequence": None, "usage": usage}},
        # gândirea vine prima, cu text gol (display implicit „omitted")
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "signature_delta", "signature": "sig"}},
        {"type": "content_block_stop", "index": 0},
    ]
    if text:
        ev += [
            {"type": "content_block_start", "index": 1,
             "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 1,
             "delta": {"type": "text_delta", "text": text}},
            {"type": "content_block_stop", "index": 1},
        ]
    delta: dict = {"stop_reason": stop, "stop_sequence": None}
    if categorie:
        delta["stop_details"] = {"type": "refusal", "category": categorie, "explanation": "x"}
    ev += [
        {"type": "message_delta", "delta": delta, "usage": {"output_tokens": 40}},
        {"type": "message_stop"},
    ]
    return _sse(ev)


@pytest.fixture
def capturat(monkeypatch):
    """Un client Anthropic real, cu transportul HTTP înlocuit: cererile se
    înregistrează, iar răspunsul se alege per test."""
    from anthropic import AsyncAnthropic

    stare = {"cereri": [], "raspuns": None, "refuza_incalzirea_cu_fallback": False}

    def handler(request: httpx.Request) -> httpx.Response:
        corp = json.loads(request.content or b"{}")
        stare["cereri"].append({"url": str(request.url), "headers": request.headers, "corp": corp})
        if corp.get("stream"):
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=stare["raspuns"]
            )
        if stare["refuza_incalzirea_cu_fallback"] and "fallbacks" in corp:
            # un refuz al cărui mesaj nu pomenește „fallback" — reîncercarea nu are voie
            # să depindă de formularea erorii
            return httpx.Response(400, json={"type": "error", "error": {
                "type": "invalid_request_error", "message": "max_tokens: unsupported value"}})
        return httpx.Response(200, json={
            "id": "msg_w", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [], "stop_reason": "max_tokens", "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0,
                      "cache_creation_input_tokens": 1500, "cache_read_input_tokens": 0},
        })

    c = AsyncAnthropic(api_key="sk-test", http_client=httpx.AsyncClient(
        transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(claude, "_client", c)
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_FALLBACKS", raising=False)
    return stare


async def test_raspunsul_cu_gandire_in_fata_e_citit_corect(capturat):
    capturat["raspuns"] = _flux_raspuns("Răspunsul propriu-zis")
    r = await claude.raspunde("Întrebare", max_tokens=4000)
    assert r.text == "Răspunsul propriu-zis"
    assert r.stop_reason == "end_turn"
    assert r.usage.cache_read_input_tokens == 900


async def test_cererea_pleaca_in_forma_documentata(capturat):
    capturat["raspuns"] = _flux_raspuns("ok")
    await claude.raspunde("Întrebare", max_tokens=4000, efort="low", system="Sistem")
    cerere = capturat["cereri"][0]
    corp = cerere["corp"]

    assert corp["model"] == "claude-opus-5-5"
    assert corp["output_config"] == {"effort": "low"}
    assert corp["fallbacks"] == "default"
    assert corp["system"] == "Sistem"
    assert corp["stream"] is True
    assert "thinking" not in corp  # pe Opus 5.5 gândirea e mereu pornită; nu se trimite
    assert "temperature" not in corp
    assert claude.BETA_FALLBACK in cerere["headers"].get("anthropic-beta", "")


async def test_prefixul_de_cache_sta_primul_cu_marcaj(capturat):
    capturat["raspuns"] = _flux_raspuns("ok")
    await claude.raspunde("Instrucțiunea", max_tokens=4000, prefix_cache="TRANSCRIPT")
    continut = capturat["cereri"][0]["corp"]["messages"][0]["content"]
    assert continut[0] == {
        "type": "text", "text": "TRANSCRIPT", "cache_control": {"type": "ephemeral"},
    }
    assert continut[1] == {"type": "text", "text": "Instrucțiunea"}


async def test_incalzirea_scrie_acelasi_prefix_fara_raspuns(capturat):
    capturat["raspuns"] = _flux_raspuns("ok")
    inc = await claude.incalzeste_cache("TRANSCRIPT", efort="medium")
    await claude.raspunde("Instrucțiunea", max_tokens=4000, prefix_cache="TRANSCRIPT")

    incalzire, reala = (c["corp"] for c in capturat["cereri"])
    assert incalzire["max_tokens"] == 0
    assert not incalzire.get("stream")  # max_tokens=0 e refuzat cu stream
    # tot ce intră în cache trebuie să fie identic: blocul prefix, efortul, modelul
    assert incalzire["messages"][0]["content"][0] == reala["messages"][0]["content"][0]
    assert incalzire["output_config"] == reala["output_config"]
    assert incalzire["model"] == reala["model"]
    # ca în exemplul oficial: un text după punctul de cache, citit dar fără răspuns
    assert incalzire["messages"][0]["content"][1]["text"] == "warmup"
    assert "cache_control" not in incalzire["messages"][0]["content"][1]
    assert inc.scris == 1500 and inc.cu_fallback and not inc.eroare


async def test_incalzirea_refuzata_cu_fallback_se_reia_fara(capturat):
    """Orice refuz al variantei cu fallback duce la o a doua încercare fără — nu doar
    unul care pomenește cuvântul „fallback" în mesaj."""
    capturat["refuza_incalzirea_cu_fallback"] = True
    inc = await claude.incalzeste_cache("TRANSCRIPT")

    prima, a_doua = (c["corp"] for c in capturat["cereri"])
    assert "fallbacks" in prima and "fallbacks" not in a_doua
    assert inc.scris == 1500 and not inc.cu_fallback
    assert "max_tokens: unsupported value" in inc.eroare  # motivul rămâne vizibil


async def test_incalzirea_nu_ridica_exceptii(capturat, monkeypatch):
    async def pica(**kw):
        raise ConnectionError("rețea căzută")

    monkeypatch.setattr(claude.client().beta.messages, "create", pica)
    inc = await claude.incalzeste_cache("TRANSCRIPT")
    assert inc.scris == 0 and "rețea căzută" in inc.eroare


async def test_refuzul_devine_exceptie_cu_categorie(capturat):
    capturat["raspuns"] = _flux_raspuns("", stop="refusal", categorie="bio")
    with pytest.raises(claude.RefuzModel) as e:
        await claude.raspunde("Întrebare", max_tokens=4000)
    assert e.value.categorie == "bio"


async def test_raspuns_taiat_e_semnalat(capturat):
    capturat["raspuns"] = _flux_raspuns('{"a": [1, 2', stop="max_tokens")
    r = await claude.raspunde("Întrebare", max_tokens=50)
    assert r.trunchiat


async def test_comutatoarele_din_mediu(capturat, monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("CLAUDE_FALLBACKS", "off")
    capturat["raspuns"] = _flux_raspuns("ok")
    await claude.raspunde("Întrebare", max_tokens=4000)
    cerere = capturat["cereri"][0]
    assert cerere["corp"]["model"] == "claude-sonnet-4-6"
    assert "fallbacks" not in cerere["corp"]
    assert claude.BETA_FALLBACK not in cerere["headers"].get("anthropic-beta", "")


def test_fara_cheie_mesaj_clar(monkeypatch):
    monkeypatch.setattr(claude, "_client", None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as e:
        claude.client()
    assert "ANTHROPIC_API_KEY" in str(e.value)


@pytest.mark.parametrize(
    "text,asteptat",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Iată:\n{"a": 1}\nGata.', {"a": 1}),
        ('{"a": [1, 2', {"a": [1, 2]}),  # ciobit — reparat
    ],
)
def test_parse_json(text, asteptat):
    assert claude.parse_json(text) == asteptat
