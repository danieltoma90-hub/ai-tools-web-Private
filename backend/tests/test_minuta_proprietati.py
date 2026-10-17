"""Proprietățile documentului generat: autorul este utilizatorul care generează minuta, iar titlul se
construiește din clientul identificat în minută (sau „TotalSoft”) și subiect — nu mai vin din șablon."""
import json
import re
import sys
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "minuta" / "scripts"))
from build_minuta import build_minuta, titlu_document  # noqa: E402
from limba import docx_to_en  # noqa: E402

from acces import nume_utilizator  # noqa: E402
from auth import verify_token  # noqa: E402
from main import app  # noqa: E402

TEMPLATE = Path(__file__).parent.parent / "skills" / "minuta" / "template" / "F05_minuta_template.docx"


def _core(path: Path) -> str:
    return zipfile.ZipFile(path).read("docProps/core.xml").decode("utf-8")


def _tag(xml: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
    return m.group(1) if m else None


def _construieste(tmp_path: Path, meta: dict, **kw) -> Path:
    src = tmp_path / "m.json"
    src.write_text(json.dumps({"meta": meta, "sectiuni": []}, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "m.docx"
    build_minuta(src, out, template_path=TEMPLATE, **kw)
    return out


def test_titlul_are_clientul_fara_marcaje_si_subiectul(tmp_path):
    meta = {"nume_client": "VEPSAŞ – compania de furnizare [CLARIFICARE NEEDED: denumirea legală]",
            "subiect": "Analiza proceselor [DEDUCȚIE]"}
    core = _core(_construieste(tmp_path, meta, autor="Ana Pop"))
    assert _tag(core, "dc:title") == "Minuta Intalnirii – VEPSAŞ – compania de furnizare – Analiza proceselor"
    assert _tag(core, "dc:creator") == "Ana Pop" and _tag(core, "cp:lastModifiedBy") == "Ana Pop"
    assert "ALPINLUX" not in core and "Nastase" not in core


def test_fara_client_titlul_si_autorul_sunt_totalsoft(tmp_path):
    core = _core(_construieste(tmp_path, {"subiect": "Ședință internă"}))
    assert _tag(core, "dc:title") == "Minuta Intalnirii – TotalSoft – Ședință internă"
    assert _tag(core, "dc:creator") == "TotalSoft"
    assert titlu_document({}) == "Minuta Intalnirii – TotalSoft"


def test_in_engleza_titlul_incepe_cu_meeting_minutes(tmp_path):
    out = _construieste(tmp_path, {"nume_client": "Client Test", "subiect": "Kick-off"}, autor="Ana Pop")
    docx_to_en(out)
    assert _tag(_core(out), "dc:title") == "Meeting Minutes – Client Test – Kick-off"


def test_sablonul_nu_mai_are_titlul_altui_client():
    assert "alpinlux" not in _core(TEMPLATE).lower()


@pytest.mark.parametrize("user, nume", [
    ({"email": "daniel.toma@totalsoft.ro"}, "Daniel Toma"),
    ({"email": "ana-maria.pop@client.ro", "user_metadata": {}}, "Ana Maria Pop"),
    ({"email": "a@b.ro", "user_metadata": {"full_name": "  Ana   Pop "}}, "Ana Pop"),
    ({"id": "u1"}, "TotalSoft"),
])
def test_numele_utilizatorului(user, nume):
    assert nume_utilizator(user) == nume


@pytest.mark.asyncio
async def test_ruta_trimite_jobului_autorul(client, tmp_path):
    transcript = tmp_path / "abc.vtt"
    transcript.write_bytes(b"WEBVTT\n\n")
    app.dependency_overrides[verify_token] = lambda: {"id": "u1", "email": "daniel.toma@totalsoft.ro"}
    try:
        with patch("routers.minuta._run_job", new_callable=AsyncMock) as rulat, \
             patch("routers.minuta.download_upload", return_value=transcript), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}):
            raspuns = await client.post("/api/minuta", headers={"Authorization": "Bearer x"},
                                        data={"storage_path": "minuta/abc.vtt", "filename": "S.vtt"})
    finally:
        app.dependency_overrides.clear()
    assert raspuns.status_code == 200
    assert rulat.call_args[0][7] == "Daniel Toma"
