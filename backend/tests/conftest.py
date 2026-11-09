import pytest
from httpx import AsyncClient, ASGITransport

import acces
from main import app


@pytest.fixture(autouse=True)
def _acces_la_toate_modulele(monkeypatch):
    """În teste, implicit oricine are acces la toate modulele — fără citiri din Supabase.

    Testele de acces (test_acces.py) își pun propria configurație peste aceasta.
    """
    cfg = acces.config_implicita()
    cfg["grup_implicit"] = acces.ERP
    monkeypatch.setattr(acces, "incarca_config", lambda fortat=False, strict=False: cfg)
    # multe teste simulează utilizatorul doar prin {"id": "u1"}, fără email
    monkeypatch.setattr(acces, "are_acces", lambda email, modul, cfg=None: True)
    return cfg

@pytest.fixture(autouse=True)
def _fara_apeluri_reale_la_claude(monkeypatch):
    """Niciun test nu ajunge la API-ul Claude din greșeală.

    Încălzirea cache-ului devine un no-op, iar un apel nesimulat explicit pică
    zgomotos în loc să plece pe rețea. Testele drumului spre Claude
    (test_claude.py) își pun la loc funcțiile reale.
    """
    import claude

    async def _incalzire(*a, **k):
        return claude.Incalzire()

    async def _raspuns_nesimulat(*a, **k):
        raise AssertionError("Apel Claude nesimulat în test — simulează claude.raspunde.")

    monkeypatch.setattr(claude, "incalzeste_cache", _incalzire)
    monkeypatch.setattr(claude, "raspunde", _raspuns_nesimulat)


@pytest.fixture(autouse=True)
def jurnal_in_memorie(monkeypatch):
    """Jurnalul de erori se scrie în Supabase; în teste rămâne în memorie.
    Testele îl pot citi prin fixture-ul `jurnal_in_memorie`."""
    import jurnal

    intrari: list[dict] = []
    monkeypatch.setattr(jurnal, "inregistreaza",
                        lambda modul, email, mesaj, tehnic="": intrari.insert(0, {
                            "modul": modul, "email": email, "mesaj": mesaj, "tehnic": tehnic}))
    monkeypatch.setattr(jurnal, "citeste", lambda limita=100: intrari[:limita])
    return intrari


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
