"""Job store in-memory, partajat de tool-urile care genereaza documente in fundal.

Se goleste la fiecare restart/redeploy Render (acceptat — frontend-ul trateaza
jobul expirat cu mesaj "reincarca fisierul").

Toate generarile trec prin `ruleaza`: el termina jobul cu rezultatul sau cu
eroarea pe inteles, noteaza esecul in jurnal si consumul Claude in `consum`.
"""
import base64
import logging
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, Any]] = {}
_job_meta: dict[str, dict[str, Any]] = {}

# Un job terminat tine documentul in base64 in memorie. Frontend-ul il ia la
# prima interogare de dupa finalizare, deci dupa o jumatate de ora nu mai are
# cine sa-l ceara — iar pe o instanta free de 512MB acumularea ajunge, incet,
# la un restart care omoara job-urile in curs.
JOB_TTL_S = 1800
# Plasa de siguranta pentru job-uri ramase in "processing" fiindca procesul lor
# a murit: fara ea ar ocupa memorie pana la restart.
JOB_MAX_LIFETIME_S = 7200


def _cleanup_jobs() -> None:
    acum = time.monotonic()
    for job_id, meta in list(_job_meta.items()):
        terminat = meta.get("terminat")
        prea_vechi = acum - (meta.get("creat") or acum) > JOB_MAX_LIFETIME_S
        livrat_demult = terminat is not None and acum - terminat > JOB_TTL_S
        if prea_vechi or livrat_demult:
            _jobs.pop(job_id, None)
            _job_meta.pop(job_id, None)


def create_job(user_email: str, modul: str = "") -> str:
    """`modul` nu ajunge în răspunsul către pagină — e pentru jurnalul de erori și consum."""
    _cleanup_jobs()
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "user_email": user_email}
    _job_meta[job_id] = {"creat": time.monotonic(), "terminat": None, "modul": modul}
    return job_id


def set_step(job_id: str, step: str) -> None:
    if job_id in _jobs:
        _jobs[job_id]["step"] = step


def finish(job_id: str, **payload: Any) -> None:
    _jobs[job_id] = {"status": "done", **payload}
    _marcheaza_terminat(job_id)


def fail(job_id: str, error: str) -> None:
    _jobs[job_id] = {"status": "error", "error": error}
    _marcheaza_terminat(job_id)


def _email(job_id: str) -> str:
    return (_jobs.get(job_id) or {}).get("user_email", "") or "anonymous"


def _modul(job_id: str) -> str:
    return str((_job_meta.get(job_id) or {}).get("modul") or "")


def esueaza(job_id: str, exc: Exception, mesaj: str | None = None) -> None:
    """Marchează jobul eșuat cu un mesaj pe înțeles și îl notează în jurnalul
    administratorului. Toate generările eșuate trec pe aici.

    `mesaj` suprascrie traducerea automată, pentru cazurile în care apelantul
    știe mai bine ce să spună (de exemplu, un document invalid).
    """
    from ai_errors import mesaj_pentru_utilizator
    import jurnal

    email = _email(job_id)
    text = mesaj or mesaj_pentru_utilizator(exc)
    fail(job_id, text)
    jurnal.inregistreaza(_modul(job_id), email, text, f"{type(exc).__name__}: {exc}")


async def ruleaza(
    job_id: str,
    lucrare: Callable[[], Awaitable[dict[str, Any]]],
    *,
    mesaj: Callable[[Exception], str | None] | None = None,
    efort: str | None = None,
) -> None:
    """Rulează o generare în fundal, de la cap la coadă.

    `lucrare` întoarce câmpurile jobului terminat. O excepție marchează jobul
    eșuat, cu mesajul din `mesaj(exc)` sau cu traducerea automată. Consumul
    Claude se notează în ambele cazuri. `efort` impune efortul tuturor apelurilor
    (testul administratorului); fără el, fiecare modul își folosește efortul lui.
    """
    import claude
    import consum

    # luate de la început: jobul terminat nu mai păstrează emailul
    modul, email = _modul(job_id), _email(job_id)
    reusit = False
    with claude.numara(efort) as c:
        try:
            finish(job_id, **await lucrare())
            reusit = True
        except Exception as e:
            logger.error("job %s (%s) FAILED: %s\n%s", job_id, modul, e, traceback.format_exc())
            esueaza(job_id, e, mesaj(e) if mesaj else None)
        finally:
            consum.inregistreaza(modul, email, c, reusit)


def livreaza(job_id: str, cale: Path, *, tool: str, filename: str) -> tuple[str, str]:
    """Salvează documentul generat în Repository și îl întoarce pentru pagină,
    ca (cale în storage, conținut base64)."""
    from storage import upload_file

    storage_path = upload_file(cale, tool=tool, filename=filename, user_email=_email(job_id))
    return storage_path, base64.b64encode(cale.read_bytes()).decode()


def _marcheaza_terminat(job_id: str) -> None:
    meta = _job_meta.setdefault(job_id, {"creat": time.monotonic(), "terminat": None})
    meta["terminat"] = time.monotonic()


def get_job(job_id: str) -> dict[str, Any] | None:
    _cleanup_jobs()
    return _jobs.get(job_id)
