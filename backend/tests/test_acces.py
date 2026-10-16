"""Grupurile de utilizatori și accesul pe module (logica reală, cu Storage simulat în memorie)."""
import copy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import acces
from auth import verify_token
from main import app

# funcțiile reale, înainte ca fixture-ul din conftest să le înlocuiască pentru celelalte teste
INCARCA_REAL, ARE_ACCES_REAL = acces.incarca_config, acces.are_acces
ADMIN, ERP_USER, TS_USER, NOU = "daniel.toma@totalsoft.ro", "ana@totalsoft.ro", "ion@totalsoft.ro", "nou@totalsoft.ro"


@pytest.fixture
def stocare(monkeypatch):
    """Configurația „din Storage” ținută în memorie; logica de acces e cea reală."""
    store = {"cfg": None, "scrieri": 0}

    def _scrie(cfg):
        store["cfg"] = copy.deepcopy(cfg)
        store["scrieri"] += 1

    monkeypatch.setattr(acces, "incarca_config", INCARCA_REAL)
    monkeypatch.setattr(acces, "are_acces", ARE_ACCES_REAL)
    monkeypatch.setattr(acces, "_citeste", lambda: copy.deepcopy(store["cfg"]))
    monkeypatch.setattr(acces, "_scrie", _scrie)
    monkeypatch.setattr(acces, "_cache", {"config": None, "pana": 0.0})
    monkeypatch.setattr(acces, "utilizatori_supabase", lambda: [
        SimpleNamespace(email=ADMIN, last_sign_in_at="2026-10-16T08:00:00Z"),
        SimpleNamespace(email=ERP_USER, last_sign_in_at="2026-10-01T08:00:00Z"),
        SimpleNamespace(email=TS_USER, last_sign_in_at=None),  # invitat, nu s-a conectat niciodată
    ])
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    return store


def _ca(email):
    app.dependency_overrides[verify_token] = lambda: {"id": email, "email": email}


@pytest.fixture(autouse=True)
def _curata_override():
    yield
    app.dependency_overrides.clear()


# ── configurația ─────────────────────────────────────────────────────────────

def test_prima_pornire_pune_utilizatorii_activi_in_echipa_erp(stocare):
    cfg = acces.incarca_config(fortat=True)
    assert cfg["membri"] == {ADMIN: acces.ERP, ERP_USER: acces.ERP}
    assert cfg["grup_implicit"] == acces.TOTALSOFT and stocare["scrieri"] == 1
    assert {g["id"]: g["module"] for g in cfg["grupuri"]} == {acces.ERP: ["*"], acces.TOTALSOFT: ["minuta"]}


def test_o_eroare_temporara_nu_suprascrie_configuratia(stocare, monkeypatch):
    acces.incarca_config(fortat=True)
    def cade():
        raise RuntimeError("timeout Storage")
    monkeypatch.setattr(acces, "_citeste", cade)
    cfg = acces.incarca_config(fortat=True)
    assert cfg["membri"][ERP_USER] == acces.ERP  # ultima variantă cunoscută, nu cea implicită
    assert stocare["scrieri"] == 1               # nimic rescris
    with pytest.raises(RuntimeError):
        acces.incarca_config(fortat=True, strict=True)


def test_doar_404_inseamna_fisier_lipsa():
    class E(Exception):
        def __init__(self, status, msg):
            super().__init__(msg)
            self.status = status
    assert acces._e_lipsa(E(404, "Object not found"))
    assert acces._e_lipsa(E(400, '{"error":"not_found","message":"Object not found"}'))
    assert not acces._e_lipsa(E(500, "Internal error"))
    assert not acces._e_lipsa(E(401, "Invalid JWT"))


def test_modulele_dupa_grup(stocare):
    cfg = acces.incarca_config(fortat=True)
    assert acces.module_permise(ERP_USER, cfg) == list(acces.MODULE)
    assert acces.module_permise(NOU, cfg) == ["minuta"]          # grupul implicit
    assert acces.module_permise(ADMIN, cfg) == list(acces.MODULE)
    assert acces.acces_la_tool(NOU, "context", cfg) and not acces.acces_la_tool(NOU, "mockup", cfg)
    assert not acces.are_acces("", "minuta", cfg)


def test_validarea_scoate_modulele_si_grupurile_necunoscute():
    cfg = acces.valideaza({"grupuri": [{"id": "x", "nume": "X", "module": ["minuta", "inexistent"]}],
                           "grup_implicit": "lipsa", "membri": {"A@B.ro": "x", "c@d.ro": "lipsa"}})
    assert cfg["grupuri"][0]["module"] == ["minuta"] and cfg["grup_implicit"] == "x"
    assert cfg["membri"] == {"a@b.ro": "x"}


