import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone
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


# Mesajul ajunge si in proxy, care il recunoaste dupa „dezactivat" si trimite
# utilizatorul la login cu explicatia potrivita, nu cu „sesiunea a expirat".
CONT_DEZACTIVAT = "Contul a fost dezactivat de administrator."


def e_dezactivat(user: Any) -> bool:
    """Contul e blocat de administrator: Supabase il tine ca `banned_until` in viitor.

    O valoare care nu se poate citi e tratata ca „nu e blocat": blocarea propriu-zisa
    o face Supabase la login si la reinnoirea sesiunii; aici e doar al doilea strat,
    pentru sesiunile deja deschise.
    """
    raw = user.get("banned_until") if isinstance(user, dict) else getattr(user, "banned_until", None)
    if not raw:
        return False
    try:
        pana = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if pana.tzinfo is None:
        pana = pana.replace(tzinfo=timezone.utc)
    return pana > datetime.now(timezone.utc)


def _id_din(user: Any) -> str:
    return str((user.get("id") if isinstance(user, dict) else getattr(user, "id", "")) or "")


def uita_utilizatorul(uid: str) -> int:
    """Scoate din cache toate sesiunile unui utilizator; intoarce cate erau.

    Fara asta, un cont dezactivat ar mai merge pana la un minut — cat tine cache-ul.
    Render ruleaza un singur proces, deci curatenia de aici e completa.
    """
    de_scos = [k for k, (_, u) in _token_cache.items() if _id_din(u) == uid]
    for k in de_scos:
        _token_cache.pop(k, None)
    return len(de_scos)


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

    # Supabase refuza login-ul si reinnoirea pentru un cont blocat, dar un token
    # emis inainte de blocare ramane valid pana expira (~1h). Il oprim aici.
    if e_dezactivat(user):
        raise HTTPException(status_code=401, detail=CONT_DEZACTIVAT)

    _retine(cheie, token, user, acum)
    return user
