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

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