# ── rutele tool-urilor ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_totalsoft_e_refuzat_la_mockup_si_primit_la_minuta(client, stocare):
    acces.incarca_config(fortat=True)
    _ca(NOU)
    refuz = await client.get("/api/mockup/job/abc", headers={"Authorization": "Bearer x"})
    assert refuz.status_code == 403 and "Mockup" in refuz.json()["detail"]
    with patch("routers.minuta.list_files", return_value=[]):
        ok = await client.get("/api/minuta/contexts", headers={"Authorization": "Bearer x"})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_varianta_free_nu_mai_exista(client, stocare):
    _ca(ERP_USER)
    r = await client.post("/api/minuta-free", headers={"Authorization": "Bearer x"},
                          data={"storage_path": "minuta/a.vtt", "filename": "a.vtt"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_incarcarea_cere_modulul(client, stocare):
    acces.incarca_config(fortat=True)
    _ca(NOU)
    with patch("routers.uploads.create_upload_url", return_value={"signed_url": "u", "storage_path": "minuta/x.vtt"}):
        ok = await client.post("/api/uploads/sign", headers={"Authorization": "Bearer x"},
                               json={"filename": "a.vtt", "tool": "minuta"})
        refuz = await client.post("/api/uploads/sign", headers={"Authorization": "Bearer x"},
                                  json={"filename": "a.xlsx", "tool": "mockup"})
    assert ok.status_code == 200 and refuz.status_code == 403


@pytest.mark.asyncio
async def test_repository_arata_doar_documentele_modulelor_permise(client, stocare):
    acces.incarca_config(fortat=True)
    _ca(NOU)
    fisiere = [{"name": n, "tool": t, "storage_path": f"{t}/x/{n}", "created_at": "", "metadata": {}}
               for n, t in (("M.docx", "minuta"), ("C.docx", "context"), ("K.docx", "mockup"))]
    with patch("routers.documents.list_files", return_value=fisiere), \
         patch("routers.documents.get_signed_urls", return_value={}):
        r = await client.get("/api/documents", headers={"Authorization": "Bearer x"})
        sters = await client.delete("/api/documents", params={"storage_path": f"mockup/{NOU}/K.docx"},
                                    headers={"Authorization": "Bearer x"})
    assert sorted(d["name"] for d in r.json()) == ["C.docx", "M.docx"]
    assert sters.status_code == 403


# ── administrarea grupurilor ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_accesul_meu(client, stocare):
    _ca(NOU)
    r = (await client.get("/api/acces/eu", headers={"Authorization": "Bearer x"})).json()
    assert r == {"email": NOU, "grup": {"id": acces.TOTALSOFT, "nume": "TotalSoft"}, "module": ["minuta"], "admin": False}


@pytest.mark.asyncio
async def test_doar_adminul_administreaza_grupurile(client, stocare):
    _ca(ERP_USER)
    assert (await client.get("/api/acces/config", headers={"Authorization": "Bearer x"})).status_code == 403
    assert (await client.post("/api/acces/grupuri", headers={"Authorization": "Bearer x"},
                              json={"nume": "Test", "module": []})).status_code == 403


@pytest.mark.asyncio
async def test_adminul_creeaza_modifica_si_sterge_grupuri(client, stocare):
    _ca(ADMIN)
    h = {"Authorization": "Bearer x"}
    cfg = (await client.get("/api/acces/config", headers=h)).json()
    assert [u["email"] for u in cfg["utilizatori"]] == sorted([ADMIN, ERP_USER, TS_USER])
    assert next(u for u in cfg["utilizatori"] if u["email"] == TS_USER)["grup"] == acces.TOTALSOFT

    creat = (await client.post("/api/acces/grupuri", headers=h, json={"nume": "Consultanți Producție",
                                                                       "module": ["minuta", "scop-core"]})).json()
    nou = next(g for g in creat["grupuri"] if g["nume"] == "Consultanți Producție")
    assert nou["id"] == "consultanti-productie" and nou["module"] == ["minuta", "scop-core"]

    assert (await client.put("/api/acces/membri", headers=h, json={"email": TS_USER, "grup": nou["id"]})).status_code == 200
    assert acces.module_permise(TS_USER) == ["minuta", "scop-core"]

    await client.put(f"/api/acces/grupuri/{nou['id']}", headers=h, json={"nume": "", "module": ["minuta", "training"]})
    assert acces.module_permise(TS_USER) == ["minuta", "training"]

    assert (await client.delete(f"/api/acces/grupuri/{acces.TOTALSOFT}", headers=h)).status_code == 422  # implicit
    assert (await client.delete(f"/api/acces/grupuri/{nou['id']}", headers=h)).status_code == 200
    assert acces.module_permise(TS_USER) == ["minuta"]  # înapoi în grupul implicit
    assert (await client.put("/api/acces/membri", headers=h, json={"email": TS_USER, "grup": "lipsa"})).status_code == 404


@pytest.mark.asyncio
async def test_modificarile_se_refuza_cand_storage_nu_raspunde(client, stocare, monkeypatch):
    _ca(ADMIN)
    acces.incarca_config(fortat=True)
    def cade():
        raise RuntimeError("timeout Storage")
    monkeypatch.setattr(acces, "_citeste", cade)
    r = await client.put("/api/acces/membri", headers={"Authorization": "Bearer x"},
                         json={"email": TS_USER, "grup": acces.ERP})
    assert r.status_code == 502 and stocare["scrieri"] == 1
