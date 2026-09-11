# -*- coding: utf-8 -*-
"""Conținutul CORE trăiește în două repo-uri. Testul semnalează divergența.

Sursa de adevăr este skill-ul local. Când nu e accesibil (CI, altă mașină),
testul se sare — nu eșuează.
"""
import hashlib
import pathlib

import pytest

SURSA = pathlib.Path("d:/AI_Claude/tools/shared/charisma_core.py")
COPIA = pathlib.Path(__file__).resolve().parents[1] / "skills" / "scop_core" / "charisma_core.py"


def _hash(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.skipif(not SURSA.is_file(), reason="repo-ul sursă nu e accesibil aici")
def test_continutul_core_nu_a_divergat():
    assert _hash(COPIA) == _hash(SURSA), (
        "charisma_core.py diferă între ai-tools-web și repo-ul sursă. "
        "Conținutul se editează în sursă și se copiază aici."
    )
