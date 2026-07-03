"""Job store + estimate store in-memory, partajate de mockup si scenarii.

Se golesc la fiecare restart/redeploy Render (acceptat — frontend-ul trateaza
job/estimate expirat cu mesaj "reincarca fisierul").
Minuta NU foloseste acest modul (are propriul _jobs, neatins).
"""
import time
import uuid
from pathlib import Path
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}
_estimates: dict[str, dict[str, Any]] = {}

ESTIMATE_TTL_S = 600  # fisierul temporar traieste 10 minute


def create_job(user_email: str) -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "user_email": user_email}
    return job_id


def set_step(job_id: str, step: str) -> None:
    if job_id in _jobs:
        _jobs[job_id]["step"] = step


def finish(job_id: str, **payload: Any) -> None:
    _jobs[job_id] = {"status": "done", **payload}


def fail(job_id: str, error: str) -> None:
    _jobs[job_id] = {"status": "error", "error": error}


def get_job(job_id: str) -> dict[str, Any] | None:
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
