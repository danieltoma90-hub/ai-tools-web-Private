import base64
import hashlib
import json
import os
import time
from typing import Any

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client

_security = HTTPBearer(auto_error=False)

_client = None


def get_supabase():
    """Un singur client Supabase per proces.

    `create_client` construieste clientii HTTP pentru auth, storage si postgrest.
    Facut la fiecare cerere, pregatirea costa mai mult decat apelul de retea care
    urmeaza dupa ea.
    """
    global _client
    if _client is None:
        _client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"],
        )
    return _client


def reset_supabase_client() -> None:
    """Forteaza reconstruirea clientului la urmatorul apel (folosit de teste)."""
    global _client
    _client = None


# Cat timp raspunsul Supabase la „cine e utilizatorul asta?" ramane valabil.
# Fara cache, fiecare cerere — inclusiv fiecare interogare de progres, la 2
# secunde — plateste un drum pana la Supabase (~0.6s masurat pe productie).
TOKEN_CACHE_TTL_S = 60
_MAX_CACHED_TOKENS = 500

_token_cache: dict[str, tuple[float, Any]] = {}


def _token_expira_la(token: str) -> float | None:
    """`exp` din payload-ul JWT, fara verificarea semnaturii.

    NU decide daca token-ul e valid — asta ramane treaba Supabase. Il citim doar
    ca sa SCURTAM cache-ul: un token care mai are 20 de secunde de trait nu are
    voie sa fie acceptat 60.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        return float(exp) if isinstance(exp, (int, float)) else None
    except Exception:
        return None


def _retine(cheie: str, token: str, user: Any, acum: float) -> None:
    valabil_pana = acum + TOKEN_CACHE_TTL_S
    expira = _token_expira_la(token)
    if expira is not None:
        valabil_pana = min(valabil_pana, acum + max(0.0, expira - time.time()))

    if len(_token_cache) >= _MAX_CACHED_TOKENS:
        for k, (pana, _) in list(_token_cache.items()):
            if pana <= acum:
                _token_cache.pop(k, None)
        if len(_token_cache) >= _MAX_CACHED_TOKENS:
            _token_cache.clear()

    _token_cache[cheie] = (valabil_pana, user)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_security),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Token lipsă")
    token = credentials.credentials

    # Cheia e amprenta token-ului, nu token-ul: nu tinem credentiale in clar
    # intr-un dictionar care traieste cat procesul.
    cheie = hashlib.sha256(token.encode()).hexdigest()
    acum = time.monotonic()
    intrare = _token_cache.get(cheie)
    if intrare is not None and intrare[0] > acum:
        return intrare[1]

    try:
        user = get_supabase().auth.get_user(token).user
    except Exception:
        _token_cache.pop(cheie, None)
        raise HTTPException(status_code=401, detail="Token invalid sau expirat")

    _retine(cheie, token, user, acum)
    return user
