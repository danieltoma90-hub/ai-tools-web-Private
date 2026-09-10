"""Job store + estimate store in-memory, partajate de tool-urile care genereaza
documente in fundal.

Se golesc la fiecare restart/redeploy Render (acceptat — frontend-ul trateaza
job/estimate expirat cu mesaj "reincarca fisierul").
"""
import time
import uuid
from pathlib import Path
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}
_job_meta: dict[str, dict[str, float | None]] = {}
_estimates: dict[str, dict[str, Any]] = {}

ESTIMATE_TTL_S = 600  # fisierul temporar traieste 10 minute

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


def create_job(user_email: str) -> str:
    _cleanup_jobs()
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "user_email": user_email}
    _job_meta[job_id] = {"creat": time.monotonic(), "terminat": None}
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


def _marcheaza_terminat(job_id: str) -> None:
    meta = _job_meta.setdefault(job_id, {"creat": time.monotonic(), "terminat": None})
    meta["terminat"] = time.monotonic()


def get_job(job_id: str) -> dict[str, Any] | None:
    _cleanup_jobs()
    return _jobs.get(job_id)


def save_estimate(file_path: Path, filename: str, data: dict[str, Any]) -> str:
    _cleanup_expired()
    estimate_id = str(uuid.uuid4())
    _estimates[estimate_id] = {
        "file_path": str(file_path),
        "filename": filename,
        "created": time.monotonic(),
        **data,
    }
    return estimate_id


def pop_estimate(estimate_id: str) -> dict[str, Any] | None:
    _cleanup_expired()
    return _estimates.pop(estimate_id, None)


def _cleanup_expired() -> None:
    now = time.monotonic()
    for eid in list(_estimates):
        entry = _estimates[eid]
        if now - entry["created"] > ESTIMATE_TTL_S:
            Path(entry["file_path"]).unlink(missing_ok=True)
            _estimates.pop(eid, None)
