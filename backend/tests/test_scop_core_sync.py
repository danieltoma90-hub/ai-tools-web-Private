# -*- coding: utf-8 -*-
"""Conținutul CORE trăiește în două repo-uri. Testul semnalează divergența.

Sursa de adevăr este skill-ul local. Când nu e accesibil (CI, altă mașină),
testul se sare — nu eșuează.

`stil.py` și `capitol.py` (Task 1 din planul scop-core-web) au aceeași
origine, ca și `charisma_core.py` — dar, spre deosebire de el, sursele lor
din `tools/shared/` importă alte module din pachetul local
(`tools.shared.docx_scop`, `tools.shared.charisma_core`), cu `sys.path`
manipulat, în timp ce copiile de aici folosesc import relativ de pachet
(`from . import stil`) și n-au nevoie de `sys.path`. Acel bloc de import e
singura diferență ACCEPTATĂ între sursă și copie — restul conținutului
trebuie să fie identic byte cu byte, deci comparăm hash-ul doar peste partea
de după bloc (vezi `_hash_fara_antet`). `stil.py` nu are acest import
încrucișat (importă doar din `docx`), deci copia lui e byte-identică cu
sursa — hash direct, ca la `charisma_core.py`.
"""
import hashlib
import pathlib

import pytest

SURSA = pathlib.Path("d:/AI_Claude/tools/shared/charisma_core.py")
COPIA = pathlib.Path(__file__).resolve().parents[1] / "skills" / "scop_core" / "charisma_core.py"

SURSA_STIL = pathlib.Path("d:/AI_Claude/tools/shared/docx_scop.py")
COPIA_STIL = pathlib.Path(__file__).resolve().parents[1] / "skills" / "scop_core" / "stil.py"

SURSA_SCOPE = pathlib.Path("d:/AI_Claude/skills/generare-scope-core/scope.py")
COPIA_SCOPE = pathlib.Path(__file__).resolve().parents[1] / "skills" / "scop_core" / "scope.py"

SURSA_CAPITOL = pathlib.Path("d:/AI_Claude/tools/shared/capitol_core.py")
COPIA_CAPITOL = pathlib.Path(__file__).resolve().parents[1] / "skills" / "scop_core" / "capitol.py"


def _hash(p: pathlib.Path) -> str:
    """Hash peste conținut, cu sfârșiturile de linie normalizate.

    Cele două repo-uri au politici diferite: ai-tools-web are un
    ``.gitattributes`` cu ``*.py text eol=lf``, repo-ul sursă nu are, deci
    ``core.autocrlf`` îi lasă fișierele cu CRLF. Un ``git checkout``
    re-materializează copia cu LF, iar o comparație pe octeți bruți ar pica
    pe ceva care nu e conținut. Testul păzește conținutul, nu artefactele de
    checkout — o singură linie de cod schimbată tot îl face să pice.
    """
    text = p.read_text(encoding="utf-8")
    text = text.replace(chr(13) + chr(10), chr(10)).replace(chr(13), chr(10))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _hash_fara_antet(p: pathlib.Path) -> str:
    """Hash peste conținutul fișierului, excluzând liniile de import/`sys.path`
    și liniile goale.

    Liniile de import diferă mereu, cu bună știință, între sursă (`tools/shared/`,
    care importă alte module ale pachetului local prin `sys.path` + import
    absolut) și copia din backend (import relativ de pachet, fără `sys.path`)
    — vezi docstring-ul modulului; liniile goale se scot ca să nu conteze
    CÂTE linii goale separă blocul de import (care variază firesc cu numărul
    de importuri) de restul fișierului. Orice altă diferență (docstring, cod,
    comentarii) tot pică testul.
    """
    linii = p.read_text(encoding="utf-8").splitlines()
    pastrate = [
        linie for linie in linii
        if linie.strip()
        and not linie.lstrip().startswith(("import ", "from "))
        and "sys.path" not in linie
    ]
    return hashlib.sha256("\n".join(pastrate).encode("utf-8")).hexdigest()


@pytest.mark.skipif(not SURSA.is_file(), reason="repo-ul sursă nu e accesibil aici")
def test_continutul_core_nu_a_divergat():
    assert _hash(COPIA) == _hash(SURSA), (
        "charisma_core.py diferă între ai-tools-web și repo-ul sursă. "
        "Conținutul se editează în sursă și se copiază aici."
    )


@pytest.mark.skipif(not SURSA_STIL.is_file(), reason="repo-ul sursă nu e accesibil aici")
def test_stil_nu_a_divergat():
    """`docx_scop.py` nu importă niciun alt modul din pachetul local — doar
    `docx` — deci copia (`stil.py`) trebuie să fie byte-identică cu sursa."""
    assert _hash(COPIA_STIL) == _hash(SURSA_STIL), (
        "stil.py diferă de tools/shared/docx_scop.py. "
        "Conținutul se editează în sursă și se copiază aici."
    )


@pytest.mark.skipif(not SURSA_CAPITOL.is_file(), reason="repo-ul sursă nu e accesibil aici")
def test_capitol_nu_a_divergat():
    """`capitol_core.py`/`capitol.py` diferă doar în blocul de import (vezi
    docstring-ul modulului) — restul conținutului trebuie să fie identic."""
    assert _hash_fara_antet(COPIA_CAPITOL) == _hash_fara_antet(SURSA_CAPITOL), (
        "capitol.py diferă de tools/shared/capitol_core.py (dincolo de "
        "blocul de import, care e singura diferență acceptată). "
        "Conținutul se editează în sursă și se copiază aici."
    )


@pytest.mark.skipif(not SURSA_SCOPE.is_file(), reason="repo-ul sursă nu e accesibil aici")
def test_scope_nu_a_divergat():
    """`scope.py` importă din pachetul local prin `sys.path`, copia de aici
    prin import relativ — doar blocul de import diferă.

    Testul lipsea când `docx_scop.py` a luat-o înainte cu rescrierea de
    antet+subsol și inserarea capturilor: driftul din `stil.py` a fost prins,
    al lui `scope.py` nu. De aici încolo, e prins.
    """
    assert _hash_fara_antet(COPIA_SCOPE) == _hash_fara_antet(SURSA_SCOPE), (
        "scope.py diferă de skills/generare-scope-core/scope.py (dincolo de "
        "blocul de import, care e singura diferență acceptată). "
        "Conținutul se editează în sursă și se copiază aici."
    )
