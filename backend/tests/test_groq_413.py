# -*- coding: utf-8 -*-
"""Teste pentru tratarea erorii Groq 413 (cerere peste TPM) si curatarea VTT."""
from pipelines.minuta_free_pipeline import _CUE_ID_RE, shrink_for_413
from skills.scenarii.ai_gen import _shrink_for_413 as scenarii_shrink


GROQ_413_MSG = (
    "Error code: 413 - {'error': {'message': 'Request too large for model "
    "`openai/gpt-oss-120b` ... on tokens per minute (TPM): Limit 8000, "
    "Requested 10276, please reduce your message size and try again.'}}"
)


def test_shrink_uses_limit_requested_ratio():
    content = "x" * 10_000
    out = shrink_for_413(content, GROQ_413_MSG)
    # 8000/10276 * 0.85 ≈ 0.66 → ~6.600 caractere
    assert 6_000 < len(out) < 7_000
    assert out == content[: len(out)]


def test_shrink_fallback_without_numbers():
    content = "x" * 10_000
    out = shrink_for_413(content, "eroare fara cifre")
    assert len(out) == 7_000  # fallback 0.7


def test_shrink_never_below_minimum():
    out = shrink_for_413("x" * 600, GROQ_413_MSG)
    assert len(out) >= 500


def test_scenarii_shrink_same_behavior():
    content = "y" * 10_000
    assert 6_000 < len(scenarii_shrink(content, GROQ_413_MSG)) < 7_000


def test_cue_id_regex_variants():
    # Teams: guid/NN-M
    assert _CUE_ID_RE.match("a10a18bb-5391-498a-8697-a5ace5aaa804/27-1")
    # GUID simplu (alte exporturi VTT)
    assert _CUE_ID_RE.match("a10a18bb-5391-498a-8697-a5ace5aaa804")
    # contor numeric (stil SRT)
    assert _CUE_ID_RE.match("42")
    # textul real de discutie NU se potriveste
    assert not _CUE_ID_RE.match("Daniel Toma: da, perfect")
    assert not _CUE_ID_RE.match("Pretul este 42 de lei")
